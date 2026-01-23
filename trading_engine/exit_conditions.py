import logging
import traceback

from trading_core.trading_ledger import TradingLedger

logger = logging.getLogger(__name__)
import pandas as pd
from trading_core.file_manager import  FileManager


from trading_utils import date_utils
from trading_utils import json_utils
from trading_utils import ib_orders_async
from trading_utils import ib_positions_async
from trading_utils import number_utils
from trading_engine import notification_helper


async def check_for_stop_loss_and_take_profit(ib, app_config, application_state, market_data):
    symbols_need_to_be_removed = [] # we dont remove in the loop ..

    for symbol, open_trade_info in application_state.get('open_trades_dic', {}).items():
        logger.info(f"check_for_stop_loss_and_take_profit(), symbol {symbol}, open order unique_ru_number: {open_trade_info.get('unique_run_number')}" )

        # ###
        # stop loss
        # ###
        if not application_state.get('is_save_time'):
            logger.info(f"in check_for_stop_loss, {symbol} , {open_trade_info}" )
            #json_utils.print_map_pretty(open_trade_info)

        if open_trade_info.get('available_quantity', 0) == 0:
            logger.info(f"{symbol}, check_for_stop_loss_and_take_profit(), available_quantity: 0")
            continue

        symbol_df = market_data.dfs_map.get(symbol, pd.DataFrame())
        if symbol_df is None or len(symbol_df) == 0:
            logger.warning(f"@@@ check_for_stop_loss_and_take_profit(), symbol_df is None or len==0 , {symbol}")
            continue
        try:
            seconds_since_last_record = date_utils.seconds_passed_since_last_record(symbol_df)
            logger.info(f"@ check_for_stop_loss_and_take_profit(), symbol: {symbol}, seconds_since_last_record: {seconds_since_last_record}")
            if seconds_since_last_record > 65:
                logger.warning(f"@@@ check_for_stop_loss_and_take_profit(), {symbol}, seconds_since_last_record: {seconds_since_last_record}")
                logger.info(f"@@@ check_for_stop_loss_and_take_profit(), symbol_df[-1:]\n {symbol_df[-1:].to_markdown()}")
                continue
        except Exception as e:
            logger.error(f"@@@@@@ check_for_stop_loss_and_take_profit(), error in date check , {symbol}, e: {e}")

        # TODO check date to make sure that the data is not old
        entry_underlying_price = float(open_trade_info.get('entry_underlying_price', -1))  # used in config ...
        level_used_to_open = float(open_trade_info.get('level_used_to_open', -1)) # used in config ...
        avg_cost_for_1_contract = open_trade_info.get('avg_cost_for_1_contract', -1) # used in config
        right = application_state['open_trades_dic'][symbol].get('right', '') # used in config
        side = application_state['open_trades_dic'][symbol].get('side') # used in config
        level_used_to_open = application_state['open_trades_dic'][symbol]['level_used_to_open'] # used in config
        dynamic_tolerance = market_data.data_store.get(symbol,{}).get('dynamic_tolerance', {})
        tolerance_amount = dynamic_tolerance.get('tolerance', 0)  # used in config
        start_quantity = application_state.get('open_trades_dic', {}).get(symbol, {}).get('starting_quantity', 0) # used in config
        available_quantity = application_state.get('open_trades_dic', {}).get(symbol, {}).get('available_quantity', 0)  # used in config

        from trading_utils import ib_pricing_async
        contract_month = app_config.get('symbols_meta', {}).get(symbol,{}).get('contract_month')
        underlying_current_price = await ib_pricing_async.get_or_subscribe_symbol_price(ib, symbol, contract_month)
        if len(symbol_df) == 0:
            # it maybe first run, and we don't have it yet in the dic ...
            underlying_previous_candle_close = underlying_current_price
        else:
            underlying_previous_candle_close = symbol_df['close'].iloc[-2] # used in config

        expiry = application_state['open_trades_dic'][symbol]['expiry']
        strike = application_state['open_trades_dic'][symbol]['strike']
        right = application_state['open_trades_dic'][symbol]['right']
        if open_trade_info.get('position_type') == 'OPTION':
            current_bid, current_ask, current_last = await ib_pricing_async.get_or_subscribe_option_price(ib, symbol, expiry, strike,right)  # used in config
        else:
            current_bid, current_ask, current_last = await ib_pricing_async.get_or_subscribe_symbol_price(ib, symbol, contract_month)  # used in config
        # TODO handle Future ...
        if not number_utils.is_valid_price(current_bid) or not number_utils.is_valid_price(current_ask):
            logger.warning(f"@@@ check_for_stop_loss_and_take_profit(), symbol: {symbol}, current_bid or current_ask is invalid, current_bid: {current_bid}, current_ask: {current_ask}")
            continue

        # update app status ...
        if app_config['symbols_meta'][symbol]['contract_type'] == 'Equity':
            application_state['open_trades_dic'][symbol]['current_bid'] = current_bid
            application_state['open_trades_dic'][symbol]['current_ask'] = current_ask
            application_state['open_trades_dic'][symbol]['current_underlying_price'] = underlying_current_price
            application_state['open_trades_dic'][symbol]['current_value'] = round( current_ask * application_state['open_trades_dic'][symbol]['starting_quantity'] * 100 , 3)
            application_state['open_trades_dic'][symbol]['current_pnl'] = round(application_state['open_trades_dic'][symbol].get('current_value', 0) - application_state['open_trades_dic'][symbol].get('cost_for_trade', 0) , 2)
            avg_cost_for_1_contract = application_state['open_trades_dic'][symbol].get('avg_cost_for_1_contract', 1)
            if avg_cost_for_1_contract != 0: # not decide by 0
                application_state['open_trades_dic'][symbol]['current_roi'] = round(application_state['open_trades_dic'][symbol]['current_bid'] / avg_cost_for_1_contract - 1, 3)

        else: # it is future ...
            application_state['open_trades_dic'][symbol]['current_bid'] = current_bid
            application_state['open_trades_dic'][symbol]['current_ask'] = current_ask
            application_state['open_trades_dic'][symbol]['current_underlying_price'] = underlying_current_price
            application_state['open_trades_dic'][symbol]['current_value'] = underlying_current_price * 1 # TODO available...
            application_state['open_trades_dic'][symbol]['current_pnl'] = round(application_state['open_trades_dic'][symbol]['current_underlying_price'] - application_state['open_trades_dic'][symbol].get('entry_underlying_price', 0), 2)
            application_state['open_trades_dic'][symbol]['current_roi'] = round(application_state['open_trades_dic'][symbol]['current_underlying_price'] / application_state['open_trades_dic'][symbol].get('entry_underlying_price', 1) - 1, 3)


        logger.info(f"level_used_to_open: {level_used_to_open}, entry_underlying_price: {entry_underlying_price}, "
                    f"underlying_current_price:, {underlying_current_price}, underlying_previous_candle_close: {underlying_previous_candle_close} ,tolerance_amount: {tolerance_amount}")
        logger.info(f"current_bid: {current_bid}, current_ask: {current_ask}, avg_cost_for_1_contract: {avg_cost_for_1_contract}")

        stop_loss_condition = app_config.get('stop_losses').get(right,{}).get('stop_loss_condition', ' 1 == 2')
        stop_loss_condition_evaluated = eval(stop_loss_condition)

        logger.info(f"symbol {symbol}, stop_loss_condition: {stop_loss_condition}, stop_loss_condition_evaluated: {stop_loss_condition_evaluated}")

        if stop_loss_condition_evaluated:
            logger.warning(f"{symbol} SL condition met ...")

            order_ref = ib_orders_async.generate_order_ref(application_state.get('portfolio_id'), event='CLOSE', symbol=symbol, alias='SL', unique_run_number=application_state.get('unique_run_number'))
            con_id = open_trade_info.get('con_id')
            ib_positions_async.close_position_by_con_id(ib, con_id=con_id, order_ref=order_ref )
            # close_option_positions(option_positions_to_monitor, symbol=symbol, order_ref=order_ref)
            data = {
                'symbol': symbol,
                'right': application_state['open_trades_dic'][symbol]['right'],
                'strike':  application_state['open_trades_dic'][symbol]['strike'],
                'expiry': application_state['open_trades_dic'][symbol]['expiry'],
                'current_bid': current_bid,
                'current_ask': current_ask,
                'underlying_current_price': underlying_current_price,
                'available_quantity_b4': available_quantity,
                'sl_u_run_number': application_state.get('unique_run_number'),
                'stop_loss_condition': stop_loss_condition,
                'candle_date': str(symbol_df['date'].iloc[-1]),
                'open_u_run_number': '',
                'open_order_ref': '',
                'sl_order_ref': order_ref,
                'local_symbol': application_state['open_trades_dic'][symbol].get('local_symbol'),
                'con_id': application_state['open_trades_dic'][symbol].get('con_id'),
                }
            application_state['open_trades_dic'][symbol].setdefault('stop_loss', {})['s1'] = data # save it in the
            archive_open_trade_dic(application_state, symbol)
            application_state.setdefault('open_trades_dic', {})[symbol] = {}  #  TODO This need to be happened after we get required inf from dic...
            add_order_ref_to_application_state(application_state, open_order_ref=open_trade_info.get('order_ref'), close_order_ref=order_ref)

            # add_to_stop_loss_history_df(data)
            TradingLedger.add_to_dataframe('stop_loss_history_df', data)

            # add_to_signals(symbol, 'STOP_LOSS_SENT', underlying_current_price, df['date'].iloc[-1], f"STOP_LOSS  <BR> {json_utils.polish_map_to_show_in_hover(data)}")
            TradingLedger.add_to_list("signals",(symbol, 'STOP_LOSS_SENT', underlying_current_price, symbol_df['date'].iloc[-1], f"STOP_LOSS  <BR> {json_utils.polish_map_to_show_in_hover(data)}"))


            # send_email(event='stop_loss_sent', symbol=symbol, body=polish_map_to_show_in_hover(data))

            notification_helper.send_email(app_config, event='stop_loss_sent', symbol=symbol, body=json_utils.polish_map_to_show_in_hover(data))



        # ###
        # Take profit
        # ###
        for take_profit in app_config['take_profits']:
            logger.info(f"check_for_stop_loss_and_take_profit(), symbol {symbol}, take_profit: {take_profit}")
            if application_state['open_trades_dic'][symbol].get('available_quantity',0) == 0:
                logger.info(f"{symbol}, {take_profit}, check_for_stop_loss_and_take_profit(), available_quantity is 0 ")
                continue


            if application_state['open_trades_dic'][symbol].get('take_profits',{}).get(take_profit,None ) is not None:
                logger.info(f"{symbol}, TP already is executed ... {take_profit}")
                continue
            take_profit_condition = app_config['take_profits'][take_profit].get('condition', '1 == 2')
            close_quantity_percentage = app_config['take_profits'][take_profit].get('close_quantity_percentage', 0)

            take_profit_condition_evaluated = eval(take_profit_condition)


            if close_quantity_percentage == -1: # close all
                close_quantity = available_quantity
            else:
                close_quantity = round(start_quantity * close_quantity_percentage )
                close_quantity = 1 if close_quantity == 0 else close_quantity  # we want to make sure 0.4 * 1 will return 1.

            logger.info(f"available_quantity: {available_quantity}, close_quantity_percentage: {close_quantity_percentage}, close_quantity: {close_quantity}, start_quantity:{start_quantity}")
            logger.info(f"take_profit_condition: {take_profit_condition}, take_profit_condition_evaluated: {take_profit_condition_evaluated}")
            order_ref = ''
            if take_profit_condition_evaluated and available_quantity > 0 and close_quantity != 0 and close_quantity <= available_quantity :
                logger.info(f"Sending TP ...{take_profit}")
                if app_config['symbols_meta'][symbol]['contract_type'] == 'Equity':
                    # order_ref = get_order_ref('CLOSE', symbol, alias_for_ref=take_profit, unique_run_number=unique_run_number)
                    order_ref = ib_orders_async.generate_order_ref(application_state.get('portfolio_id'), event='CLOSE', symbol=symbol, alias=take_profit, unique_run_number=application_state.get('unique_run_number'))
                    con_id = open_trade_info.get('con_id')
                    # close_option_positions(option_positions_to_monitor, symbol=symbol, close_qty=close_quantity, order_ref=order_ref)
                    ib_positions_async.close_position_by_con_id(ib, con_id = con_id, qty_to_close=close_quantity, order_ref=order_ref )
                elif app_config['symbols_meta'][symbol]['contract_type'] == 'Future':
                    # order_ref = get_order_ref('CLOSE', symbol, alias_for_ref=take_profit, unique_run_number=unique_run_number)
                    order_ref = ib_orders_async.generate_order_ref(application_state.get('portfolio_id'), event='CLOSE', symbol=symbol, alias=take_profit, unique_run_number=application_state.get('unique_run_number'))

                    con_id = open_trade_info.get('con_id')
                    # close_future_positions(future_positions_to_monitor, symbol=symbol, close_qty=close_quantity, order_ref=order_ref )
                    ib_positions_async.close_position_by_con_id(ib, con_id=con_id, qty_to_close=close_quantity,order_ref=order_ref)

                else:
                    logger.warning(f"@@@@ TBD")

                application_state['open_trades_dic'][symbol]['available_quantity'] = available_quantity - close_quantity

                data = {
                    'status': 'SENT',
                    'available_quantity_b4' : available_quantity,
                    'close_quantity': close_quantity,
                    'candle_date': str(symbol_df['date'].iloc[-1]),
                    'tp_u_run_number': application_state.get('unique_run_number'),
                    'order_ref': order_ref,
                }
                application_state['open_trades_dic'][symbol].setdefault('take_profits', {})[take_profit] = data

                data = {
                    'symbol': symbol,
                    'right': application_state['open_trades_dic'][symbol].get('right'),
                    'strike': application_state['open_trades_dic'][symbol].get('strike'),
                    'expiry': application_state['open_trades_dic'][symbol].get('expiry'),
                    'current_bid': current_bid,
                    'current_ask': current_ask,
                    'underlying_current_price': underlying_current_price,
                    'available_quantity_b4': available_quantity,
                    'take_profit_case': take_profit,
                    'take_profit_condition': take_profit_condition,
                    'close_quantity': close_quantity,
                    'candle_date': str(symbol_df['date'].iloc[-1]),
                    'tp_u_run_number': application_state.get('unique_run_number'),
                    'order_ref': order_ref,
                    'local_symbol': application_state['open_trades_dic'][symbol].get('local_symbol'),
                    'con_id': application_state['open_trades_dic'][symbol].get('con_id'),
                }
                add_order_ref_to_application_state(application_state, open_order_ref=open_trade_info.get('order_ref'), close_order_ref=order_ref)
                # add_to_take_profit_history_df(data)
                TradingLedger.add_to_dataframe('take_profit_history_df', data)
                # add_to_signals(symbol, 'TAKE_PROFIT_SENT', underlying_current_price, df['date'].bloc[-1], f"TAKE-PROFIT-{take_profit} <BR>{polish_map_to_show_in_hover(data)}")
                TradingLedger.add_to_list("signals", (symbol, 'TAKE_PROFIT_SENT', underlying_current_price, symbol_df['date'].iloc[-1], f"TAKE-PROFIT-{take_profit} <BR>{json_utils.polish_map_to_show_in_hover(data)}"))
                # send_email(event='take_profit_sent', symbol=symbol, body=polish_map_to_show_in_hover(data))
                notification_helper.send_email(app_config, event='take_profit_sent', symbol=symbol, body=json_utils.polish_map_to_show_in_hover(data))
                increment_wins(application_state, symbol)
                # This is very import. There was a case that after t1 execution, t2 condition meet also
                # but the available_quantity was not updates. look at the for iterator. we are updating what we are iterating it ...
                # DO MOT DELETE THIS. we go out, and we will come back i next .... if break didn't work we need to use return ...
                break

            else:
                logger.warning(f"{symbol}, {take_profit} TP condition didn't meet ...  ")


        # check to clean up
        if application_state['open_trades_dic'].get(symbol, {}) != {} and application_state['open_trades_dic'][symbol].get('available_quantity', 0) == 0:
            logger.info(f"{symbol}, the available_quantity is zero, so we set empty dic for it")
            symbols_need_to_be_removed.append(symbol)

    for s in symbols_need_to_be_removed:
        archive_open_trade_dic(application_state, s)
        remove_symbol_from_open_trade_dic(application_state, s)

    return






def add_order_ref_to_application_state(application_state, open_order_ref='', close_order_ref=''):

    if open_order_ref != '' and close_order_ref == '': # this is for open order ...
        application_state.setdefault('open_close_refs_map', {})[open_order_ref] = []
    elif open_order_ref != '' and close_order_ref != '': # this is for close ...
        entry = {open_order_ref: close_order_ref}
        application_state.setdefault('open_close_refs_list', []).append(entry) # add to the list ...

        if  not application_state.get('open_close_refs_map', {}).get(open_order_ref): #  opn is not there,sso add it …
            application_state.setdefault('open_close_refs_map', {})[open_order_ref] = []

        application_state.get('open_close_refs_map', {}).get(open_order_ref).append(close_order_ref) # now add the close ...
    else:
        logger.info(f"@@@ add_order_ref_to_application_state, is not supported, open_order_ref: {open_order_ref}, close_order_ref: {close_order_ref}")
    data = {
        'open_order_ref': open_order_ref,
        'close_order_ref': close_order_ref,
        'ib_exec_id': ''
    }

    TradingLedger.add_to_dataframe('open_close_refs_df', data)
    return

def archive_open_trade_dic(application_state, symbol):
    FileManager.save_named_json(application_state, file_name=f"84-{application_state.get('unique_run_number')}-{symbol}.json",
                            dir='intermediate')
    return



def remove_symbol_from_open_trade_dic(application_state, symbol):
    application_state['open_trades_dic'].pop(symbol, None)
    return


def is_executed_take_profits(application_state, symbol, take_profit_list=[]): # used in config
    for tp in take_profit_list:
        if application_state.get('open_trades_dic',{}).get(symbol,{}).get('take_profits',{}).get(tp, {}) != {}: # it is there
            return True
    return False


def is_price_crossed_levels(application_state, side='down', symbol='', next_levels=['PDL'], current_price=-1, entry_underlying_price=-1):
    if next_levels is None:
        return False

    levels_map = application_state.get('levels', {}).get(symbol, {})
    for key in next_levels:
        next_level_price = levels_map.get(key, None)
        if next_level_price is None:
            continue  # skip missing levels

        # current_price > the next level AND the open price < next level , so we croessed the level
        if side == "up" and current_price >  next_level_price and entry_underlying_price < next_level_price:
            return True
        if side == "down" and current_price < next_level_price and entry_underlying_price > next_level_price:
            return True

    return False


def check_mark_revers_candles(application_state, symbol, take_profit_alias=None, market_data= None):
    # TODO remove try later ...
    try:
        df = market_data.dfs_map.get(symbol)
        logger.info(f"check_mark_revers_candles ... {symbol}")
        result = False
        tp_candle_date = application_state['open_trades_dic'].get(symbol,{}).get('take_profits',{}).get(take_profit_alias,{}).get('candle_date',None)
        logger.info(f"check_mark_revers_candles, {symbol}, tp_candle_date: {tp_candle_date}")

        if tp_candle_date == None:
           return False

        right = application_state['open_trades_dic'].get(symbol,{}).get('right', '')
        logger.info(f"check_mark_revers_candles, {symbol}, right: {right} ")


        if len(df) == 0:
            logger.warning(f"@@ len(df) is zero")
            return False
        logger.info(f"check_mark_revers_candles, {symbol}, df[-5:]\n {df[-5:].to_markdown()}")
        crossed_ema9 = False
        df["ema_9"] = df["close"].ewm(span=9, adjust=False).mean()
        if right == 'C':
            crossed_ema9 = True if df["close"].iloc[-1] < df["ema_9"].iloc[-1] else False
        else:
            crossed_ema9 = True if df["close"].iloc[-1] > df["ema_9"].iloc[-1] else False

        check_date = df['date'].iloc[-1]
        prev_close = df["close"].iloc[-2]

        target_date = pd.Timestamp(tp_candle_date)

        df = df[df["date"] >= target_date]
        logger.info(f"@@ check_mark_revers_candles, {symbol}, prev_close: {prev_close}. ")
        logger.info(f"check_mark_revers_candles, {symbol}, first two \n {df[:2].to_markdown()}")
        logger.info(f"check_mark_revers_candles, {symbol}, last two \n {df[-2:].to_markdown()}")

        df = df[:-2]                           # cut the latest row and the prev one as we comparing against it ...
        logger.info(f"@@ check_mark_revers_candles, {symbol}, candles we checking - after cutting last two (need to be verified)\n {df[-5:].to_markdown()}")
        if right == 'C':

            df["is_bearish"] = df["close"] < df["open"]
            lowest_bearish_low = df.loc[df["is_bearish"], "low"].min()

            result = prev_close < lowest_bearish_low and crossed_ema9
            logger.info(f"check_mark_revers_candles, {symbol}, lowest_bearish_low: {lowest_bearish_low}, prev_close: {prev_close}, {result}, \n{df[-5:].to_markdown()}")
            if result:
                logger.info(f"check_mark_revers_candles, {symbol}, The break happened. lowest_bearish_low: {lowest_bearish_low}, prev_close: {prev_close}")
                # add_to_signlas(symbol, 'LEVEL_REPLACED', df['close'].iloc[-1], check_date, f'Level is break out {check_date}<br> t_date: {target_date} <br>  lowest_bearish_low: {lowest_bearish_low} <br> prev_close: {prev_close}' )
                TradingLedger.add_to_list("signals",(symbol, 'LEVEL_REPLACED', df['close'].iloc[-1], check_date, f'Level is break out {check_date}<br> t_date: {target_date} <br>  lowest_bearish_low: {lowest_bearish_low} <br> prev_close: {prev_close}' ))

        else:

            df["is_bulish"] = df["close"] > df["open"]
            highest_bulish_high = df.loc[df["is_bulish"], "high"].max()

            result = prev_close > highest_bulish_high and crossed_ema9
            logger.info(f"check_mark_revers_candles, {symbol}, highest_bulish_high: {highest_bulish_high}, prev_close: {prev_close}, result: {result}, \n {df[-5:].to_markdown()}")
            if result:
                logger.info(f"check_mark_revers_candles, {symbol}, The break happened. highest_bulish_high: {highest_bulish_high}, prev_close: {prev_close}")
                # add_to_signlas(symbol, 'LEVEL_REPLACED', df['close'].iloc[-1], check_date, f'Level is break out {check_date}<br> t_date: {target_date} <br>  highest_bulish_high: {highest_bulish_high} <br> prev_close: {prev_close}' )
                TradingLedger.add_to_list("signals", (symbol, 'LEVEL_REPLACED', df['close'].iloc[-1], check_date, f'Level is break out {check_date}<br> t_date: {target_date} <br>  highest_bulish_high: {highest_bulish_high} <br> prev_close: {prev_close}' ))

        if result:
            logger.info(f"check_mark_revers_candles, The break happened. ")

        return result
    except Exception as e:
        logger.error(f"@@@ error: {e}")
        logger.error(traceback.format_exc())
    return result



def increment_wins(application_state, symbol):
    trading_date = application_state.get('trading_date', 'N/A')

    wins_by_day = application_state.setdefault('number_of_wins', {})
    wins_by_day[trading_date] = wins_by_day.get(trading_date, 0) + 1

    logger.info(f"increment_wins, {trading_date}, number_of_wins: {application_state['number_of_wins'][trading_date]}")
    return