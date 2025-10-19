import pandas as pd
import numpy as np

# --- Core ATR (Wilder's) ------------------------------------------------------
def compute_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Compute ATR using Wilder's smoothing.
    Expects columns: 'high','low','close'.
    Returns a pd.Series aligned with df.index.
    """
    high, low, close = df["high"].values, df["low"].values, df["close"].values
    prev_close = np.roll(close, 1)
    prev_close[0] = close[0]

    tr1 = high - low
    tr2 = np.abs(high - prev_close)
    tr3 = np.abs(low - prev_close)
    tr = np.maximum.reduce([tr1, tr2, tr3])

    atr = pd.Series(tr, index=df.index, dtype=float).ewm(alpha=1/period, adjust=False).mean()
    return atr

# --- Dynamic factor based on volatility regime --------------------------------
def dynamic_atr_tolerance_factor(atr_now: float, atr_baseline: float,
                                 low=0.18, normal=0.25, high=0.30,
                                 low_thr=0.8, high_thr=1.2) -> float:
    """
    Regime-based factor:
      - If current ATR < 0.8 * baseline -> low (tighter)
      - If 0.8–1.2x baseline          -> normal
      - If > 1.2x baseline            -> high (wider)
    """
    if atr_baseline <= 0:
        return normal
    r = atr_now / atr_baseline
    if r < low_thr:   return low
    if r > high_thr:  return high
    return normal

# --- Tolerance calc with floors/caps ------------------------------------------
def calc_retest_tolerance_amount(atr_now: float,
                                 atr_factor: float,
                                 min_tick: float = 0.01,
                                 hard_cap: float | None = None,
                                 round_digits: int = 4) -> float:
    """
    Convert ATR into a price tolerance with a tick floor and optional hard cap.
    """
    tol = max(atr_now * atr_factor, 2 * min_tick)
    if hard_cap is not None:
        tol = min(tol, hard_cap)
    return round(tol, round_digits)

# --- One-call helper: get dynamic ATR + tolerance -----------------------------
def get_dynamic_tolerance(df: pd.DataFrame,
                          level: float,
                          min_tick: float,
                          atr_period: int = 14,
                          atr_baseline_window: int = 390,  # ~1 RTH day of 1m bars; adjust per TF
                          factor_cfg: dict | None = None,
                          static_factor: float | None = None,
                          hard_cap: float | None = None) -> dict:
    """
    Returns dict with current ATR, baseline ATR, chosen factor, and tolerance.
    - If static_factor is provided, uses it.
    - Else uses regime-based dynamic factor.
    """
    if factor_cfg is None:
        factor_cfg = {"low": 0.18, "normal": 0.25, "high": 0.30,
                      "low_thr": 0.8, "high_thr": 1.2}

    atr_series = compute_atr(df, period=atr_period)
    atr_now = float(atr_series.iloc[-1])

    # Baseline from recent history (rolling mean of ATR)
    atr_baseline = float(atr_series.tail(atr_baseline_window).mean()) if len(atr_series) >= atr_baseline_window else float(atr_series.mean())

    # Pick factor
    if static_factor is not None:
        factor = static_factor
    else:
        factor = dynamic_atr_tolerance_factor(
            atr_now, atr_baseline,
            low=factor_cfg["low"], normal=factor_cfg["normal"], high=factor_cfg["high"],
            low_thr=factor_cfg["low_thr"], high_thr=factor_cfg["high_thr"]
        )

    tol = calc_retest_tolerance_amount(atr_now, factor, min_tick=min_tick, hard_cap=hard_cap)

    return {
        "level": level,
        "atr_now": round(atr_now, 6),
        "atr_baseline": round(atr_baseline, 6),
        "atr_factor": factor,
        "tolerance": tol
    }
# --- Example of how to use -----------------------------------------------------
"""
    Example Usage
    -------------
    # df has columns: date, open, high, low, close, volume (OHLCV)
    info = get_dynamic_tolerance(
        df=df, 
        level=403.30, 
        min_tick=0.01, 
        atr_period=14,
        atr_baseline_window=390,           # adjust for your timeframe
        # static_factor=0.25,              # uncomment to force static factor
        # hard_cap=0.50                    # optional cap (e.g., 50¢ max tolerance)
    )
    print(info)
    # -> {'level': 403.3, 'atr_now': 0.82, 'atr_baseline': 0.78, 'atr_factor': 0.25, 'tolerance': 0.205}

"""


"""
    Usage in our levels calculations
    level = info["level"]
    tol   = info["tolerance"]

    low   = float(df["low"].iloc[-1])      # retest bar
    close = float(df["close"].iloc[-1])

    if low >= level - tol:
        signal = "VALID_RETEST"
    elif low < level - tol and close >= level:
        signal = "RECLAIM_EVENT"
    else:
        signal = "FAILED_RETEST"

"""

"""
 Tick size considerations

    In US equities, the minimum tick size is typically $0.01.
    For Futures MES, MNQ tick values are 0.25 points; use tick in “price units” for tolerance.
"""