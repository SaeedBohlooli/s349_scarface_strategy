"""
BNR Quality Helper — drop-in module (no side-effects)

Usage pattern:
    from bnr_quality_helper import (
        BnrCfg, BnrWeights, BreakoutCfg, FollowCfg, RetestCfg,
        good_breakout, has_follow_through, good_retest, bnr_score, evaluate_level
    )

You MUST pass "hooks" (tiny callables) for:
    - atr(df, i, period)
    - rolling_median_range(df, i, window)
    - avg_volume(df, i, window)
    - count_touches(df, level, i0, i1, tol)

This avoids importing your internal utilities and lets you keep your files untouched.
"""

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

# ── Small numerics ────────────────────────────────────────────────────────────
def _clamp01(x: float) -> float:
    return 0.0 if x < 0 else 1.0 if x > 1 else x

def _min1(x: float) -> float:
    return x if x < 1 else 1.0

def _dir_of(side: str) -> int:
    return 1 if side == "long" else -1

def _body_frac(candle) -> float:
    rng = max(1e-9, candle.high - candle.low)
    return abs(candle.close - candle.open) / rng

def _wick_frac(candle) -> float:
    rng = max(1e-9, candle.high - candle.low)
    upper = max(0.0, candle.high - max(candle.open, candle.close))
    lower = max(0.0, min(candle.open, candle.close) - candle.low)
    return (upper + lower) / rng

# ── Config dataclasses (keep defaults sane; override per-symbol as needed) ────
@dataclass
class BreakoutCfg:
    min_gap_atr: float = 0.05
    min_body_frac: float = 0.60
    range_median_window: int = 10
    min_range_mult_vs_median: float = 1.4
    volume_avg_window: int = 14
    min_vol_mult_vs_avg: float = 1.5
    max_wick_frac: float = 0.35
    max_extension_atr: float = 1.2  # beyond this -> retest-only

@dataclass
class FollowCfg:
    bars: int = 3
    min_ext_atr: float = 0.35
    allow_immediate_retest: bool = True
    skip_if_gap_atr: float = 1.0   # if breakout close >= this ATR and…
    skip_if_body_frac: float = 0.70  # …body >= this, treat breakout as follow-through

@dataclass
class RetestCfg:
    tol_atr_mult: float = 0.35
    min_tick: float = 0.01
    max_abs_cap: float = 0.40
    max_retest_body_frac: float = 0.35
    min_rejection_wick_frac: float = 0.35
    max_touches: int = 1
    chop_window_bars: int = 6
    compare_vs_breakout: bool = True
    max_vol_vs_breakout: float = 0.85
    max_scan_bars: int = 20

@dataclass
class BnrWeights:
    breakout: float = 0.35
    follow: float = 0.25
    retest: float = 0.25
    context: float = 0.15

from dataclasses import dataclass, field

@dataclass
class BnrCfg:
    atr_period: int = 14
    breakout: BreakoutCfg = field(default_factory=BreakoutCfg)
    follow: FollowCfg = field(default_factory=FollowCfg)
    retest: RetestCfg = field(default_factory=RetestCfg)
    score_trade_threshold: float = 0.70
    score_weights: BnrWeights = field(default_factory=BnrWeights)


# ── Function hooks signature (you provide) ────────────────────────────────────
@dataclass
class Hooks:
    atr: Callable[[Any, int, int], float]
    rolling_median_range: Callable[[Any, int, int], float]
    avg_volume: Callable[[Any, int, int], float]
    count_touches: Callable[[Any, float, int, int, float], int]

# ── Core evaluators ───────────────────────────────────────────────────────────
def good_breakout(df, level: float, side: str, i: int, cfg: BnrCfg, hooks: Hooks) -> Dict[str, Any]:
    c = df[i]
    rng = c.high - c.low
    if rng <= 0:
        return {"ok": False, "reason": "zero_range"}

    atr_now = hooks.atr(df, i, cfg.atr_period)
    gap_needed = cfg.breakout.min_gap_atr * atr_now
    gap_close = _dir_of(side) * (c.close - level)
    if gap_close < gap_needed:
        return {"ok": False, "reason": "no_close_beyond", "atr": atr_now}

    bfrac = _body_frac(c)
    if bfrac < cfg.breakout.min_body_frac:
        return {"ok": False, "reason": "weak_body", "atr": atr_now}

    med_rng = hooks.rolling_median_range(df, i, cfg.breakout.range_median_window)
    if med_rng <= 0:
        return {"ok": False, "reason": "no_median", "atr": atr_now}
    rng_mult = rng / med_rng
    if rng_mult < cfg.breakout.min_range_mult_vs_median:
        return {"ok": False, "reason": "small_range", "atr": atr_now}

    vavg = hooks.avg_volume(df, i, cfg.breakout.volume_avg_window)
    if vavg <= 0:
        return {"ok": False, "reason": "no_vol_avg", "atr": atr_now}
    vol_mult = (c.volume / vavg) if vavg else 0.0
    if vol_mult < cfg.breakout.min_vol_mult_vs_avg:
        return {"ok": False, "reason": "no_vol_surge", "atr": atr_now}

    wfrac = _wick_frac(c)
    if wfrac > cfg.breakout.max_wick_frac:
        return {"ok": False, "reason": "wicky", "atr": atr_now}

    gap_atr = gap_close / max(1e-9, atr_now)
    too_extended = gap_atr >= cfg.breakout.max_extension_atr
    qualify_no_follow = (gap_atr >= cfg.follow.skip_if_gap_atr) and (bfrac >= cfg.follow.skip_if_body_frac)

    return {
        "ok": True,
        "idx": i,
        "atr": atr_now,
        "features": {
            "gap_atr": gap_atr,
            "body_frac": bfrac,
            "range_mult": rng_mult,
            "vol_mult": vol_mult,
            "wick_frac": wfrac,
            "close_vs_level": gap_close,
        },
        "too_extended": too_extended,          # force retest-only
        "qualify_no_follow": qualify_no_follow # breakout itself counts as follow-through
    }

def has_follow_through(df, i_break: int, side: str, cfg: BnrCfg, hooks: Hooks) -> Dict[str, Any]:
    atr_now = hooks.atr(df, i_break, cfg.atr_period)
    need = cfg.follow.min_ext_atr * atr_now
    hi0 = df[i_break].high
    lo0 = df[i_break].low

    # look-ahead bars for plain extension
    for j in range(i_break + 1, min(i_break + 1 + cfg.follow.bars, len(df))):
        if side == "long" and df[j].high >= hi0 + need:
            return {"ok": True, "idx": j, "reason": "plain_extension", "atr": atr_now, "ext": df[j].high - hi0}
        if side == "short" and df[j].low <= lo0 - need:
            return {"ok": True, "idx": j, "reason": "plain_extension", "atr": atr_now, "ext": lo0 - df[j].low}

    return {"ok": False, "reason": "no_extension", "atr": atr_now}

def good_retest(df, level: float, side: str, i_start: int, cfg: BnrCfg, hooks: Hooks, breakout_vol: Optional[float] = None) -> Dict[str, Any]:
    max_scan = cfg.retest.max_scan_bars
    for i in range(i_start, min(i_start + max_scan, len(df))):
        c = df[i]
        a = hooks.atr(df, i, cfg.atr_period)
        tol = max(cfg.retest.min_tick, min(cfg.retest.max_abs_cap, cfg.retest.tol_atr_mult * a))

        # distance in the direction that matters
        dist = abs((c.low - level) if side == "long" else (c.high - level))
        if dist > tol:
            continue

        # small-body + rejection wick
        bfrac = _body_frac(c)
        if bfrac > cfg.retest.max_retest_body_frac:
            continue

        rng = max(1e-9, c.high - c.low)
        if side == "long":
            rejection = (c.low <= level) and ((c.close - c.low) / rng >= cfg.retest.min_rejection_wick_frac)
        else:
            rejection = (c.high >= level) and ((c.high - c.close) / rng >= cfg.retest.min_rejection_wick_frac)
        if not rejection:
            continue

        # lighter retest volume than breakout (absorption)
        if cfg.retest.compare_vs_breakout and breakout_vol is not None:
            if c.volume > breakout_vol * cfg.retest.max_vol_vs_breakout:
                continue

        # anti-chop
        touches = hooks.count_touches(df, level, max(0, i - cfg.retest.chop_window_bars), i, tol)
        if touches > cfg.retest.max_touches:
            continue

        return {"ok": True, "idx": i, "tol": tol, "dist": dist, "bf": bfrac, "atr": a, "reason": "clean_retest"}

    return {"ok": False, "reason": "no_clean_retest"}

def bnr_score(breakout: Dict[str, Any], follow: Dict[str, Any], retest: Dict[str, Any],
              ctx: Any, W: BnrWeights) -> Dict[str, Any]:
    b = breakout["features"]

    b_strength = _clamp01(
        0.40 * _min1(b["body_frac"] / 0.70) +
        0.25 * _min1(b["range_mult"] / 1.60) +
        0.25 * _min1(b["vol_mult"]  / 1.80) -
        0.10 * _min1(b["wick_frac"] / 0.50)
    )

    # follow-through strength
    if breakout.get("qualify_no_follow", False):
        f_strength = 1.0
    else:
        if not follow.get("ok", False):
            f_strength = 0.0
        else:
            atr_now = follow.get("atr", 1.0)
            ext = follow.get("ext", 0.0)
            f_strength = _clamp01(ext / (0.6 * max(1e-9, atr_now)))

    if retest.get("ok", False):
        fit = 0.6 * _clamp01(1 - (retest["dist"] / max(1e-9, retest["tol"]))) \
            + 0.4 * _clamp01((0.35 - retest["bf"]) / 0.35)
        r_strength = _clamp01(fit)
    else:
        r_strength = 0.0

    c_strength = _clamp01(
        0.4 * float(ctx.market_alignment) +
        0.3 * float(ctx.vwap_alignment)   +
        0.2 * float(ctx.time_window_ok)   +
        0.1 * float(ctx.rs_rw)
    )

    penalty = 0.0
    if breakout.get("too_extended", False) and not retest.get("ok", False):
        penalty = 0.20

    score = _clamp01(
        W.breakout * b_strength +
        W.follow   * f_strength +
        W.retest   * r_strength +
        W.context  * c_strength -
        penalty
    )

    gates = {
        "breakout_ok": breakout.get("ok", False),
        "context_ok":  bool(ctx.market_alignment and ctx.time_window_ok),
        "retest_ok":   retest.get("ok", False),
        "follow_ok":   follow.get("ok", False) or breakout.get("qualify_no_follow", False),
    }

    return {"score": score, "parts": {"b": b_strength, "f": f_strength, "r": r_strength, "c": c_strength}, "gates": gates}

def evaluate_level(df, level: float, side: str, i_break: int, cfg: BnrCfg, hooks: Hooks, ctx: Any) -> Dict[str, Any]:
    """
    Orchestrates one 5MH/5ML opportunity starting from a detected breakout bar index.
    Returns a dict with {"signal": "ENTER" | "NO_TRADE", "type": "...", "idx": int, "score": {...}}.
    """
    br = good_breakout(df, level, side, i_break, cfg, hooks)
    if not br["ok"]:
        return {"signal": "NO_TRADE", "reason": f"breakout_fail:{br.get('reason')}", "score": None}

    # Force retest-only if too extended
    if br["too_extended"]:
        fol = {"ok": False, "reason": "forced_retest_only", "atr": br["atr"]}
        ret = good_retest(df, level, side, i_break + 1, cfg, hooks, breakout_vol=df[i_break].volume)
        sc  = bnr_score(br, fol, ret, ctx, cfg.score_weights)
        if ret.get("ok", False) and sc["score"] >= cfg.score_trade_threshold and sc["gates"]["context_ok"]:
            return {"signal": "ENTER", "type": "retest_only", "idx": ret["idx"], "score": sc}
        return {"signal": "NO_TRADE", "reason": "extended_no_retest", "score": sc}

    # Non-extended: follow-through may be skipped if big/clean candle
    need_ft = not br["qualify_no_follow"]
    if need_ft:
        fol = has_follow_through(df, i_break, side, cfg, hooks)
    else:
        fol = {"ok": True, "reason": "breakout_satisfies_follow", "atr": br["atr"], "ext": br["features"]["close_vs_level"]}

    # Retest path = preferred trigger
    start_scan = (fol["idx"] + 1) if fol.get("ok", False) else (i_break + 1)
    ret = good_retest(df, level, side, start_scan, cfg, hooks, breakout_vol=df[i_break].volume)

    sc = bnr_score(br, fol, ret, ctx, cfg.score_weights)
    if ret.get("ok", False) and sc["score"] >= cfg.score_trade_threshold and sc["gates"]["context_ok"]:
        return {"signal": "ENTER", "type": "break_retest", "idx": ret["idx"], "score": sc}

    return {"signal": "NO_TRADE", "reason": "filters_not_met", "score": sc}
