import logging
import numpy as np
import pandas as pd
from trading_utils import date_utils
from trading_core.trading_ledger import TradingLedger

logger = logging.getLogger(__name__)


def compute_symbol_scores(app_config, application_state, market_data):
    """
    Compute a composite score for each tradeable symbol relative to QQQ.
    Called once per engine loop cycle AFTER all symbols have indicators + levels,
    but BEFORE order decisions.

    Populates application_state['scoring'][symbol] with:
        - Individual factor scores (0-100)
        - composite_score (weighted 0-100)
        - rank (1 = strongest)
        - is_leader / is_laggard flags
    """
    scoring_config = app_config.get('scoring', {})
    if not scoring_config.get('enabled', False):
        return

    weights = scoring_config.get('weights', {})
    symbols = [s for s in app_config.get('symbols', []) if app_config.get('symbols_meta', {}).get(s, {}).get('can_trade', False)]

    if len(symbols) == 0:
        return

    rs_data = application_state.get('rs_data', {})
    raw_scores = {}

    for symbol in symbols:
        symbol_rs = rs_data.get(symbol)
        if symbol_rs is None:
            continue

        df = market_data.dfs_map.get(symbol)
        if df is None or len(df) < 2:
            continue

        scores = {}
        raw = {}

        # --- Factor 1: Intraday RS Delta ---
        rs_delta_ema = symbol_rs.get('rs_delta_ema', 0.0)
        raw['rs_delta_ema'] = rs_delta_ema

        # --- Factor 2: RS ROC ---
        rs_roc = symbol_rs.get('rs_roc', 0.0)
        raw['rs_roc'] = rs_roc

        # --- Factor 3: EMA Alignment ---
        price = df['close'].iloc[-1]
        ema_9 = df['ema_9'].iloc[-1] if 'ema_9' in df.columns else price
        ema_21 = df['ema_21'].iloc[-1] if 'ema_21' in df.columns else price
        raw['price'] = price
        raw['ema_9'] = ema_9
        raw['ema_21'] = ema_21

        # --- Factor 4: VWAP Position ---
        vwap = df['vwap'].iloc[-1] if 'vwap' in df.columns else price
        atr = df['atr_14'].iloc[-2] if 'atr_14' in df.columns and len(df) > 1 else 1.0
        raw['vwap'] = vwap
        raw['atr_14'] = atr

        # --- Factor 5: Level Distance (ATR-normalized) ---
        levels = application_state.get('levels', {}).get(symbol, {})
        five_mh = levels.get('5MH')
        five_ml = levels.get('5ML')
        if five_mh is not None and five_ml is not None and atr > 0:
            dist_to_long = abs(price - five_mh) / atr
            dist_to_short = abs(price - five_ml) / atr
            level_distance = min(dist_to_long, dist_to_short)
        else:
            level_distance = 99.0
        raw['level_distance'] = level_distance

        # --- Factor 6: Breakout Recency ---
        breakout_idxs = application_state.get('breakout_idx', {}).get(symbol, [])
        if breakout_idxs:
            most_recent_breakout = max(b['breakout_idx'] for b in breakout_idxs)
            breakout_recency = abs(most_recent_breakout)  # e.g., -2 means 2 bars ago
        else:
            breakout_recency = 99
        raw['breakout_recency'] = breakout_recency

        raw_scores[symbol] = raw

    if len(raw_scores) == 0:
        return

    # --- Normalize each factor across all symbols to 0-100 ---
    scored = {}
    for symbol, raw in raw_scores.items():
        scored[symbol] = {'raw': raw}

    # Collect raw values for normalization
    all_rs_delta = [r['rs_delta_ema'] for r in raw_scores.values()]
    all_rs_roc = [r['rs_roc'] for r in raw_scores.values()]
    all_level_dist = [r['level_distance'] for r in raw_scores.values()]
    all_breakout_rec = [r['breakout_recency'] for r in raw_scores.values()]

    for symbol, raw in raw_scores.items():
        s = scored[symbol]

        # RS Delta: higher = stronger (good for longs)
        s['rs_delta_score'] = _normalize_rank(raw['rs_delta_ema'], all_rs_delta, higher_is_better=True)

        # RS ROC: higher = stronger momentum
        s['rs_roc_score'] = _normalize_rank(raw['rs_roc'], all_rs_roc, higher_is_better=True)

        # EMA Alignment: price > ema9 > ema21 = 100 (bullish alignment)
        s['ema_alignment_score'] = _score_ema_alignment(raw['price'], raw['ema_9'], raw['ema_21'])

        # VWAP Position: distance above VWAP normalized by ATR
        s['vwap_position_score'] = _score_vwap_position(raw['price'], raw['vwap'], raw['atr_14'])

        # Level Distance: closer to level = better (inverted)
        s['level_distance_score'] = _normalize_rank(raw['level_distance'], all_level_dist, higher_is_better=False)

        # Breakout Recency: fewer bars ago = better (inverted)
        s['breakout_recency_score'] = _normalize_rank(raw['breakout_recency'], all_breakout_rec, higher_is_better=False)

        # Weighted composite
        composite = (
            weights.get('rs_delta', 0.25) * s['rs_delta_score'] +
            weights.get('rs_roc', 0.20) * s['rs_roc_score'] +
            weights.get('ema_alignment', 0.20) * s['ema_alignment_score'] +
            weights.get('vwap_position', 0.15) * s['vwap_position_score'] +
            weights.get('level_distance', 0.10) * s['level_distance_score'] +
            weights.get('breakout_recency', 0.10) * s['breakout_recency_score']
        )
        s['composite_score'] = round(composite, 2)

    # --- Rank by composite score ---
    ranked_symbols = sorted(scored.keys(), key=lambda sym: scored[sym]['composite_score'], reverse=True)
    for rank, symbol in enumerate(ranked_symbols, start=1):
        scored[symbol]['rank'] = rank

    # --- Determine leaders / laggards ---
    use_threshold = scoring_config.get('use_threshold', True)
    leader_threshold = scoring_config.get('leader_threshold', 60)
    laggard_threshold = scoring_config.get('laggard_threshold', 40)
    top_n = scoring_config.get('top_n', 3)

    for symbol in scored:
        if use_threshold:
            scored[symbol]['is_leader'] = scored[symbol]['composite_score'] >= leader_threshold
            scored[symbol]['is_laggard'] = scored[symbol]['composite_score'] <= laggard_threshold
        else:
            scored[symbol]['is_leader'] = scored[symbol]['rank'] <= top_n
            scored[symbol]['is_laggard'] = scored[symbol]['rank'] > (len(scored) - top_n)

    # --- Store in application_state ---
    application_state['scoring'] = scored

    # --- Log summary ---
    for symbol in ranked_symbols:
        s = scored[symbol]
        logger.info(
            f"SCORING | {symbol:6s} | composite: {s['composite_score']:5.1f} | rank: {s['rank']} | "
            f"leader: {s['is_leader']} | laggard: {s['is_laggard']} | "
            f"rs_d: {s['rs_delta_score']:.0f} rs_roc: {s['rs_roc_score']:.0f} "
            f"ema: {s['ema_alignment_score']:.0f} vwap: {s['vwap_position_score']:.0f} "
            f"lvl: {s['level_distance_score']:.0f} bkout: {s['breakout_recency_score']:.0f}"
        )

    # --- Append to TradingLedger for CSV persistence ---
    _append_to_scoring_df(application_state, scored)


def passes_scoring_gate(app_config, application_state, symbol, side):
    """
    Check if a symbol passes the scoring gate for the given trade side.
    side: 'long' or 'short'
      - long  -> symbol must be a leader (high score)
      - short -> symbol must be a laggard (low score)

    Returns: (passes: bool, reason: str)
    """
    scoring_config = app_config.get('scoring', {})

    if not scoring_config.get('enabled', False) or not scoring_config.get('gate_enabled', False):
        logger.info(f"SCORING GATE | {symbol} | {side} | SKIPPED (enabled={scoring_config.get('enabled')}, gate_enabled={scoring_config.get('gate_enabled')})")
        return True, ''

    scoring = application_state.get('scoring', {})
    symbol_score = scoring.get(symbol)

    if symbol_score is None:
        logger.info(f"SCORING GATE | {symbol} | {side} | PASS (no scoring data available)")
        return True, 'no scoring data available'

    composite = symbol_score.get('composite_score', 50)
    rank = symbol_score.get('rank', 0)
    is_leader = symbol_score.get('is_leader', False)
    is_laggard = symbol_score.get('is_laggard', False)

    raw = symbol_score.get('raw', {})
    logger.info(f"SCORING GATE | {symbol} | {side} | composite={composite}, rank={rank}, "
                f"is_leader={is_leader}, is_laggard={is_laggard} | "
                f"rs_d={symbol_score.get('rs_delta_score', '?'):.0f}, rs_roc={symbol_score.get('rs_roc_score', '?'):.0f}, "
                f"ema={symbol_score.get('ema_alignment_score', '?'):.0f}, vwap={symbol_score.get('vwap_position_score', '?'):.0f}, "
                f"lvl={symbol_score.get('level_distance_score', '?'):.0f}, bkout={symbol_score.get('breakout_recency_score', '?'):.0f}")

    if side == 'long':
        if is_leader:
            logger.info(f"SCORING GATE | {symbol} | {side} | PASS (leader, score={composite} >= {scoring_config.get('leader_threshold', 60)})")
            return True, ''
        reason = f'not a leader (score={composite}, rank={rank})'
        logger.info(f"SCORING GATE | {symbol} | {side} | FAIL ({reason})")
        return False, reason
    elif side == 'short':
        if is_laggard:
            logger.info(f"SCORING GATE | {symbol} | {side} | PASS (laggard, score={composite} <= {scoring_config.get('laggard_threshold', 40)})")
            return True, ''
        reason = f'not a laggard (score={composite}, rank={rank})'
        logger.info(f"SCORING GATE | {symbol} | {side} | FAIL ({reason})")
        return False, reason

    return True, ''


# ---- Internal helpers ----

def _normalize_rank(value, all_values, higher_is_better=True):
    """
    Normalize a value to 0-100 based on its percentile rank among all_values.
    """
    if len(all_values) <= 1:
        return 50.0

    sorted_vals = sorted(all_values)
    n = len(sorted_vals)

    # Find percentile position
    count_below = sum(1 for v in sorted_vals if v < value)
    count_equal = sum(1 for v in sorted_vals if v == value)

    # Average percentile for ties
    percentile = (count_below + count_equal / 2.0) / n * 100.0

    if not higher_is_better:
        percentile = 100.0 - percentile

    return round(percentile, 1)


def _score_ema_alignment(price, ema_9, ema_21):
    """
    Score EMA alignment on a 0-100 scale.
    100 = price > ema9 > ema21 (perfect bullish alignment)
    50  = partial alignment
    0   = price < ema9 < ema21 (perfect bearish alignment)
    """
    score = 50.0

    # Price vs EMA9
    if price > ema_9:
        score += 25.0
    elif price < ema_9:
        score -= 25.0

    # EMA9 vs EMA21
    if ema_9 > ema_21:
        score += 25.0
    elif ema_9 < ema_21:
        score -= 25.0

    return max(0.0, min(100.0, score))


def _score_vwap_position(price, vwap, atr):
    """
    Score price position relative to VWAP, normalized by ATR.
    Above VWAP = higher score, below = lower score.
    Clamped to 0-100.
    """
    if atr <= 0 or np.isnan(vwap):
        return 50.0

    distance_in_atr = (price - vwap) / atr
    # Map [-2 ATR, +2 ATR] to [0, 100]
    score = 50.0 + (distance_in_atr / 2.0) * 50.0
    return round(max(0.0, min(100.0, score)), 1)


def _append_to_scoring_df(application_state, scored):
    """Append current scoring snapshot to the TradingLedger for CSV persistence."""
    timestamp = str(date_utils.time_now())
    rows = []
    for symbol, s in scored.items():
        raw = s.get('raw', {})
        rows.append({
            'timestamp': timestamp,
            'symbol': symbol,
            'rs_delta_ema': raw.get('rs_delta_ema', 0),
            'rs_roc': raw.get('rs_roc', 0),
            'ema_9': raw.get('ema_9', 0),
            'ema_21': raw.get('ema_21', 0),
            'vwap': raw.get('vwap', 0),
            'atr_14': raw.get('atr_14', 0),
            'level_distance': raw.get('level_distance', 0),
            'breakout_recency': raw.get('breakout_recency', 0),
            'rs_delta_score': s.get('rs_delta_score', 0),
            'rs_roc_score': s.get('rs_roc_score', 0),
            'ema_alignment_score': s.get('ema_alignment_score', 0),
            'vwap_position_score': s.get('vwap_position_score', 0),
            'level_distance_score': s.get('level_distance_score', 0),
            'breakout_recency_score': s.get('breakout_recency_score', 0),
            'composite_score': s.get('composite_score', 0),
            'rank': s.get('rank', 0),
            'is_leader': s.get('is_leader', False),
            'is_laggard': s.get('is_laggard', False),
        })

    if rows:
        TradingLedger.add_to_dataframe("scoring_df", rows, buffer=True)
