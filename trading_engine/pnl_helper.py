import logging
logger = logging.getLogger(__name__)

from trading_core.trading_ledger import TradingLedger
from trading_utils import ib_posttrade
from trading_core.file_manager import FileManager

from trading_utils import date_utils

import pandas as pd


def populate_open_close_refs_pnl_df():

    # This method added ib_on_filla and on_commission to open_close_refs_pnl_df
    open_close_refs_df = TradingLedger.get_dataframe('open_close_refs_df')
    open_close_refs_pnl_df = TradingLedger.get_dataframe('open_close_refs_pnl_df')

    if len(open_close_refs_df) == 0:
        return open_close_refs_df

    ib_dir = FileManager.dirs.ib

    executions_df = ib_posttrade.load_ib_df(ib_dir, 'ib_on_fill_fill_df')
    if len(executions_df) == 0:
        logger.warning(f"populate_open_close_refs_pnl_df: No executions found in ib_on_fill_fill_df")
        return

    ib_commission_df = ib_posttrade.load_ib_df(ib_dir, 'ib_commission_df')
    if len(ib_commission_df) == 0:
        logger.warning(f"populate_open_close_refs_pnl_df: No commission found in ib_commission_df")
        return

    open_close_refs_df = open_close_refs_df[open_close_refs_df['close_order_ref'].notnull()]
    if len(open_close_refs_df) == 0:
        logger.warning(f"populate_open_close_refs_pnl_df: No close_order_ref found in open_close_refs_df")
        return open_close_refs_df

    merged_df = open_close_refs_df.merge(
        executions_df[["execution_orderRef", "execution_execId"]],
        how="left",
        left_on=["close_order_ref"],
        right_on=["execution_orderRef"],
        suffixes=("", "_df2"),  # <--- IMPORTANT # The second table ...
        indicator=True  # <-- enables _merge flag

    )

    missing = merged_df[merged_df["_merge"] == "left_only"].copy()
    if len(missing)> 0:
        logger.warning(f"@@@ populate_open_close_refs_pnl_df, missing (close_order_ref is not in IB yet.): \n {missing.to_markdown()}")
    merged_df = merged_df.drop(columns=["_merge"])

    merged_df = merged_df.drop(columns=["execution_orderRef" ,"ib_exec_id"])
    merged_df = merged_df.rename(columns={
        "execution_execId": "ib_exec_id",
    })
    logger.info(f"populate_open_close_refs_pnl_df, (open_close_refs_df joined with ib) merged_df:\n {merged_df.to_markdown()}")


    # Now we have ib_exec_id, now merge with commission to find the pnl ...

    merged_df = merged_df.merge(
        ib_commission_df[['commission','execId','realizedPNL', 'currency']],
        left_on=["ib_exec_id"],
        right_on=["execId"],
        suffixes=("", "_df2"),  # <--- IMPORTANT # The second table ...
        indicator=True  # <-- enables _merge flag

    )
    missing = merged_df[merged_df["_merge"] == "left_only"].copy()
    if len(missing)> 0:
        logger.warning(f"@@@ populate_open_close_refs_pnl_df, missing (no record in commission ):\n {missing.to_markdown()}")
    merged_df = merged_df.drop(columns=["_merge"])

    merged_df = merged_df.drop(columns=["execId" ])
    merged_df = merged_df.rename(columns={
        "realizedPNL": "realized_pnl",
    })
    logger.info(f"populate_open_close_refs_pnl_df, merged_df (open_close_refs_df + ib + commission):\n {merged_df.to_markdown()}")

    open_close_refs_pnl_df = pd.concat([open_close_refs_pnl_df, merged_df])

    open_close_refs_pnl_df = open_close_refs_pnl_df.drop_duplicates()

    TradingLedger.set_dataframe('open_close_refs_pnl_df', open_close_refs_pnl_df)

def populate_close_orders_in_capital_flow_df():
    # This methd pouplates close orders which are sent to the the cash_flow.

    open_close_refs_pnl_df = TradingLedger.get_dataframe('open_close_refs_pnl_df')

    if len(open_close_refs_pnl_df) == 0:
        return

    capital_flow_df = TradingLedger.get_dataframe('capital_flow_df')
    if len(capital_flow_df) ==0:
        return

    # The ones in open_close_refs_pnl_df which are not in capital_flow_df
    missing = open_close_refs_pnl_df[~open_close_refs_pnl_df["close_order_ref"].isin(capital_flow_df["close_order_ref"])]

    if missing.empty:
        return   # nothing to add

    logger.warning(f"[populate_close_orders_in_capital_flow_df] populate_close_orders_in_capital_flow_df, missing records need to be added : \n{missing.to_markdown()}")

    # Build rows to add. These are the one that are NOT in capital_flow_df
    rows_to_add_df = (
        # missing.rename(columns={"close_order_ref": "order_ref"})[["order_ref", "commission", "realized_pnl"]]
        missing[["close_order_ref", "commission", "realized_pnl"]]
    )

    rows_to_add_df['timestamp'] = str(date_utils.time_now())
    rows_to_add_df['trade_date'] = date_utils.get_yyyymmdd()
    rows_to_add_df['event'] = 'CLOSE_ORDER'
    rows_to_add_df['cash_flow'] = rows_to_add_df['realized_pnl']
    rows_to_add_df['memo'] = 'Added from IB logs'

    logger.warning(f"[populate_close_orders_in_capital_flow_df], final rows going to be added to capital_flow_df. \n{rows_to_add_df.to_markdown()}")
    # Append to df1
    capital_flow_df = pd.concat([capital_flow_df, rows_to_add_df], ignore_index=True)

    logger.warning(f"capital_flow_df: \n{capital_flow_df.to_markdown()}")
    capital_flow_df = capital_flow_df.drop_duplicates()
    TradingLedger.set_dataframe( 'capital_flow_df', capital_flow_df)
    return


def check_open_orders_in_capital_flow_df(application_state):
    # This method fndd order which are cloed and put a reverse record
    # in the capital_flow
    df = TradingLedger.get_dataframe('capital_flow_df').copy()

    df['is_closed'] = df['is_closed'].apply(
        lambda v: 'YES' if str(v).upper() == 'YES' else 'NO'
    )
    df['memo'] = df['memo'].fillna('')

    df = df.sort_values('timestamp').reset_index(drop=True)

    reverse_records = []
    for i, row in df.iterrows():  #TODO just find the ones we need
        if row['is_closed'] == 'YES' or row['event'] != 'OPEN_ORDER': # we looking for open orderas which are not closed.
            continue

        open_order_ref = row['open_order_ref']
        if not is_order_ref_open(application_state, open_order_ref): # this order_ref is not open anymore
            logger.info(f"check_open_orders_in_capital_flow_df, found closed open order_ref: {open_order_ref}, row: {row.to_dict()}")
            d = {
                'timestamp': str(date_utils.time_now()),
                'trade_date': date_utils.get_yyyymmdd(),
                'event': 'REVERSE_OPEN_ORDER',
                'cash_flow': row['cash_flow'] * -1,
                'symbol': row['symbol'],
                'memo': f'Reverse for {open_order_ref}  update: {date_utils.time_now_yyyy_mm_dd_hh_mm_ss()}'
            }
            reverse_records.append(d)
            df.at[i, "is_closed"] = 'YES'
            # coancat with exisintg memo
            df.at[i, "memo"] = f"{df.at[i, 'memo']} | Marked closed on {date_utils.time_now_yyyy_mm_dd_hh_mm_ss()}"


    logger.info(f"check_open_orders_in_capital_flow_df, df after marking closed:\n {df[-10:].to_markdown()}")

    if len(reverse_records) > 0:
        logger.info(f"check_open_orders_in_capital_flow_df, reverse_records: \n {'\n'.join(str(n) for n in reverse_records)}")  # TODO not working
        df = pd.concat([df, pd.DataFrame(reverse_records)])
    df = df.drop_duplicates()
    TradingLedger.set_dataframe("capital_flow_df", df)



def is_order_ref_open(application_state, open_order_ref):
    for symbol, open_trade_info in application_state.get('open_trades_dic', {}).items():
        if open_trade_info.get('order_ref', '') == open_order_ref and open_trade_info.get('available_quantity', 0) != 0:
            return True
    return False

def recompute_capital_flow_df(start_capital):
    # This method compuutes capital_before_event and capital_after_event
    df = TradingLedger.get_dataframe("capital_flow_df")
    if len(df) ==0:
        return

    df = df.sort_values('timestamp').reset_index(drop=True)

    #df = df.fillna(0)

    capital = start_capital

    for trade_date, group in df.groupby("trade_date"):
        capital = start_capital

        for i, row in group.iterrows():
            logger.debug(f"recompute_capital_flow_df , {i} ,{capital}, {row.to_dict()}")
            # 1) assign starting capital
            df.at[i, "capital_before_event"] = capital

            # 2) calculate cash flow based on event
            event = row["event"]

            trade_cost = float(row["trade_cost"])
            realized_pnl = float(row["realized_pnl"])
            commission = float(row["commission"])
            cash_flow = float(row["cash_flow"])

            # if event == "OPEN_ORDER":
            #     cash_flow = -(trade_cost + commission)
            #
            # elif event in ("CLOSE_ORDER", "CLODE_ORDER"):
            #     cash_flow = realized_pnl + trade_cost - commission
            #
            # else:
            #     cash_flow = 0.0


            # 3) update capital_after_event
            capital = round(capital + cash_flow, 2)
            df.at[i, "capital_after_event"] = capital

    df = df.drop_duplicates()
    TradingLedger.set_dataframe('capital_flow_df', df)
