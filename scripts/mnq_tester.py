import pandas as pd
from dataclasses import dataclass, field
from typing import List, Literal, Optional

Side = Literal["long", "short"]


@dataclass
class SetupConfig:
    name: str
    side: Side
    zone_low: float
    zone_high: float
    entry_trigger: float  # price level that must be reclaimed / lost to enter
    stop: float           # hard stop price
    tps: List[float]      # list of absolute TP levels (in price)
    max_trades_per_day: int = 1  # safety


@dataclass
class Position:
    side: Side
    entry_price: float
    size: int
    stop: float
    tps: List[float]
    setup_name: str
    opened_at: pd.Timestamp
    next_tp_index: int = 0  # index into tps list


MNQ_POINT_VALUE = 2.0  # $ per point per contract


# ====== CONFIGURE YOUR PLAYBOOK HERE ======
PLAYBOOK_SETUPS: List[SetupConfig] = [
    # Long Setup A: 25192–25196 zone
    SetupConfig(
        name="LONG_A_25192_25196",
        side="long",
        zone_low=25192.0,
        zone_high=25196.0,
        entry_trigger=25198.0,  # reclaim above zone
        stop=25186.0,
        tps=[25220.0, 25240.0, 25260.0, 25300.0],
        max_trades_per_day=2,
    ),
    # Long Setup B: Deep discount 25130–25135
    SetupConfig(
        name="LONG_B_DEEP_25130_25135",
        side="long",
        zone_low=25130.0,
        zone_high=25135.0,
        entry_trigger=25140.0,
        stop=25118.0,
        tps=[25175.0, 25220.0, 25240.0, 25260.0],
        max_trades_per_day=1,
    ),
    # Short Setup A: 25240–25260 zone
    SetupConfig(
        name="SHORT_A_25240_25260",
        side="short",
        zone_low=25240.0,
        zone_high=25260.0,
        entry_trigger=25240.0,  # close back below zone_low
        stop=25272.0,
        tps=[25220.0, 25192.0, 25175.0, 25130.0],
        max_trades_per_day=2,
    ),
]


def load_data(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp").reset_index(drop=True)
    return df


def price_touches_zone(row: pd.Series, setup: SetupConfig) -> bool:
    """
    Basic check: did this bar trade through the zone?
    """
    if setup.side == "long":
        # we want a dip INTO the zone or below
        return row["low"] <= setup.zone_low
    else:  # short
        # we want a spike INTO the zone or above
        return row["high"] >= setup.zone_high


def entry_confirmed(row: pd.Series, setup: SetupConfig) -> bool:
    """
    Simple confirmation for entry.

    Long: close must be ABOVE entry_trigger.
    Short: close must be BELOW entry_trigger.
    """
    if setup.side == "long":
        return row["close"] >= setup.entry_trigger
    else:
        return row["close"] <= setup.entry_trigger


def simulate_trades(df: pd.DataFrame) -> pd.DataFrame:
    open_position: Optional[Position] = None
    trades = []

    # track how many trades per day per setup
    trades_per_day = {}  # {(date, setup_name): count}

    for i, row in df.iterrows():
        ts = row["timestamp"]
        date_key = ts.date()

        # handle open position first
        if open_position is not None:
            # Check stop & TP intrabar
            high, low = row["high"], row["low"]
            pos = open_position

            stopped = False
            tp_hit = False
            exit_price = None
            exit_reason = None

            if pos.side == "long":
                # If both stop and TP in same bar, assume worst (stop first)
                if low <= pos.stop:
                    stopped = True
                    exit_price = pos.stop
                    exit_reason = "STOP"
                elif pos.next_tp_index < len(pos.tps) and high >= pos.tps[pos.next_tp_index]:
                    tp_hit = True
                    exit_price = pos.tps[pos.next_tp_index]
                    exit_reason = f"TP{pos.next_tp_index + 1}"
            else:  # short
                if high >= pos.stop:
                    stopped = True
                    exit_price = pos.stop
                    exit_reason = "STOP"
                elif pos.next_tp_index < len(pos.tps) and low <= pos.tps[pos.next_tp_index]:
                    tp_hit = True
                    exit_price = pos.tps[pos.next_tp_index]
                    exit_reason = f"TP{pos.next_tp_index + 1}"

            if stopped or tp_hit:
                points = (exit_price - pos.entry_price)
                if pos.side == "short":
                    points = -points
                pnl_dollars = points * MNQ_POINT_VALUE * pos.size

                trades.append(
                    {
                        "setup": pos.setup_name,
                        "side": pos.side,
                        "entry_time": pos.opened_at,
                        "entry_price": pos.entry_price,
                        "exit_time": ts,
                        "exit_price": exit_price,
                        "exit_reason": exit_reason,
                        "points": points,
                        "pnl_dollars": pnl_dollars,
                    }
                )

                if tp_hit and pos.next_tp_index + 1 < len(pos.tps):
                    # Move stop to breakeven after TP1, etc. (basic example)
                    pos.next_tp_index += 1
                    pos.entry_price = exit_price  # treat as scale out + trail to BE
                    pos.stop = exit_price  # BE stop
                    open_position = pos
                else:
                    open_position = None

        # if flat, look for new trades
        if open_position is None:
            for setup in PLAYBOOK_SETUPS:
                key = (date_key, setup.name)
                count = trades_per_day.get(key, 0)
                if count >= setup.max_trades_per_day:
                    continue

                if price_touches_zone(row, setup) and entry_confirmed(row, setup):
                    # open position
                    pos = Position(
                        side=setup.side,
                        entry_price=row["close"],
                        size=1,
                        stop=setup.stop,
                        tps=setup.tps.copy(),
                        setup_name=setup.name,
                        opened_at=ts,
                        next_tp_index=0,
                    )
                    open_position = pos
                    trades_per_day[key] = count + 1
                    break  # only one trade per bar

    trades_df = pd.DataFrame(trades)
    return trades_df


def main():
    data_path = "../../portfolios/ohlc/p250/"  # TODO: change path as needed
    df = load_data(data_path)
    trades_df = simulate_trades(df)

    if trades_df.empty:
        print("No trades generated.")
        return

    print(trades_df)
    print("\nSummary:")
    print(trades_df.groupby("setup")["pnl_dollars"].sum())
    print("\nTotal PnL:", trades_df["pnl_dollars"].sum())


if __name__ == "__main__":
    main()
