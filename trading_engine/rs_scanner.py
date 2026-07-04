import logging
import datetime

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# RS RANKER — Relative Strength ranking helpers
# Spec: docs/rs_ranker_requirements.md  §3.1 – §3.6
#
# Pure snapshot functions — no data fetching, no side-effects.
# All functions work directly inside config condition strings because
# check_buy_sell_condition already exposes these names in the eval() scope
# (scanner.py imports * from this module via its globals).
#
# Variables available in the config eval context:
#   df       — symbol intraday bars DataFrame
#   qqq_df   — QQQ intraday bars DataFrame
#   levels   — application_state['levels'][symbol]  (PDH, PDL, PMH, PML, …)
#   price    — df['close'].iloc[-1]
#
# Example config conditions:
#   - rs_trend(df, qqq_df, levels) == 'Long'
#   - rs_spread(df, qqq_df) > 0.5
#   - rs_prev_d(df, levels) == 'Above'
#   - rs_pre_mkt(df, levels) == 'Above'
#   - rs_since_open_pct(df) > 1.0
#   - rs_move_pct(df) > 0.5
# ─────────────────────────────────────────────────────────────────────────────


def _rs_get_rth_open(df):
    """
    Returns the 9:30 RTH open price from an intraday bars DataFrame.
    Falls back to the first bar of today's session when the 09:30 bar is absent.
    Returns None if no today data exists.
    """
    today = df['date'].dt.date.max()
    today_df = df[df['date'].dt.date == today]
    if today_df.empty:
        return None
    mask_930 = today_df['date'].dt.time == datetime.time(9, 30)
    if mask_930.any():
        return today_df.loc[mask_930].iloc[0]['open']
    # fallback: first bar of the session
    return today_df.iloc[0]['open']


def rs_move_pct(df):
    """
    §3.1  Move / Gap % = (RTH_open − prev_close) / prev_close × 100

    Fixed at the open — does not change during the session.
    Display / context field only; does not feed into RS Spread or Trend.
    Returns None when data is insufficient.
    """
    rth_open = _rs_get_rth_open(df)
    if rth_open is None:
        return None
    today = df['date'].dt.date.max()
    prev_df = df[df['date'].dt.date < today]
    if prev_df.empty:
        return None
    prev_close = prev_df['close'].iloc[-1]
    if prev_close == 0:
        return None
    result = round((rth_open - prev_close) / prev_close * 100, 4)
    logger.debug(f"[rs_move_pct] rth_open:{rth_open} prev_close:{prev_close} move_pct:{result}")
    return result


def rs_since_open_pct(df):
    """
    §3.2  Since-Open % = (current_price − RTH_open) / RTH_open × 100

    Measures intraday movement since the RTH open.
    Used by rs_spread() for relative comparison against QQQ.
    Returns None when the RTH open cannot be determined.
    """
    rth_open = _rs_get_rth_open(df)
    if not rth_open:
        return None
    price = df['close'].iloc[-1]
    result = round((price - rth_open) / rth_open * 100, 4)
    logger.debug(f"[rs_since_open_pct] price:{price} rth_open:{rth_open} since_open_pct:{result}")
    return result


def rs_spread(df, qqq_df):
    """
    §3.3  RS Spread = SinceOpen%(symbol) − SinceOpen%(QQQ)

    Positive  → symbol outperforming QQQ since the RTH open.
    Negative  → symbol underperforming.

    Primary field for ranking the watchlist (strongest to weakest).
    Use this continuous value for any entry logic — not the Trend label.
    Returns None when either since-open % cannot be computed.
    """
    sym_pct = rs_since_open_pct(df)
    qqq_pct = rs_since_open_pct(qqq_df)
    if sym_pct is None or qqq_pct is None:
        logger.warning(f"[rs_spread] cannot compute — sym_pct:{sym_pct} qqq_pct:{qqq_pct}")
        return None
    result = round(sym_pct - qqq_pct, 4)
    logger.debug(f"[rs_spread] sym_pct:{sym_pct} qqq_pct:{qqq_pct} spread:{result}")
    return result


def rs_prev_d(df, levels):
    """
    §3.4  PrevD — price position relative to Prior Day High / Low.

    Returns: 'Above' | 'Below' | 'Inside'
    Falls back to 'Inside' when PDH / PDL are absent from levels.
    """
    price = df['close'].iloc[-1]
    pdh = levels.get('PDH')
    pdl = levels.get('PDL')
    if pdh is None or pdl is None:
        logger.warning("[rs_prev_d] PDH or PDL missing from levels — defaulting to Inside")
        return 'Inside'
    if price > pdh:
        label = 'Above'
    elif price < pdl:
        label = 'Below'
    else:
        label = 'Inside'
    logger.debug(f"[rs_prev_d] price:{price} PDH:{pdh} PDL:{pdl} → {label}")
    return label


def rs_pre_mkt(df, levels):
    """
    §3.5  PreMkt — price position relative to Premarket High / Low.

    Returns: 'Above' | 'Below' | 'Inside'
    Falls back to 'Inside' when PMH / PML are absent from levels.
    """
    price = df['close'].iloc[-1]
    pmh = levels.get('PMH')
    pml = levels.get('PML')
    if pmh is None or pml is None:
        logger.warning("[rs_pre_mkt] PMH or PML missing from levels — defaulting to Inside")
        return 'Inside'
    if price > pmh:
        label = 'Above'
    elif price < pml:
        label = 'Below'
    else:
        label = 'Inside'
    logger.debug(f"[rs_pre_mkt] price:{price} PMH:{pmh} PML:{pml} → {label}")
    return label


def rs_trend(df, qqq_df, levels, threshold=0.05):
    """
    §3.6  Trend — 3-factor vote: PrevD + PreMkt + RS Spread.

    Each factor contributes 1 bull or 1 bear point:
      PrevD    'Above' → +1 bull  |  'Below' → +1 bear
      PreMkt   'Above' → +1 bull  |  'Below' → +1 bear
      RS Spread > +threshold → +1 bull  |  < −threshold → +1 bear

    Scoring:
      3 bull            → 'Long'
      3 bear            → 'Short'
      ≥2 bull > bear    → 'Long'
      ≥2 bear > bull    → 'Short'
      otherwise         → 'Flat'

    ⚠  threshold=0.05 is inherited from Pine Script and has not been backtested.
       For actual entry logic use rs_spread() (continuous), not this label.

    Returns: 'Long' | 'Short' | 'Flat'
    """
    spread  = rs_spread(df, qqq_df)
    prev_d  = rs_prev_d(df, levels)
    pre_mkt = rs_pre_mkt(df, levels)

    bull = 0
    bear = 0

    if prev_d == 'Above':
        bull += 1
    elif prev_d == 'Below':
        bear += 1

    if pre_mkt == 'Above':
        bull += 1
    elif pre_mkt == 'Below':
        bear += 1

    if spread is not None:
        if spread > threshold:
            bull += 1
        elif spread < -threshold:
            bear += 1

    if bull == 3:
        trend = 'Long'
    elif bear == 3:
        trend = 'Short'
    elif bull >= 2 and bull > bear:
        trend = 'Long'
    elif bear >= 2 and bear > bull:
        trend = 'Short'
    else:
        trend = 'Flat'

    logger.info(
        f"[rs_trend] prev_d:{prev_d} pre_mkt:{pre_mkt} spread:{spread} "
        f"bull:{bull} bear:{bear} → {trend}"
    )
    return trend

def sort_symbols_based_on_rs(app_config, application_state, market_data):
    """
    §4  Ranking pipeline — sorts the watchlist by RS Spread, strongest first.

    Steps (per spec §4):
      1. Compute SinceOpen% for every symbol and the benchmark (QQQ).
      2. Drop any symbol where SinceOpen% can't be computed (missing/zero open).
      3. Compute RS Spread for each remaining symbol.
      4. Compute PrevD, PreMkt, Trend for each remaining symbol.
      5. Sort descending by RS Spread.

    Writes the ranked list to application_state['rs_ranking'] and returns it.

    Returns a list of dicts (strongest first), e.g.:
      [
        { 'symbol': 'NVDA', 'rs_spread': 1.23, 'since_open_pct': 2.1,
          'move_pct': 0.5, 'prev_d': 'Above', 'pre_mkt': 'Above', 'trend': 'Long' },
        ...
      ]
    Returns [] when QQQ data is unavailable.
    """
    logger.info(f"[sort_symbols_based_on_rs] started ..")
    qqq_df = market_data.dfs_map.get('QQQ')
    if qqq_df is None:
        logger.warning("[sort_symbols_based_on_rs] QQQ df not available — cannot rank")
        return []

    qqq_since_open = rs_since_open_pct(qqq_df)
    if qqq_since_open is None:
        logger.warning("[sort_symbols_based_on_rs] QQQ since-open% is None — cannot rank")
        return []

    ranked = []
    symbols = [s for s in app_config.get('symbols', []) if s != 'QQQ']

    for symbol in symbols:
        df = market_data.dfs_map.get(symbol)
        if df is None:
            logger.debug(f"[sort_symbols_based_on_rs] {symbol} — no df, skipping")
            continue

        # §4 step 2: drop symbols where since-open% can't be computed
        since_open = rs_since_open_pct(df)
        if since_open is None:
            logger.debug(f"[sort_symbols_based_on_rs] {symbol} — since_open_pct is None, skipping")
            continue

        levels = application_state.get('levels', {}).get(symbol, {})

        spread   = round(since_open - qqq_since_open, 4)
        move     = rs_move_pct(df)
        prev_d   = rs_prev_d(df, levels)
        pre_mkt  = rs_pre_mkt(df, levels)
        trend    = rs_trend(df, qqq_df, levels)

        ranked.append({
            'symbol':         symbol,
            'rs_spread':      spread,
            'since_open_pct': since_open,
            'move_pct':       move,
            'prev_d':         prev_d,
            'pre_mkt':        pre_mkt,
            'trend':          trend,
        })

    # §4 step 5: sort descending by RS Spread — strongest relative movers first
    ranked.sort(key=lambda x: x['rs_spread'], reverse=True)

    application_state['rs_ranking'] = ranked
    application_state['rs_ranked_symbols'] = [r['symbol'] for r in ranked]

    logger.info(
        f"[sort_symbols_based_on_rs] ranked {len(ranked)} symbols. "
        f"Top: {ranked[0]['symbol']} {ranked[0]['rs_spread']:+.4f}" if ranked else
        f"[sort_symbols_based_on_rs] no symbols ranked"
    )
    logger.info(f"[sort_symbols_based_on_rs] finished ..")
    return ranked
