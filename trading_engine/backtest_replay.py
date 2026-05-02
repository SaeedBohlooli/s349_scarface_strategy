"""
Historical bar replay using the same strategy / scanner / chart stack as TradingEngine.

Drives simulated wall/monotonic clocks via trading_utils.date_utils so RuntimeManager,
trade_time/busy_time evals, and per-bar should_run_once keys align with each replayed bar.

Does not submit live IB orders; uses optional on-disk OHLCV under dirs.backtest_ohlcv per
session date to avoid refetching (set backtest_run.refresh_ohlcv_from_ib to force IB).
"""

from __future__ import annotations

import contextlib
import dataclasses
import logging
import os
import time
from typing import Any, Dict, Iterator, List, Optional

import pandas as pd
import pandas_market_calendars as mcal

from trading_core.config_manager import ConfigManager
from trading_core.directory_manager import DirectoryManager
from trading_core.file_manager import FileManager
from trading_core.logging_manager import LoggingManager
from trading_core.market_data_store import MarketDataStore
from trading_core.runtime_manager import RuntimeManager
from trading_core.trading_ledger import TradingLedger
from trading_engine import application_state_helper
from trading_engine import chart_helper
from trading_engine import inidicators
from trading_engine import marketdata_helper
from trading_engine import options_helper
from trading_engine import order_helper
from trading_engine import exit_conditions
from trading_engine import position_helper
from trading_engine import strategy
from trading_engine import scanner
from trading_utils import date_utils
from trading_utils.ib_marketdata_async import get_stock_historical_data

logger = logging.getLogger(__name__)


@contextlib.contextmanager
def _backtest_cases_to_run_override(app_config: Dict[str, Any]) -> Iterator[None]:
    """
    Optional `backtest_run.cases_to_run` replaces `live.cases_to_run` only during replay.

    Omit this key so replay uses the same case list as live (recommended when live cases
    already include breakout/retest scanner cores).
    """
    bt = app_config.get("backtest_run") or {}
    if "cases_to_run" not in bt:
        yield
        return
    live = app_config.setdefault("live", {})
    original = list(live.get("cases_to_run", []))
    live["cases_to_run"] = list(bt["cases_to_run"])
    logger.info(
        "[backtest_replay] backtest_run.cases_to_run=%s (live default was %s)",
        live["cases_to_run"],
        original,
    )
    try:
        yield
    finally:
        live["cases_to_run"] = original


@dataclasses.dataclass
class ReplayBootStub:
    """Minimal boot object for RuntimeManager."""

    portfolio_id: str
    app_config: dict
    application_state: dict


def _nyse_dates_between(start_iso: str, end_iso: str) -> List[str]:
    cal = mcal.get_calendar("NYSE")
    sched = cal.schedule(start_date=start_iso, end_date=end_iso)
    return [pd.Timestamp(x).strftime("%Y-%m-%d") for x in sched.index]


def _parse_hhmm(s: str) -> tuple[int, int]:
    parts = str(s).strip().split(":")
    h = int(parts[0])
    m = int(parts[1]) if len(parts) > 1 else 0
    return h, m


def _minutes_from_midnight(h: int, m: int) -> int:
    return h * 60 + m


def session_timestamps_from_day_dataframe(
    day_df: pd.DataFrame,
    session_start_et: str = "04:00",
    session_end_et: str = "16:00",
) -> List[pd.Timestamp]:
    """Timestamps actually present in day_df, filtered to ET session window inclusive."""
    if day_df is None or day_df.empty:
        return []
    mn0 = _minutes_from_midnight(*_parse_hhmm(session_start_et))
    mn1 = _minutes_from_midnight(*_parse_hhmm(session_end_et))
    out: List[pd.Timestamp] = []
    seen = set()
    for t in sorted(pd.to_datetime(day_df["date"]).unique()):
        ts = pd.Timestamp(t)
        mn = _minutes_from_midnight(ts.hour, ts.minute)
        if mn0 <= mn <= mn1 and ts not in seen:
            seen.add(ts)
            out.append(ts)
    return out


def _filter_through(dfull: pd.DataFrame, ts: pd.Timestamp) -> pd.DataFrame:
    if dfull is None or dfull.empty:
        return pd.DataFrame()
    col = pd.to_datetime(dfull["date"])
    if getattr(col.dt, "tz", None) is not None:
        col = col.dt.tz_convert("America/New_York").dt.tz_localize(None)
    ts_cmp = pd.Timestamp(ts)
    if ts_cmp.tzinfo is not None:
        ts_cmp = ts_cmp.tz_convert("America/New_York").tz_localize(None)
    return dfull[col <= ts_cmp].copy()


def slice_session_day_only(dfull: pd.DataFrame, session_date_yyyy_mm_dd: str) -> pd.DataFrame:
    if dfull is None or dfull.empty:
        return pd.DataFrame()
    dd = pd.to_datetime(dfull["date"])
    if getattr(dd.dt, "tz", None) is not None:
        dd = dd.dt.tz_convert("America/New_York").dt.tz_localize(None)
    d_norm = pd.Timestamp(session_date_yyyy_mm_dd).normalize()
    return dfull[dd.dt.normalize() == d_norm].copy()


_OHLCV_CACHE_COLS = ("date", "open", "high", "low", "close", "volume")


def _normalize_ib_hist_df(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.copy()
    if "date" not in out.columns:
        return pd.DataFrame()
    out["date"] = pd.to_datetime(out["date"])
    if getattr(out["date"].dt, "tz", None) is not None:
        out["date"] = out["date"].dt.tz_convert("America/New_York").dt.tz_localize(None)
    out = out.sort_values("date").reset_index(drop=True)
    out = out.drop_duplicates(subset=["date"], keep="last").reset_index(drop=True)
    return out


def _backtest_ohlcv_cache_file(cache_dir: Optional[str], symbol: str) -> Optional[str]:
    if not cache_dir:
        return None
    return os.path.join(cache_dir, f"{symbol}-1min.csv")


def _load_backtest_ohlcv_cache(
    cache_file: str,
    session_date_yyyy_mm_dd: str,
) -> pd.DataFrame:
    try:
        df = pd.read_csv(cache_file)
    except Exception as exc:
        logger.warning("[backtest_replay] Could not read OHLCV cache %s: %s", cache_file, exc)
        return pd.DataFrame()
    df = _normalize_ib_hist_df(df)
    if df.empty:
        return df
    day = slice_session_day_only(df, session_date_yyyy_mm_dd)
    if day.empty:
        logger.info(
            "[backtest_replay] OHLCV cache %s has no rows on session %s — refetch",
            cache_file,
            session_date_yyyy_mm_dd,
        )
        return pd.DataFrame()
    return df


def _save_backtest_ohlcv_cache(cache_file: str, df: pd.DataFrame) -> None:
    os.makedirs(os.path.dirname(cache_file), exist_ok=True)
    cols = [c for c in _OHLCV_CACHE_COLS if c in df.columns]
    if len(cols) < 2 or "date" not in cols:
        logger.warning("[backtest_replay] Skip OHLCV cache write — missing columns in df")
        return
    out = df[cols].copy()
    out.to_csv(cache_file, index=False)
    logger.info("[backtest_replay] Wrote OHLCV cache %s (%s rows)", cache_file, len(out))


async def prefetch_symbol_history(
    ib,
    *,
    symbol: str,
    app_config: dict,
    ib_historical_window: str,
    session_date_yyyy_mm_dd: str,
    cache_dir: Optional[str] = None,
    refresh_ohlcv_from_ib: bool = False,
) -> pd.DataFrame:
    cache_file = _backtest_ohlcv_cache_file(cache_dir, symbol)

    if cache_file and not refresh_ohlcv_from_ib and os.path.isfile(cache_file):
        cached = _load_backtest_ohlcv_cache(cache_file, session_date_yyyy_mm_dd)
        if not cached.empty:
            logger.info(
                "[backtest_replay] Using OHLCV cache for %s session=%s (%s rows)",
                symbol,
                session_date_yyyy_mm_dd,
                len(cached),
            )
            return cached

    end_compact = pd.Timestamp(session_date_yyyy_mm_dd).strftime("%Y%m%d")
    df = await get_stock_historical_data(
        ib,
        symbol,
        time_frame="1m",
        end_date=end_compact,
        duration=ib_historical_window,
        contract_month=app_config.get("symbols_meta", {}).get(symbol, {}).get("contract_month"),
        use_RTH=False,
        print_last_few_rows=0,
    )
    if df is None or df.empty:
        logger.warning("[backtest_replay] No bars for symbol=%s end=%s", symbol, session_date_yyyy_mm_dd)
        return pd.DataFrame()

    df = _normalize_ib_hist_df(df)
    if cache_file:
        _save_backtest_ohlcv_cache(cache_file, df)

    return df


async def _run_symbol_tick(
    *,
    ib,
    app_config,
    application_state,
    runtime: RuntimeManager,
    market_data: MarketDataStore,
    symbol: str,
    day_of_week: str,
    df_slice: pd.DataFrame,
) -> None:
    if df_slice.empty or len(df_slice) == 0:
        return

    market_data.dfs_map[symbol] = df_slice
    lc = df_slice["close"].iloc[-1]
    application_state.setdefault("latest_prices", {})[symbol] = float(lc) if pd.notna(lc) else -1.0

    if application_state.get("is_save_time"):
        try:
            logger.debug("%s df tail:\n%s", symbol, df_slice.tail(4).to_markdown())
        except Exception:
            logger.debug("%s df tail rows=%s", symbol, len(df_slice))

    qqq_df = market_data.dfs_map.get("QQQ")
    relative_strength_df = inidicators.compute_relative_strength(df_slice, qqq_df, period=20)
    intraday_rs_df = inidicators.compute_intraday_rs(df_slice, qqq_df)

    if runtime.should_run_once(
        f'{symbol}-DYNAMIC-TOLERANCE-CALCULATION-{str(df_slice["date"].iloc[-1])}'
    ):
        from utils import atr_tolerance_helper

        dynamic_tolerance = atr_tolerance_helper.get_dynamic_tolerance(
            df_slice[:-1].copy(), level=0, min_tick=0.01
        )
        dynamic_tolerance["timestamp"] = str(df_slice["date"].iloc[-1])
        market_data.data_store.setdefault(symbol, {})["dynamic_tolerance"] = dynamic_tolerance
        application_state.setdefault("dynamic_tolerances", {})[symbol] = dynamic_tolerance

    if not strategy.all_levels_in(application_state, symbol, ["PDH"]):
        strategy.calculate_PDL_PDH(application_state, symbol, df_slice, day_of_week)

    if not strategy.all_levels_in(application_state, symbol, ["5MH"]):
        strategy.find_add_5MH_5ML(application_state, df_slice, symbol)

    if not strategy.all_levels_in(application_state, symbol, ["PMH", "PML"]):
        strategy.find_add_PMH_PML(application_state, df_slice, symbol)

    df_slice = strategy.compute_indicators(app_config, application_state, symbol, df_slice)
    market_data.dfs_map[symbol] = df_slice
    are_all_levels_in = strategy.all_levels_in(application_state, symbol)

    if runtime.should_run_once(f'{symbol}-CANDLE-{str(df_slice["date"].iloc[-1])}'):
        chart_helper.mark_tolerance_to_the_level(app_config, application_state, symbol, "5ML", market_data)
        chart_helper.mark_tolerance_to_the_level(app_config, application_state, symbol, "5MH", market_data)
        chart_helper.mark_atr_to_the_level(application_state, symbol, "up", "5MH", market_data)
        chart_helper.mark_atr_to_the_level(application_state, symbol, "down", "5ML", market_data)
        chart_helper.add_atr_to_candle_info(symbol, market_data)
        chart_helper.add_rs_relative_to_candle_info(symbol, intraday_rs_df, market_data)
        chart_helper.add_open_position_to_candle_info(application_state, symbol, market_data)

    if are_all_levels_in and runtime.should_run_once(f"{symbol}-CLOSED-LEVELS-MARKED"):
        chart_helper.mark_close_levels(app_config, application_state, symbol, df_slice)

    buy_sell_case_results_list = scanner.check_buy_and_sell_cases(
        ib, app_config, application_state, symbol, market_data
    )
    buy_sell_case_results_list = order_helper.add_case_manual_order_to_buy_sell_case_results_list(
        application_state, symbol, buy_sell_case_results_list
    )

    await order_helper.check_buy_sell_result_to_send_order(
        ib,
        app_config,
        application_state,
        buy_sell_case_results_list,
        symbol,
        df_slice,
        market_data,
        runtime,
        replay_markers_only=True,
    )
    await exit_conditions.check_for_stop_loss_and_take_profit(
        ib, app_config, application_state, market_data, replay_markers_only=True
    )

    # Match engine.py: gap runs when `not should_run_once(MARK_GAP)` (first call arms the flag, second runs).
    current_hh_mm_ny = runtime.now_hhmm()
    if application_state["is_save_time"] and 931 < current_hh_mm_ny and not runtime.should_run_once(
        f"{symbol}-MARK_GAP"
    ):
        chart_helper.detect_a_mark_market_gap(application_state, symbol, df_slice)

    chart_helper.add_buy_a_sell_entries_to_signals(
        app_config, application_state, buy_sell_case_results_list, symbol, market_data
    )
    position_helper.update_position_for_avg_cost(application_state)
    position_helper.update_position_for_entry_execution_price(application_state)


async def replay_one_calendar_day(
    *,
    ib,
    portfolio_id: str,
    app_config: Dict[str, Any],
    session_date_yyyy_mm_dd: str,
    symbols: List[str],
    ib_historical_window: str,
    session_start: str,
    session_end: str,
    refresh_ohlcv_from_ib: bool = False,
) -> None:
    prefetch_symbols = list(dict.fromkeys(["QQQ"] + [s for s in symbols if s != "QQQ"]))
    symbols_save_charts = list(symbols)
    dm = DirectoryManager(
        portfolio_id=portfolio_id,
        app_config=app_config,
        mode="live",
        session_date=session_date_yyyy_mm_dd,
    )
    FileManager.set_dirs(dm)
    FileManager.set_files_config(app_config["files"])
    backtest_ohlcv_dir = getattr(dm.paths, "backtest_ohlcv", None)

    with _backtest_cases_to_run_override(app_config):
        await _replay_one_calendar_day_body(
            ib=ib,
            portfolio_id=portfolio_id,
            app_config=app_config,
            session_date_yyyy_mm_dd=session_date_yyyy_mm_dd,
            symbols_save_charts=symbols_save_charts,
            prefetch_symbols=prefetch_symbols,
            ib_historical_window=ib_historical_window,
            session_start=session_start,
            session_end=session_end,
            backtest_ohlcv_dir=backtest_ohlcv_dir,
            refresh_ohlcv_from_ib=refresh_ohlcv_from_ib,
        )


async def _replay_one_calendar_day_body(
    *,
    ib,
    portfolio_id: str,
    app_config: Dict[str, Any],
    session_date_yyyy_mm_dd: str,
    symbols_save_charts: List[str],
    prefetch_symbols: List[str],
    ib_historical_window: str,
    session_start: str,
    session_end: str,
    backtest_ohlcv_dir: Optional[str] = None,
    refresh_ohlcv_from_ib: bool = False,
) -> None:
    TradingLedger.clear_all()
    hover_cols = [
        "symbol",
        "time_frame",
        "object",
        "color",
        "date_1",
        "price_1",
        "date_2",
        "price_2",
        "memo",
        "unique_id",
    ]
    TradingLedger.set_dataframe_columns("hover_df", hover_cols)
    key_lv_cols = ["symbol", "time_frame", "key_level", "price", "memo", "unique_id"]
    TradingLedger.set_dataframe_columns("key_levels_df", key_lv_cols)

    RuntimeManager.reset_scheduler_state_for_replay()

    application_state: Dict[str, Any] = {
        "portfolio_id": portfolio_id,
        "mode": "live",
        "chart_replay_save_full": True,
        "signals": [],  # not used directly; ledger list "signals" is authoritative
    }
    application_state_helper.initialize_application_state_replay(
        app_config, application_state, replay_symbols=prefetch_symbols
    )

    boot = ReplayBootStub(portfolio_id, app_config, application_state)
    runtime = RuntimeManager(boot)

    full_hist: Dict[str, pd.DataFrame] = {}
    for sym in prefetch_symbols:
        full_hist[sym] = await prefetch_symbol_history(
            ib,
            symbol=sym,
            app_config=app_config,
            ib_historical_window=ib_historical_window,
            session_date_yyyy_mm_dd=session_date_yyyy_mm_dd,
            cache_dir=backtest_ohlcv_dir,
            refresh_ohlcv_from_ib=refresh_ohlcv_from_ib,
        )

    usable = all(not full_hist[s].empty for s in prefetch_symbols)
    if not usable:
        logger.warning("[backtest_replay] Skipping session %s (missing bars for some symbols)", session_date_yyyy_mm_dd)
        date_utils.clear_replay_context()
        return

    first_sym = prefetch_symbols[0]
    day_df = slice_session_day_only(full_hist[first_sym], session_date_yyyy_mm_dd)
    if day_df.empty:
        logger.warning("[backtest_replay] No bars on session calendar date %s for %s", session_date_yyyy_mm_dd, first_sym)
        date_utils.clear_replay_context()
        return

    timestamps = session_timestamps_from_day_dataframe(day_df, session_start, session_end)
    if not timestamps:
        logger.warning("[backtest_replay] Empty session timestamps for %s", session_date_yyyy_mm_dd)
        date_utils.clear_replay_context()
        return

    market_data = MarketDataStore()

    # Same option chains / strikes merge as live (engine ORCHESTRATE_EXPIRATIONS_STRIKES) for contract selection.
    try:
        await options_helper.orchestrate_expirations_strikes(ib, app_config, application_state, market_data)
    except Exception as exc:
        logger.warning(
            "[backtest_replay] orchestrate_expirations_strikes failed — order/entry markers may differ from live: %s",
            exc,
        )

    dow = pd.Timestamp(session_date_yyyy_mm_dd).strftime("%A")

    mono_base = time.time()

    run_number_outer = 0
    for i, ts in enumerate(timestamps):
        date_utils.set_replay_wall_clock_et_naive(ts.to_pydatetime())
        date_utils.set_replay_monotonic_time(mono_base + float(i))

        application_state_helper.initialize_application_state_for_run(app_config, application_state)

        run_number_outer += 1
        uniq_x = runtime.generate_unique_run_number(run_number_outer)

        for sn, symbol in enumerate(prefetch_symbols):
            application_state["unique_run_number"] = f"{uniq_x}-{sn + 1}"
            application_state_helper.initialize_application_state_for_symbol_run(app_config, application_state)
            dfs = full_hist.get(symbol)
            df_sl = _filter_through(dfs, ts)

            if df_sl.empty:
                continue
            df_feats = inidicators.populate_volume_ratio(inidicators.popualate_features(df_sl.copy()))

            await _run_symbol_tick(
                ib=ib,
                app_config=app_config,
                application_state=application_state,
                runtime=runtime,
                market_data=market_data,
                symbol=symbol,
                day_of_week=dow,
                df_slice=df_feats,
            )

    chart_helper.add_candle_info_df_to_signals()
    chart_helper.convert_signals_to_hover_df()

    session_only_map: Dict[str, pd.DataFrame] = {}
    for sx in symbols_save_charts:
        full = full_hist.get(sx)
        if full is None or full.empty:
            continue
        sday = slice_session_day_only(full, session_date_yyyy_mm_dd)
        if not sday.empty:
            session_only_map[sx] = inidicators.populate_volume_ratio(inidicators.popualate_features(sday.copy()))

    application_state.setdefault("chart_replay_save_full", True)
    for sx, sdf in session_only_map.items():
        marketdata_helper.save_ohlc_dataframe_to_charts(application_state, sx, sdf, save_tabular=False)

    # Same merged RS / intraday-RS file as live `save_extra_features_df` (engine SAVE on interval).
    qqq_ses = session_only_map.get("QQQ")
    if qqq_ses is not None and not qqq_ses.empty:
        for sx, sdf in session_only_map.items():
            rel = inidicators.compute_relative_strength(sdf, qqq_ses, period=20)
            intra = inidicators.compute_intraday_rs(sdf, qqq_ses)
            marketdata_helper.save_extra_features_df(
                application_state, sx, sdf, rel, intra, time_frame="1 min", save_tabular=False
            )

    dodf = TradingLedger.get_dataframe("drawing_objects_df")
    if dodf.empty:
        TradingLedger.set_dataframe(
            "drawing_objects_df",
            pd.DataFrame(
                columns=[
                    "symbol",
                    "time_frame",
                    "object",
                    "color",
                    "date_1",
                    "price_1",
                    "date_2",
                    "price_2",
                    "memo",
                    "unique_id",
                ]
            ),
        )
        dodf = TradingLedger.get_dataframe("drawing_objects_df")
    FileManager.save_my_df(
        dodf,
        "drawing_objects_df",
        mode="w",
        drop_duplicates=True,
        save_tabular=True,
    )
    FileManager.save_my_df(
        TradingLedger.get_dataframe("hover_df"), "hover_df", mode="w", drop_duplicates=True, save_tabular=True
    )
    FileManager.save_my_df(
        TradingLedger.get_dataframe("key_levels_df"),
        df_name="key_levels_df",
        dir="charts",
        file_name="11-key_levels_df.csv",
        mode="w",
        drop_duplicates=True,
        save_tabular=True,
    )

    logger.info("[backtest_replay] Completed session_date=%s", session_date_yyyy_mm_dd)
    date_utils.clear_replay_context()


async def run_backtest_job_from_cli(*, portfolio_id: str, config_folder: str = "") -> None:
    configs_folder = f"{config_folder}/configs" if config_folder else "../configs"

    cfg = (
        ConfigManager.load(portfolio_id)
        if config_folder == ""
        else __import__("trading_utils.config_utils").config_utils.load_app_config(
            portfolio_id, config_folder=configs_folder
        )
    )

    job = cfg.get("backtest_run") or {}
    if not job.get("enabled", False):
        logger.warning("[backtest_run] disabled in config — nothing to do.")
        return

    start = job["start_date"]
    end = job["end_date"]
    syms_cfg = job.get("symbols") or []
    symbols = syms_cfg if isinstance(syms_cfg, list) and len(syms_cfg) > 0 else list(cfg.get("symbols", []))
    ib_window = job.get("ib_historical_window", cfg.get("live", {}).get("historical_days", "6 D"))
    ss = job.get("session_start_et", "04:00")
    se = job.get("session_end_et", "16:00")
    refresh_ohlcv = bool(job.get("refresh_ohlcv_from_ib", False))

    if "QQQ" in cfg.get("symbols", []) and "QQQ" not in symbols:
        symbols = ["QQQ"] + [s for s in symbols if s != "QQQ"]

    dates = _nyse_dates_between(start, end)
    if not dates:
        logger.warning("[backtest_run] No NYSE session dates between %s and %s.", start, end)
        return

    dm0 = DirectoryManager(
        portfolio_id=portfolio_id,
        app_config=cfg,
        mode="live",
        session_date=dates[0],
    )
    LoggingManager.setup(
        log_dir=dm0.log_dir,
        portfolio_id=portfolio_id,
        logging_level=logging.INFO,
    )

    from trading_core.ib_connector import IBConnector

    ib = await IBConnector.connect_from_config(cfg)

    try:
        for d in dates:
            await replay_one_calendar_day(
                ib=ib,
                portfolio_id=portfolio_id,
                app_config=cfg,
                session_date_yyyy_mm_dd=d,
                symbols=symbols,
                ib_historical_window=ib_window,
                session_start=ss,
                session_end=se,
                refresh_ohlcv_from_ib=refresh_ohlcv,
            )
    finally:
        ib.disconnect()
        logger.info("[backtest_replay] IB disconnected.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
