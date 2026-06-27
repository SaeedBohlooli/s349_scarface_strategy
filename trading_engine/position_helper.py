import logging

logger = logging.getLogger(__name__)
# ##
from trading_utils import ib_posttrade
from trading_core.file_manager import FileManager



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
                local_symbol = open_trade_info['local_symbol']
                order_ref = open_trade_info['order_ref']
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



def calculate_number_of_open_positions(application_state):
    """
    Count open trades across all symbols.
    A trade is considered open if available_quantity > 0.
    """
    open_trades = application_state.get("open_trades_dic", {})
    count = 0

    for symbol, trade in open_trades.items():
        if not trade:  # empty dict - > skip
            continue
        if trade.get("available_quantity", 0) > 0:
            count += 1
    return count


def set_stop_loss(application_state, user_request):
    stop_loss = user_request.get('stop_loss', 0)
    order_ref = user_request.get('order_ref', '')
    open_trades = application_state.get("open_trades_dic", {})
    for symbol, trade in open_trades.items():
        if not trade:  # empty dict - > skip
            continue
        if trade.get("available_quantity", 0) == 0:
            continue
        if trade.get("order_ref", "") == order_ref:
            logger.info(f"[set_stop_loss] order_ref: {order_ref}, new stop_loss: {stop_loss}")
            trade["stop_loss"] = stop_loss


