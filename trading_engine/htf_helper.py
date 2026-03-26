import logging
import numpy as np
import pandas as pd

from trading_utils import ib_marketdata_async
from trading_utils import date_utils
from trading_core.trading_ledger import TradingLedger

logger = logging.getLogger(__name__)


# =========================================================================
# Public API
# =========================================================================

async def refresh_htf_levels(ib, app_config, application_state, market_data):
    """
    Fetch higher-timeframe bars (1D, 4H, 30m, 15m) for every tradeable symbol,
    detect swing highs/lows, and store them in application_state['htf_levels'].

    Called periodically from engine.py (e.g. every 15 min).
    """
    htf_config = app_config.get('htf', {})
    if not htf_config.get('enabled', False):
        return

    timeframes = htf_config.get('timeframes', ['1D', '4H', '30m', '15m'])
    swing_lookback = htf_config.get('swing_lookback', 5)
    min_reversal_atr = htf_config.get('min_reversal_atr', 0.3)
    zone_merge_atr = htf_config.get('zone_merge_atr', 0.5)

    symbols = [s for s in app_config.get('symbols', [])
               if app_config.get('symbols_meta', {}).get(s, {}).get('can_trade', False)]

    for symbol in symbols:
        contract_month = app_config.get('symbols_meta', {}).get(symbol, {}).get('contract_month')
        symbol_htf = {}

        # Get ATR from 1m df for zone merging (use what we already have)
        df_1m = market_data.dfs_map.get(symbol)
        atr = df_1m['atr_14'].iloc[-2] if df_1m is not None and 'atr_14' in df_1m.columns and len(df_1m) > 1 else 1.0

        for tf in timeframes:
            try:
                df = await ib_marketdata_async.get_stock_historical_data(
                    ib, symbol, time_frame=tf, contract_month=contract_month, use_RTH=False
                )
                if df is None or len(df) < swing_lookback * 2:
                    logger.warning(f"HTF | {symbol} {tf}: insufficient data ({0 if df is None else len(df)} bars)")
                    continue

                resistance, support = detect_swing_levels(
                    df, lookback=swing_lookback, min_reversal_atr=min_reversal_atr,
                    zone_merge_distance=zone_merge_atr * atr
                )
                symbol_htf[tf] = {
                    'resistance': resistance,
                    'support': support,
                }
                logger.info(f"HTF | {symbol} {tf}: R={resistance}, S={support}")

            except Exception as e:
                logger.error(f"HTF | {symbol} {tf}: error fetching data: {e}")
                continue

        application_state.setdefault('htf_levels', {})[symbol] = symbol_htf

    # Persist snapshot for backtesting
    _append_to_htf_levels_df(application_state)
    logger.info(f"HTF | refresh complete for {len(symbols)} symbols")


def check_htf_clearance(app_config, application_state, symbol, side, entry_price):
    """
    Entry filter: check if there's enough room to the nearest HTF resistance (long)
    or support (short).

    Returns: (clear: bool, reason: str, nearest_level: float or None)
    """
    htf_config = app_config.get('htf', {})
    if not htf_config.get('enabled', False) or not htf_config.get('use_htf_entry', False):
        return True, '', None

    min_clearance_atr = htf_config.get('min_clearance_atr', 1.0)
    htf_levels = application_state.get('htf_levels', {}).get(symbol, {})
    timeframe_weights = htf_config.get('timeframe_weights', {'1D': 1.0, '4H': 0.8, '30m': 0.6, '15m': 0.4})

    # Get ATR from scoring or market data
    atr = _get_symbol_atr(application_state, symbol)
    if atr <= 0:
        return True, 'no ATR available', None

    if side == 'long':
        # Collect all resistance levels above entry
        blocking_levels = _collect_levels_above(htf_levels, entry_price, 'resistance', timeframe_weights)
    else:
        # Collect all support levels below entry
        blocking_levels = _collect_levels_below(htf_levels, entry_price, 'support', timeframe_weights)

    if not blocking_levels:
        return True, '', None

    # Find nearest level (weighted by timeframe importance)
    nearest = blocking_levels[0]  # already sorted by distance
    distance_in_atr = nearest['distance'] / atr

    if distance_in_atr < min_clearance_atr:
        reason = (f"HTF {nearest['timeframe']} {'resistance' if side == 'long' else 'support'} "
                  f"at {nearest['price']:.2f} is only {distance_in_atr:.1f} ATR away")
        return False, reason, nearest['price']

    return True, '', nearest['price']


def compute_dynamic_take_profits(app_config, application_state, symbol, side, entry_price):
    """
    Compute take profit targets based on HTF levels instead of fixed percentages.

    Returns: list of dicts, ordered by distance from entry:
        [{'price': 233.20, 'close_pct': 0.60, 'source': '30m resistance', 'label': 'htf_tp1'}, ...]
    Returns empty list if HTF TP is disabled or no levels found.
    """
    htf_config = app_config.get('htf', {})
    if not htf_config.get('enabled', False) or not htf_config.get('use_htf_tp', False):
        return []

    htf_levels = application_state.get('htf_levels', {}).get(symbol, {})
    timeframe_weights = htf_config.get('timeframe_weights', {'1D': 1.0, '4H': 0.8, '30m': 0.6, '15m': 0.4})
    tp_close_pcts = htf_config.get('tp_close_percentages', [0.60, 0.20, -1])
    min_tp_distance_atr = htf_config.get('min_tp_distance_atr', 0.3)

    atr = _get_symbol_atr(application_state, symbol)
    if atr <= 0:
        return []

    if side == 'long':
        target_levels = _collect_levels_above(htf_levels, entry_price, 'resistance', timeframe_weights)
    else:
        target_levels = _collect_levels_below(htf_levels, entry_price, 'support', timeframe_weights)

    # Filter: levels must be at least min_tp_distance_atr away
    target_levels = [l for l in target_levels if l['distance'] / atr >= min_tp_distance_atr]

    if not target_levels:
        return []

    # Assign close percentages to nearest levels
    dynamic_tps = []
    for i, level in enumerate(target_levels[:len(tp_close_pcts)]):
        close_pct = tp_close_pcts[i] if i < len(tp_close_pcts) else -1
        dynamic_tps.append({
            'price': level['price'],
            'close_pct': close_pct,
            'source': f"{level['timeframe']} {'resistance' if side == 'long' else 'support'}",
            'label': f'htf_tp{i + 1}',
            'distance_atr': round(level['distance'] / atr, 2),
        })

    return dynamic_tps


# =========================================================================
# Swing Level Detection
# =========================================================================

def detect_swing_levels(df, lookback=5, min_reversal_atr=0.3, zone_merge_distance=0.5):
    """
    Detect swing highs (resistance) and swing lows (support) from OHLC data.

    A swing high: bar's high is the highest among `lookback` bars on each side.
    A swing low: bar's low is the lowest among `lookback` bars on each side.

    Returns: (resistance_levels: list[float], support_levels: list[float])
             Both sorted by proximity to current price.
    """
    if df is None or len(df) < lookback * 2 + 1:
        return [], []

    highs = df['high'].values
    lows = df['low'].values
    closes = df['close'].values

    # Compute ATR for filtering (simple approach)
    tr = np.maximum(highs[1:] - lows[1:],
                    np.maximum(np.abs(highs[1:] - closes[:-1]),
                               np.abs(lows[1:] - closes[:-1])))
    atr = np.mean(tr[-14:]) if len(tr) >= 14 else np.mean(tr) if len(tr) > 0 else 1.0
    min_reversal = min_reversal_atr * atr

    swing_highs = []
    swing_lows = []

    # Don't check the last `lookback` bars (they haven't been confirmed yet)
    for i in range(lookback, len(df) - lookback):
        # Swing high: highest high in window
        window_highs = highs[i - lookback:i + lookback + 1]
        if highs[i] == np.max(window_highs):
            # Verify reversal: price moved down at least min_reversal after the swing
            future_lows = lows[i + 1:i + lookback + 1]
            if len(future_lows) > 0 and (highs[i] - np.min(future_lows)) >= min_reversal:
                swing_highs.append(highs[i])

        # Swing low: lowest low in window
        window_lows = lows[i - lookback:i + lookback + 1]
        if lows[i] == np.min(window_lows):
            future_highs = highs[i + 1:i + lookback + 1]
            if len(future_highs) > 0 and (np.max(future_highs) - lows[i]) >= min_reversal:
                swing_lows.append(lows[i])

    # Merge nearby levels into zones
    resistance = _merge_zones(swing_highs, zone_merge_distance)
    support = _merge_zones(swing_lows, zone_merge_distance)

    # Sort by proximity to current price
    current_price = closes[-1]
    resistance.sort(key=lambda x: abs(x - current_price))
    support.sort(key=lambda x: abs(x - current_price))

    return resistance, support


# =========================================================================
# Internal helpers
# =========================================================================

def _merge_zones(levels, merge_distance):
    """Merge levels that are within merge_distance of each other. Return zone midpoints."""
    if not levels:
        return []

    sorted_levels = sorted(levels)
    zones = []
    current_zone = [sorted_levels[0]]

    for level in sorted_levels[1:]:
        if level - current_zone[-1] <= merge_distance:
            current_zone.append(level)
        else:
            zones.append(np.mean(current_zone))
            current_zone = [level]
    zones.append(np.mean(current_zone))

    return [round(z, 2) for z in zones]


def _collect_levels_above(htf_levels, price, level_type, timeframe_weights):
    """Collect all levels above price, sorted by distance (nearest first)."""
    results = []
    for tf, levels_map in htf_levels.items():
        weight = timeframe_weights.get(tf, 0.5)
        for level_price in levels_map.get(level_type, []):
            if level_price > price:
                results.append({
                    'price': level_price,
                    'distance': level_price - price,
                    'timeframe': tf,
                    'weight': weight,
                })
    results.sort(key=lambda x: x['distance'])
    return results


def _collect_levels_below(htf_levels, price, level_type, timeframe_weights):
    """Collect all levels below price, sorted by distance (nearest first)."""
    results = []
    for tf, levels_map in htf_levels.items():
        weight = timeframe_weights.get(tf, 0.5)
        for level_price in levels_map.get(level_type, []):
            if level_price < price:
                results.append({
                    'price': level_price,
                    'distance': price - level_price,
                    'timeframe': tf,
                    'weight': weight,
                })
    results.sort(key=lambda x: x['distance'])
    return results


def _get_symbol_atr(application_state, symbol):
    """Get ATR from scoring raw data or return 0."""
    scoring = application_state.get('scoring', {}).get(symbol, {})
    raw = scoring.get('raw', {})
    return raw.get('atr_14', 0)


def _append_to_htf_levels_df(application_state):
    """Persist HTF levels snapshot to TradingLedger for CSV output."""
    timestamp = str(date_utils.time_now())
    rows = []
    for symbol, tf_map in application_state.get('htf_levels', {}).items():
        for tf, levels_map in tf_map.items():
            for level_price in levels_map.get('resistance', []):
                rows.append({
                    'timestamp': timestamp,
                    'symbol': symbol,
                    'timeframe': tf,
                    'level_type': 'resistance',
                    'price': level_price,
                })
            for level_price in levels_map.get('support', []):
                rows.append({
                    'timestamp': timestamp,
                    'symbol': symbol,
                    'timeframe': tf,
                    'level_type': 'support',
                    'price': level_price,
                })
    if rows:
        TradingLedger.add_to_dataframe("htf_levels_df", rows, buffer=True)
