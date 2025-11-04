import os.path

import pandas as pd
import sys
sys.path.insert(0, f'../')
from utils import miscutils
from utils import email_util_ver_02
from utils import atr_tolerance_helper
from trading_utils import df_utils


def prepate_on_fill_df(on_fill_file_path=''):
    if not os.path.exists(on_fill_file_path):
        return pd.DataFrame()
    df = pd.read_csv(on_fill_file_path)

    df["signed_qty"] = df.apply(
        lambda x: x["execution_shares"] if x["execution_side"] == "BOT" else -x["execution_shares"], axis=1)

    # ensure proper datetime
    df["execution_time"] = pd.to_datetime(df["execution_time"])
    df = df.sort_values("execution_time")
    df["cum_position"] = df.groupby("contract_localSymbol")["signed_qty"].cumsum()

    df = df [['contract_symbol', 'contract_strike',  'contract_right', 'execution_shares', 'signed_qty', 'cum_position', 'execution_side',
              'execution_avgPrice', 'execution_price', 'execution_orderRef', 'execution_time', 'contract_localSymbol', 'execution_execId', 'commissionReport_realizedPNL']]

    return df


def create_ib_commission_df(file_path):
    if not os.path.exists(file_path):
        return pd.DataFrame()
    df = pd.read_csv(file_path)
    return df


import pandas as pd


def extract_trades_with_prices(df):
    trades = []
    for contract_localSymbol, group in df.groupby("contract_localSymbol"):
        group = group.sort_values("execution_time").reset_index(drop=True)
        if 'TSLL' in contract_localSymbol:
            print(f"group, {contract_localSymbol}, group: \n{group.to_markdown()} ")

        pos = 0
        open_price = 0
        total_cost = 0
        realized_pnl = 0
        open_time = None
        commission = 0.0
        execution_orderRef = ""
        for _, row in group.iterrows():
            qty = row["signed_qty"]
            price = row["execution_avgPrice"]
            contract_symbol = row["contract_symbol"]
            realized_pnl += row.get("realizedPNL", 0) or 0
            commission += row.get("commission", 0) or 0
            execution_orderRef += " # " + row["execution_orderRef"]

            # -- BUY (open or add)
            if qty > 0:
                if pos == 0:
                    open_time = row["execution_time"]
                    open_price = price
                    total_cost = qty * price
                    pos = qty
                else:
                    total_cost += qty * price
                    pos += qty
                    open_price = total_cost / pos  # weighted average

            # -- SELL (reduce or close)
            elif qty < 0:
                sell_qty = abs(qty)
                close_time = row["execution_time"]
                close_price = price

                # If it fully closes
                if sell_qty == pos:
                    trades.append({
                        "contract_localSymbol": contract_localSymbol,
                        "contract_symbol": contract_symbol,
                        "open_time": open_time,
                        "close_time": close_time,
                        "contracts": pos,
                        "open_price": round(open_price, 2),
                        "close_price": round(close_price, 2),
                        "realized_pnl": round(realized_pnl, 2),
                        "commission": round(commission, 2),
                        "execution_orderRef": execution_orderRef,
                    })
                    pos = 0
                    total_cost = 0
                    open_price = 0
                    realized_pnl = 0
                    open_time = None

                # If partial close
                elif sell_qty < pos:
                    pos -= sell_qty
                    total_cost = open_price * pos  # remaining cost

        # Still open?
        if pos > 0:
            trades.append({
                "contract_localSymbol": contract_localSymbol,
                "contract_symbol": contract_symbol,
                "open_time": open_time,
                "close_time": None,
                "contracts": pos,
                "open_price": round(open_price, 2),
                "close_price": None,
                "realized_pnl": None,
                "commission": None,
                "execution_orderRef": execution_orderRef,

            })

    trades_df = pd.DataFrame(trades).sort_values("open_time")

    return trades_df
def summarize_trades(df):
    trades = []

    for symbol, group in df.groupby("contract_localSymbol"):
        group = group.sort_values("execution_time").reset_index(drop=True)
        # print(f"group, {symbol}, group: \n{group.to_markdown()} ")

        open_time = None
        open_price = 0.0
        total_qty = 0
        realized_pnl = 0.0
        commission = 0.0
        last_price = None
        current_pos = 0
        execution_orderRef = ""

        for _, row in group.iterrows():
            prev_pos = current_pos
            current_pos = row["cum_position"]

            side = row["execution_side"]
            price = row["execution_avgPrice"]
            qty = row["execution_shares"]
            realized_pnl += row.get("realizedPNL", 0) or 0
            commission += row.get("commission", 0) or 0
            execution_orderRef += " # " + row["execution_orderRef"]

            # --- Opening new trade ---
            if prev_pos == 0 and current_pos != 0:
                open_time = row["execution_time"]
                open_price = price
                total_qty = current_pos
                realized_pnl = 0.0
                commission = 0.0

            # --- Updating while open ---
            if current_pos != 0:
                last_price = price

            # --- Closing trade completely ---
            if prev_pos != 0 and current_pos == 0:
                trades.append({
                    "contract_localSymbol": symbol,
                    "contract_symbol": row["contract_symbol"],
                    "open_time": open_time,
                    "close_time": row["execution_time"],
                    "contracts": abs(prev_pos),
                    "open_price": round(open_price, 2),
                    "close_price": round(last_price, 2),
                    "realized_pnl": round(realized_pnl, 2),
                    "commission": round(commission, 2),
                    "execution_orderRef": execution_orderRef,

                })
                # reset for next possible round-trip
                open_time = None
                open_price = 0.0
                total_qty = 0
                realized_pnl = 0.0
                commission = 0.0
                last_price = None

        # --- Still open at end of period ---
        if current_pos != 0:
            trades.append({
                "contract_localSymbol": symbol,
                "contract_symbol": group.iloc[0]["contract_symbol"],
                "open_time": open_time,
                "close_time": None,
                "contracts": abs(current_pos),
                "open_price": round(open_price, 2),
                "close_price": None,
                "realized_pnl": None,
                "commission": None,
                "execution_orderRef": execution_orderRef,

            })

    trades_df = pd.DataFrame(trades).sort_values("open_time").reset_index(drop=True)
    return trades_df

if __name__ == "__main__":

    portfolio_id = 'p250'
    portfolio_dir = f'../../portfolios/results/{portfolio_id}'

    flatten_on_fill_trade_df_file_path = f"{portfolio_dir}/92-flatten_on_fill_fill_df.csv"
    ib_commission_df_file_path = f"{portfolio_dir}/89-ib_commission_df.csv"

    executions_df = prepate_on_fill_df(on_fill_file_path=flatten_on_fill_trade_df_file_path)
    print(f"executions_df:\n{df_utils.capture_df_starting_hour_x_on_last_day(executions_df, 'execution_time', '00:00').to_markdown()}")

    commission_df = create_ib_commission_df(ib_commission_df_file_path)

    merged_df = pd.merge(executions_df, commission_df, left_on="execution_execId", right_on="execId", how="left")

    print(f"merged_df:\n{df_utils.capture_df_starting_hour_x_on_last_day(merged_df, 'execution_time', '00:00').to_markdown()}")

    # TODO debug ,,,
    merged_df = df_utils.capture_df_starting_hour_x_on_last_day(merged_df, 'execution_time', '00:00')

    trads_w_prices_df = extract_trades_with_prices(merged_df)
    print(f"trads_w_prices_df \n{trads_w_prices_df[0:].to_markdown()}")

    summarize_trades_df = summarize_trades(merged_df)
    print(f"summarize_trades_df:\n{df_utils.capture_df_starting_hour_x_on_last_day(summarize_trades_df, 'open_time', '00:00').to_markdown()}")



