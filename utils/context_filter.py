"""
Standalone pre-trade context filter.

Usage:
    from context_filter import check_trade, LevelData

    result = check_trade(
        side="long",
        level=355.93,
        retest_candle_high=356.20,
        retest_candle_low=355.50,
        stop_loss=355.31,
        signal_time="2026-05-01 09:42:00",
        qqq=qqq_data,
        ticker=ticker_data,
        qqq_level_break_time="2026-05-01 09:35:00",  # optional — when QQQ broke its level
        vwap=353.96,
        ema9=355.78,
        ema20=353.83,
        ema50=351.72,
    )

    if result.allowed:
        # send market order
    else:
        print(result.block_reasons)

Blocking gates (in order):
    1. QQQ range position     — QQQ already extended in trade direction?
    2. Entry quality          — retest candle too far from level?
    3. Ticker timing vs QQQ   — ticker broke its level too long after QQQ? (optional gate)

Informational only (never block):
    - VWAP context and extension %
    - EMA stack direction
    - Price vs 9 EMA
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


def _parse_dt(value: Any) -> datetime:
    """Coerce market timestamps from ISO strings, datetime, or pandas/numpy scalars."""
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    if isinstance(value, datetime):
        return value
    import pandas as pd

    return pd.Timestamp(value).to_pydatetime()


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class LevelData:
    """Key levels + current price for one symbol. Maps directly to eval_ctx."""
    symbol: str
    price: float
    TDH: float
    TDL: float
    PDH: float
    PDL: float
    PMH: float
    PML: float
    five_MH: float  # 5MH
    five_ML: float  # 5ML


@dataclass
class FilterResult:
    # --- Decision ---
    allowed: bool
    trade_state: str  # ALLOWED | BLOCKED
    block_reasons: list = field(default_factory=list)
    watch_note: str = ""

    # --- QQQ context (always populated) ---
    qqq_location: str = ""  # NEAR_HOD | NEAR_LOD | MID_RANGE
    qqq_momentum: str = ""  # EXPANDING | STALLED
    qqq_phase: str = ""  # EARLY_IMPULSE | CONTINUATION | STRUCTURE

    # --- Entry quality (always populated) ---
    entry_quality: str = ""  # IDEAL | OK | LATE | CHASE
    late_factor: float = 0.0

    # --- Ticker timing vs QQQ (optional — None when qqq_level_break_time not provided) ---
    ticker_timing: Optional[str] = None  # LEADER | ALIGNED | LAGGING
    lag_minutes: Optional[float] = None  # positive = ticker lagged QQQ, negative = ticker led

    # --- EMA / VWAP (optional — None when not provided) ---
    vwap_context: Optional[str] = None  # ABOVE | BELOW | NEAR
    vwap_extension_pct: Optional[float] = None
    ema_stack: Optional[str] = None  # BULLISH | BEARISH | MIXED
    price_vs_ema9: Optional[str] = None  # ABOVE | BELOW | AT


# ---------------------------------------------------------------------------
# Thresholds — tune here without touching logic
# ---------------------------------------------------------------------------

QQQ_NEAR_HOD_THRESHOLD = 0.80  # top 20% of day range = near HOD
QQQ_NEAR_LOD_THRESHOLD = 0.20  # bottom 20% of day range = near LOD

EARLY_IMPULSE_MINUTES = 10  # first 10 min — 5MH/5ML still forming
CONTINUATION_MINUTES = 45

CHASE_THRESHOLD = 2.0  # late_factor > this = chase = block
LATE_THRESHOLD = 1.0
OK_THRESHOLD = 0.5

# Ticker timing thresholds (minutes after QQQ break)
LEADER_THRESHOLD = -1  # ticker broke >= 1 min BEFORE QQQ = leader
ALIGNED_THRESHOLD = 5  # ticker broke within 5 min of QQQ = aligned
LAGGING_BLOCK_THRESHOLD = 5  # ticker broke > 5 min AFTER QQQ = lagging = block

VWAP_NEAR_THRESHOLD = 0.003
VWAP_EXTENDED_THRESHOLD = 0.010

# QQQ momentum — how close to TDH/TDL counts as "actively making new extreme"
QQQ_EXPANDING_THRESHOLD = 0.001  # within 0.1% of TDH/TDL = EXPANDING


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _minutes_from_open(dt: datetime) -> int:
    market_open = dt.replace(hour=9, minute=30, second=0, microsecond=0)
    return max(0, int((dt - market_open).total_seconds() / 60))


def _qqq_range_position(qqq: LevelData) -> float:
    day_range = qqq.TDH - qqq.TDL
    if day_range <= 0:
        return 0.5
    return (qqq.price - qqq.TDL) / day_range


def _qqq_location(pos: float) -> str:
    if pos >= QQQ_NEAR_HOD_THRESHOLD:
        return "NEAR_HOD"
    if pos <= QQQ_NEAR_LOD_THRESHOLD:
        return "NEAR_LOD"
    return "MID_RANGE"


def _qqq_phase(minutes: int) -> str:
    if minutes <= EARLY_IMPULSE_MINUTES:
        return "EARLY_IMPULSE"
    if minutes <= CONTINUATION_MINUTES:
        return "CONTINUATION"
    return "STRUCTURE"


def _entry_quality(trigger_price: float, level: float, stop_loss: float) -> tuple[str, float]:
    structure_width = abs(level - stop_loss)
    if structure_width == 0:
        return "UNKNOWN", 0.0
    late_factor = round(abs(trigger_price - level) / structure_width, 2)
    if late_factor <= OK_THRESHOLD:
        return "IDEAL", late_factor
    if late_factor <= LATE_THRESHOLD:
        return "OK", late_factor
    if late_factor <= CHASE_THRESHOLD:
        return "LATE", late_factor
    return "CHASE", late_factor


def _qqq_momentum(qqq: LevelData, side: str) -> str:
    """
    EXPANDING — QQQ is right at its TDH (for longs) or TDL (for shorts),
                meaning it is actively making new highs/lows right now.
    STALLED   — QQQ is near the extreme but has pulled back from it,
                meaning the move has settled and momentum has faded.
    """
    if side == "long":
        dist_pct = (qqq.TDH - qqq.price) / qqq.TDH
        return "EXPANDING" if dist_pct <= QQQ_EXPANDING_THRESHOLD else "STALLED"
    else:
        dist_pct = (qqq.price - qqq.TDL) / qqq.TDL
        return "EXPANDING" if dist_pct <= QQQ_EXPANDING_THRESHOLD else "STALLED"


def _ticker_timing(lag_minutes: float, aligned_threshold: float) -> str:
    if lag_minutes <= LEADER_THRESHOLD:
        return "LEADER"
    if lag_minutes <= aligned_threshold:
        return "ALIGNED"
    return "LAGGING"


def _vwap_context(price: float, vwap: float) -> tuple[str, float]:
    pct = (price - vwap) / vwap
    if abs(pct) <= VWAP_NEAR_THRESHOLD:
        label = "NEAR"
    elif pct > 0:
        label = "ABOVE"
    else:
        label = "BELOW"
    return label, round(pct * 100, 2)


def _ema_stack(ema9: float, ema20: float, ema50: float) -> str:
    if ema9 > ema20 > ema50:
        return "BULLISH"
    if ema9 < ema20 < ema50:
        return "BEARISH"
    return "MIXED"


def _price_vs_ema9(price: float, ema9: float) -> str:
    if abs(price - ema9) / ema9 <= 0.001:
        return "AT"
    return "ABOVE" if price > ema9 else "BELOW"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def check_trade(
        side: str,  # "long" or "short"
        level: float,  # B&R level (5MH, 5ML, PDH, PDL)
        retest_candle_high: float,
        retest_candle_low: float,
        stop_loss: float,
        signal_time: Any,  # ISO str, datetime, or pandas/numpy timestamp
        qqq: LevelData,
        ticker: LevelData,
        qqq_level_break_time: Any | None = None,  # when QQQ broke its corresponding level
        vwap: Optional[float] = None,
        ema9: Optional[float] = None,
        ema20: Optional[float] = None,
        ema50: Optional[float] = None,
) -> FilterResult:
    side = side.lower()
    assert side in ("long", "short"), "side must be 'long' or 'short'"

    trigger_price = retest_candle_high if side == "long" else retest_candle_low

    signal_dt = _parse_dt(signal_time)
    minutes = _minutes_from_open(signal_dt)

    qqq_pos = _qqq_range_position(qqq)
    location = _qqq_location(qqq_pos)
    momentum = _qqq_momentum(qqq, side)
    phase = _qqq_phase(minutes)
    entry_qual, late_factor = _entry_quality(trigger_price, level, stop_loss)

    block_reasons = []

    # --- Gate 1: QQQ range position + momentum ---
    # Two cases to block:
    #   A. QQQ near extreme and STALLED — move is over, new signals are late
    #   B. QQQ near extreme and EXPANDING — momentum is live, BUT ticker must be aligned
    #      (Gate 3 handles alignment; Gate 1 only blocks the stalled case here)
    #
    # Skipped entirely during EARLY_IMPULSE — near HOD/LOD in first 10 min
    # means the first move is happening, not exhaustion.
    if phase != "EARLY_IMPULSE":
        if side == "long" and location == "NEAR_HOD" and momentum == "STALLED":
            block_reasons.append(
                f"QQQ near HOD ({qqq_pos:.0%} of day range) but momentum stalled "
                f"— QQQ not making new highs, avoid new longs"
            )
        if side == "short" and location == "NEAR_LOD" and momentum == "STALLED":
            block_reasons.append(
                f"QQQ near LOD ({qqq_pos:.0%} of day range) but momentum stalled "
                f"— QQQ not making new lows, avoid new shorts"
            )

    # --- Gate 2: Entry quality ---
    if entry_qual == "CHASE":
        block_reasons.append(
            f"Retest candle too far from level — "
            f"trigger {trigger_price} is {abs(trigger_price - level):.2f} from level {level}, "
            f"structure width {abs(level - stop_loss):.2f}, late_factor {late_factor}"
        )

    # --- Gate 3: Ticker timing vs QQQ (only if qqq_level_break_time provided) ---
    timing_label = None
    lag_mins = None

    if qqq_level_break_time is not None:
        qqq_break_dt = _parse_dt(qqq_level_break_time)
        lag_mins = round((signal_dt - qqq_break_dt).total_seconds() / 60, 1)
        lag_threshold = 3 if phase == "EARLY_IMPULSE" else LAGGING_BLOCK_THRESHOLD
        timing_label = _ticker_timing(lag_mins, lag_threshold)

        if timing_label == "LAGGING":
            block_reasons.append(
                f"{ticker.symbol} broke {lag_mins} min after QQQ "
                f"(threshold {lag_threshold} min in {phase}) — signal is too late"
            )

    allowed = len(block_reasons) == 0

    if allowed:
        trade_state = "ALLOWED"
    elif len(block_reasons) > 1:
        trade_state = "BLOCKED_MULTIPLE"
    elif (
            (side == "long" and momentum == "STALLED" and location == "NEAR_HOD") or
            (side == "short" and momentum == "STALLED" and location == "NEAR_LOD")
    ):
        trade_state = "BLOCKED_QQQ_STALLED"
    elif timing_label == "LAGGING":
        trade_state = "BLOCKED_LAGGING"
    elif entry_qual == "CHASE":
        trade_state = "BLOCKED_CHASE"
    else:
        trade_state = "BLOCKED"

    watch_note = _build_watch_note(side, location, momentum, entry_qual, timing_label, level) if not allowed else ""

    # --- Informational only ---
    vwap_ctx = vwap_ext_pct = None
    if vwap is not None:
        vwap_ctx, vwap_ext_pct = _vwap_context(ticker.price, vwap)

    ema_stack_label = None
    if ema9 is not None and ema20 is not None and ema50 is not None:
        ema_stack_label = _ema_stack(ema9, ema20, ema50)

    price_vs_9 = None
    if ema9 is not None:
        price_vs_9 = _price_vs_ema9(ticker.price, ema9)

    return FilterResult(
        allowed=allowed,
        trade_state=trade_state,
        block_reasons=block_reasons,
        watch_note=watch_note,
        qqq_location=location,
        qqq_momentum=momentum,
        qqq_phase=phase,
        entry_quality=entry_qual,
        late_factor=late_factor,
        ticker_timing=timing_label,
        lag_minutes=lag_mins,
        vwap_context=vwap_ctx,
        vwap_extension_pct=vwap_ext_pct,
        ema_stack=ema_stack_label,
        price_vs_ema9=price_vs_9,
    )


def _build_watch_note(
        side: str,
        qqq_location: str,
        qqq_momentum: str,
        entry_qual: str,
        timing_label: Optional[str],
        level: float,
) -> str:
    notes = []
    if entry_qual == "CHASE":
        notes.append(f"Retest candle too far from {level:.2f} — wait for a tighter retest")
    if side == "long" and qqq_location == "NEAR_HOD" and qqq_momentum == "STALLED":
        notes.append("QQQ stalled near HOD — wait for new QQQ leg up before taking longs")
    if side == "short" and qqq_location == "NEAR_LOD" and qqq_momentum == "STALLED":
        notes.append("QQQ stalled near LOD — wait for new QQQ leg down before taking shorts")
    if side == "long" and qqq_location == "NEAR_HOD" and qqq_momentum == "EXPANDING":
        notes.append("QQQ making new highs — ensure ticker is aligned, not lagging")
    if side == "short" and qqq_location == "NEAR_LOD" and qqq_momentum == "EXPANDING":
        notes.append("QQQ making new lows — ensure ticker is aligned, not lagging")
    if timing_label == "LAGGING":
        notes.append("Ticker broke level too late after QQQ — wait for next QQQ leg")
    return " | ".join(notes)

#############################################

# Implementation of this class
# from context_filter import check_trade, LevelData

#   qqq = LevelData(
#       symbol="QQQ",
#       price=eval_ctx["QQQ_price"],
#       TDH=eval_ctx["QQQ_TDH"],
#       TDL=eval_ctx["QQQ_TDL"],
#       PDH=eval_ctx["QQQ_PDH"],
#       PDL=eval_ctx["QQQ_PDL"],
#       PMH=eval_ctx["QQQ_PMH"],
#       PML=eval_ctx["QQQ_PML"],
#       five_MH=eval_ctx["QQQ_5MH"],
#       five_ML=eval_ctx["QQQ_5ML"],
#   )

#   ticker = LevelData(
#       symbol="NVDA",
#       price=eval_ctx["NVDA_price"],
#       TDH=eval_ctx["NVDA_TDH"],
#       TDL=eval_ctx["NVDA_TDL"],
#       PDH=eval_ctx["NVDA_PDH"],
#       PDL=eval_ctx["NVDA_PDL"],
#       PMH=eval_ctx["NVDA_PMH"],
#       PML=eval_ctx["NVDA_PML"],
#       five_MH=eval_ctx["NVDA_5MH"],
#       five_ML=eval_ctx["NVDA_5ML"],
#   )

#   result = check_trade(
#       side="short",
#       level=200.21,
#       retest_candle_high=200.40,
#       retest_candle_low=200.25,
#       stop_loss=201.00,
#       signal_time="2026-05-01 09:36:00",
#       qqq=qqq,
#       ticker=ticker,
#   )
