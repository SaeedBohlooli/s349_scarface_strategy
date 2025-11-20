import pandas as pd
import time


def _to_num(df, cols, ndigits=None):
    """Safely convert columns to numeric, rounding if requested."""
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
            if ndigits is not None:
                df[c] = df[c].round(ndigits)
        else:
            df[c] = pd.NA
    return df


def enrich_with_pnl(app, df, fast=False):
    """Adds IB-streamed or fallback local PnL values."""
    df = df.copy()
    _to_num(df, ["Bid", "Ask", "Last", "Avg Price", "Position", "Multiplier"])

    df["Multiplier"] = df["Multiplier"].fillna(50)
    df["Position"] = df["Position"].fillna(0)
    df["Mid"] = df[["Bid", "Ask"]].mean(axis=1)
    df["MarketPrice"] = df["Mid"].fillna(df["Last"])

    pnl_map = {}
    conids = pd.to_numeric(df.get("ConId"), errors="coerce").dropna().astype(int).unique().tolist()

    for cid in conids:
        try:
            app.req_pnl_for_conid(cid)
        except Exception as e:
            print(f"⚠️ reqPnL failed for {cid}: {e}")
    time.sleep(5)

    if hasattr(app, "pnl_by_conid"):
        for k, v in app.pnl_by_conid.items():
            try:
                pnl_map[int(k)] = v.get("unrealized")
            except Exception:
                continue

    df["UnrealizedPnL_IB"] = df["ConId"].map(pnl_map)
    df["UnrealizedPnL_local"] = (df["MarketPrice"] - df["Avg Price"]) * df["Position"] * df["Multiplier"]
    df["UnrealizedPnL"] = df["UnrealizedPnL_IB"].fillna(df["UnrealizedPnL_local"])
    return df


def compute_exposures(df):
    """Compute Greek exposures and keep numeric 6-decimal precision."""
    df = df.copy()
    _to_num(df, ["Delta", "Gamma", "Vega", "Theta"], ndigits=6)
    df[["Delta", "Gamma", "Vega", "Theta"]] = df[["Delta", "Gamma", "Vega", "Theta"]].fillna(0.0)
    _to_num(df, ["Position", "Multiplier"])
    df["Multiplier"] = df["Multiplier"].fillna(50)
    df["Position"] = df["Position"].fillna(0)

    df["DeltaExposure"] = df["Position"] * df["Delta"] * df["Multiplier"]
    df["GammaExposure"] = df["Position"] * df["Gamma"] * df["Multiplier"]
    df["VegaExposure"] = df["Position"] * df["Vega"] * df["Multiplier"]
    df["ThetaExposure"] = df["Position"] * df["Theta"] * df["Multiplier"]

    # Round exposures numerically
    round_cols = ["DeltaExposure", "GammaExposure", "VegaExposure", "ThetaExposure"]
    for c in round_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").round(6)

    return df


def finalize_dataframe(df):
    """
    Custom sorting logic for portfolio output:
    1. Short Puts first (Right='P' and Position<0), sorted by Gamma↓ then Delta↓
    2. Long Puts second (Right='P' and Position>0), sorted by Gamma↓ then Delta↓
    3. Other option types (Calls etc.) follow as-is.
    """
    df = df.copy()

    # Ensure numeric and clean columns
    _to_num(df, ["Bid", "Ask", "Gamma", "Delta", "Position"])
    df["Spread"] = (df["Ask"] - df["Bid"]).round(4)

    # Drop zero positions
    if "Position" in df.columns:
        df = df[df["Position"] != 0].copy()

    # -------------------------------------
    # Assign custom sorting group priorities
    # -------------------------------------
    def _group_priority(row):
        right = row.get("Right")
        pos = row.get("Position", 0)
        if right == "P" and pos < 0:
            return 0  # Short Put
        elif right == "P" and pos > 0:
            return 1  # Long Put
        elif right == "C" and pos < 0:
            return 2  # Short Call
        elif right == "C" and pos > 0:
            return 3  # Long Call
        else:
            return 4  # Others fallback

    df["_group"] = df.apply(_group_priority, axis=1)

    # Sort by custom priority + Gamma ↓ + Delta ↓ + Expiration ↑ + Strike ↑
    df = df.sort_values(
        by=["_group", "Gamma", "Delta", "Expiration", "Strike"],
        ascending=[True, False, False, True, True],
        ignore_index=True
    )

    df.drop(columns=["_group"], inplace=True, errors="ignore")

    # Round Greeks & exposures numerically only (no strings)
    round_cols = [
        "Delta", "Gamma", "Vega", "Theta",
        "DeltaExposure", "GammaExposure", "VegaExposure", "ThetaExposure"
    ]
    for c in round_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").round(6)

    # -------------------------------------------------
    # Select and order only the desired output columns
    # -------------------------------------------------
    wanted_cols = [
        "Expiration", "Strike", "Position", "UnrealizedPnL",  
        "Avg Price", "Delta", "Gamma", "Vega", "Theta",
        "Bid", "Ask", "Spread", "ConId", 
        "DeltaExposure", "GammaExposure", "VegaExposure", "ThetaExposure",
        "MarketPrice", "UnrealizedPnL_IB" 
    ]

    existing_cols = [c for c in wanted_cols if c in df.columns]
    df = df[existing_cols]

    return df

