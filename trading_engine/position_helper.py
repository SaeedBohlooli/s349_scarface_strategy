import logging

logger = logging.getLogger(__name__)
# ##
from trading_utils import ib_posttrade
from trading_core.file_manager import FileManager

# TODO Thisi s mistake
# TODO need to be filled out with ib_fill

def update_position_for_avg_cost(application_state):
    ib_positions = application_state.get("ib_positions", [])

    for symbol, open_trade_info in application_state.get('open_trades_dic', {}).items():
        if application_state.get('open_trades_dic', {}).get(symbol, {}) != {}: # There is open order ...
            if application_state.get('open_trades_dic', {}).get(symbol, {}).get('avg_cost', 0) == 0:  # only if not set before ...
                app_con_id = application_state['open_trades_dic'][symbol]['con_id']
                position_in_ib = next((p for p in ib_positions if p.get("contract_id") == app_con_id), None )
                if position_in_ib is None:
                    logger.warning(f"Could not find position for symbol {symbol} with con_id {app_con_id} in IB positions.")
                    continue

                logger.info(f"setting avg_cost in {position_in_ib['avg_cost']} for symbol {symbol} with con_id {app_con_id} in IB positions.")
                application_state['open_trades_dic'][symbol]['avg_cost'] = position_in_ib['avg_cost']

                application_state['open_trades_dic'][symbol]['cost_for_trade'] = round(position_in_ib['avg_cost'] * abs(position_in_ib['abs_qty']), 3)  # TODO could be from before ....
                application_state['open_trades_dic'][symbol]['avg_cost_for_1_position'] = round(position_in_ib['avg_cost'], 3)
                application_state['open_trades_dic'][symbol]['avg_cost_for_1_contract'] = round(position_in_ib['avg_cost'] / 100, 3)

    return


def update_position_for_entry_execution_price(application_state):
    ib_on_fill_fill_df = None

    for symbol, open_trade_info in application_state.get('open_trades_dic', {}).items():
        if application_state.get('open_trades_dic', {}).get(symbol, {}) != {}: # There is open order ...
            if application_state.get('open_trades_dic', {}).get(symbol, {}).get('entry_execution_price', 0) == 0:  # only if not set before ...

                if ib_on_fill_fill_df is None:
                    ib_on_fill_fill_df = ib_posttrade.load_ib_df(FileManager.dirs.ib, 'ib_on_fill_fill_df')

                if ib_on_fill_fill_df is None or ib_on_fill_fill_df.empty:
                    logger.info(f"Skipping {symbol} -- ib_on_fill_fill_df is None or empty")
                    continue
                local_symbol = application_state['open_trades_dic'][symbol]['local_symbol']
                order_ref = application_state['open_trades_dic'][symbol]['order_ref']
                execution_info_map = ib_posttrade.get_execution_map(ib_on_fill_fill_df,
                                                                    contract_localSymbol=local_symbol,
                                                                    execution_orderRef=order_ref)

                if execution_info_map:
                    execution_price = execution_info_map.get('execution_price', 0.0)
                    open_trade_info['entry_execution_price'] = execution_price
                    logger.info(f"Set entry_execution_price for {symbol} to {execution_price} based on execution info.")
                else:
                    logger.warning(f"No execution info found for {symbol} with local_symbol {local_symbol} and order_ref {order_ref}.")
                    continue


    return