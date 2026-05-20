import logging

import pandas as pd

from trading_core.file_manager import FileManager
from trading_core.trading_ledger import TradingLedger
from trading_utils import json_utils
from trading_utils import constants
from trading_utils import date_utils

logger = logging.getLogger(__name__)


def add_buy_a_sell_entries_to_signals(app_config, application_state, buy_sell_case_results_list, symbol, market_data ):
    for buy_sell_case_result in buy_sell_case_results_list:
        df = market_data.dfs_map.get(symbol)

        logger.debug(f"add_buy_a_sell_entries_to_signals(), buy_sell_case_result: {buy_sell_case_result}")
        # case, can_buy, can_sell, details_map
        case = buy_sell_case_result[0]
        can_buy = buy_sell_case_result[1]
        can_sell = buy_sell_case_result[2]
        result_map = buy_sell_case_result[3]

        res_str = result_map.get('res_str')
        can_buy_cores = result_map.get('can_buy_cores')
        can_sell_cores = result_map.get('can_sell_cores')

        case_color = get_case_color(app_config, case)

        if case == 'case_1':
            price = df['high'].iloc[-1]
        elif case == 'case_2':
            price = df['low'].iloc[-1]
        else:
            price = df['close'].iloc[-1]


        if can_buy:
            # add_to_signlas(symbol, f"BUY_ENTRY_{case}", price, df['date'].iloc[-1], f"{case} - {res_str}")
            TradingLedger.add_to_list("signals", (symbol, f"BUY_ENTRY_{case}", price, df['date'].iloc[-1], f"{case} - {res_str}", case_color))
        elif can_buy_cores:
            TradingLedger.add_to_list("signals", (symbol, f"BUY_ENTRY_{case}", price, df['date'].iloc[-1], f"{case} - {res_str}", case_color))

        if can_sell:
            # add_to_signlas(symbol, f"SELL_ENTRY_{case}", price, df['date'].iloc[-1], f"{case} - {res_str}")
            TradingLedger.add_to_list("signals", (symbol, f"SELL_ENTRY_{case}", price, df['date'].iloc[-1], f"{case} - {res_str}", case_color))
        elif can_sell_cores:
            TradingLedger.add_to_list("signals", (symbol, f"SELL_ENTRY_{case}", price, df['date'].iloc[-1], f"{case} - {res_str}", case_color))


        # add_to_signlas(symbol,  f"SCREENING_{case}", offseted_price, df['date'].iloc[-1], f'{case} - {res_str}')  #
        price = get_offseted_price(app_config, application_state, symbol,'down', df['low'].iloc[-1])

        add_to_candle_info_df(symbol, date=df['date'].iloc[-1], price=price, memo=f'{case} - {res_str}')

    return


def get_offseted_price(app_config, application_state, symbol = None, side='up', price=1):
    offset_symbol = app_config['symbols_meta'][symbol]['chart_entry_offset']
    if side == 'up':
        price = price + get_offset_counter(application_state, side, add=True) * offset_symbol
    else:
        price = price - get_offset_counter(application_state, side, add=True) * offset_symbol
    return price

def get_offset_counter(application_state, side='up', add=True):
    # This is for to see what is the offset for the hover  for the cnalde.
    # resets in every candle ...
    up_offset_counter = application_state.get('up_offset_counter', 0)
    down_offset_counter = application_state.get('down_offset_counter', 0)

    if side == 'up':
        if add:
            up_offset_counter += 1
        up_offset_counter = 1 if up_offset_counter == 0 else up_offset_counter  # return 1 if is 0
        application_state['up_offset_counter'] = up_offset_counter

        return up_offset_counter
    else:
        if add:
            down_offset_counter += 1
        down_offset_counter = 1 if down_offset_counter == 0 else down_offset_counter # return 1 if it is 0
        application_state['down_offset_counter'] = down_offset_counter
        return down_offset_counter


def add_candle_info_df_to_signals():
    candle_info_df = TradingLedger.get_dataframe("candle_info_df")


    # combine memo for candles for each date ...
    if len(candle_info_df) == 0:
        return

    # logger.info(f"@ type(candle_info_df): {type(candle_info_df)}")

    df = candle_info_df

# AMZN	2025-12-31 16:06:00-05:00	230.41	case_2_1_async - res_case_2_1_async:<br>1:F,2:F,3:F,4:F,5:F,6:F,7:T,8:T,9:F,10:F,11:T .. set().set() <br>1:F,2:F,3:F,4:F,5:F,6:T,7:T,8:T,9:F,10:T,11:T .. set().set() <br>long_breakout: None, long_retest: None <br>short_breakout: None, short_retest: None <br>16:06
# AMZN	2025-12-31 16:06:00-05:00	230.41	case_4_1_async - res_case_4_1_async:<br>1:F,2:F,3:F,4:F,5:F,6:F,7:F,8:T,9:T,10:T .. set().set() <br>1:F,2:F,3:F,4:F,5:F,6:F,7:F,8:F,9:T,10:T .. set().set() <br>long_breakout: None, long_retest: None <br>short_breakout: None, short_retest: None <br>16:06
# AMZN	2025-12-31 16:06:00-05:00	230.41	case_3 - res_case_3:<br>1:F .. set().set() <br>1:F .. set().set() <br>long_breakout: None, long_retest: None <br>short_breakout: None, short_retest: None <br>16:06
# AMZN	2025-12-31 16:06:00-05:00	230.32	case_2_1_async - res_case_2_1_async:<br>1:F,2:F,3:F,4:F,5:F,6:F,7:T,8:T,9:F,10:F,11:T .. set().set() <br>1:F,2:F,3:F,4:F,5:F,6:T,7:T,8:T,9:F,10:T,11:T .. set().set() <br>long_breakout: None, long_retest: None <br>short_breakout: None, short_retest: None <br>16:06
# AMZN	2025-12-31 16:06:00-05:00	230.32	case_4_1_async - res_case_4_1_async:<br>1:F,2:F,3:F,4:F,5:F,6:F,7:F,8:T,9:T,10:T .. set().set() <br>1:F,2:F,3:F,4:F,5:F,6:F,7:F,8:F,9:T,10:T .. set().set() <br>long_breakout: None, long_retest: None <br>short_breakout: None, short_retest: None <br>16:06
# AMZN	2025-12-31 16:06:00-05:00	230.32	case_3 - res_case_3:<br>1:F .. set().set() <br>1:F .. set().set() <br>long_breakout: None, long_retest: None <br>short_breakout: None, short_retest: None <br>16:06

    # drop dups bases on symbol, date, memo  # price is not used as it can be different for the same candle info
    df = df.drop_duplicates(subset=['symbol', 'date', 'memo'], keep='last') # no memo as it has jdon and it thrrwos errror  # 'price'
    # df_grouped = (  # for example multiple retest on one candle
    #     df.groupby(['date', 'price'], as_index=False)
    #     .agg({'memo': lambda x: ' <br> '.join(x)})
    # )

    df_grouped = (
        df.groupby(['symbol', 'date'], as_index=False)
        .agg({
            'price': 'min', # we put candle info below the candles ...
            'memo': lambda x: '<br> ------------ <br> '.join(x)
        })
    )

    for index, row in df_grouped.iterrows():
        logger.debug(f"add_candle_info_df_to_signals, row:\n{row}")
        date = row['date']
        symbol = row['symbol']
        date.strftime('%H:%M')  # just hh:mm from  2025-10-17 10:56:00-04:00
        price = row['price']
        memo = f"{row['memo']} <br> {date.strftime('%H:%M')}"  # adding date to the memo ...

        # add_to_signlas(symbol, "CANDLE_INFO", price, date, memo)  #
        TradingLedger.add_to_list("signals", (symbol, "CANDLE_INFO", price, date, memo))

    return


def convert_signals_to_hover_df():
    signals = TradingLedger.get_list("signals")

    if len(signals) == 0:
        return

    hovers_list = []
    for s in signals:
        if len(s) < 5:
            logger.warning(f"@@@@@ convert_signals_to_hover_df, signal length less than 5, signal:{s}")

        logger.debug(f"convert_signals_to_hover_df, signal:{s}")
        symbol = s[0]
        event = s[1]
        price_1 = s[2]
        date_1 = s[3]
        memo = s[4]
        color = s[5] if len(s) > 5 else None

        if memo == '':
            memo = event
        if 'breakout' in event.lower():
            obj = event
            clr = 'crimson'
        elif 'retest' in event.lower():
            obj = event
            clr = 'Green'
        elif 'LEVEL_REPLACED' in event:
            obj = event
            clr = 'Black'
        elif 'CANDLE_TYPE' in event:
            obj = event
            clr = 'YELLOW'
        elif 'SCREENING_case_1' in event :  # this is for buy sell entry
            obj = event
            clr = 'Green'
        elif 'SCREENING_case_2' in event:  # this is for buy sell entry
            obj = event
            clr = 'Blue'
        elif 'SCREENING_case_3' in event:  # this is for buy sell entry
            obj = event
            clr = 'Blue'
        elif 'ENTRY_case_1' in event:  # this is for buy sell entry
            obj = event
            clr = 'Green'
        elif 'ENTRY_case_2' in event:  # this is for buy sell entry
            obj = event
            clr = 'Blue'
        elif 'ENTRY_case_3' in event:  # this is for buy sell entry
            obj = event
            clr = 'Blue'
        elif 'CANDLE_INFO' in event:  # this is for buy sell entry
            obj = event
            clr = 'Orange'
        elif 'ORDER_SENT' in event:  # this is for buy sell entry
            obj = event
            clr = 'Blue'
        elif 'STOP_LOSS_SENT' in event:
            obj = event
            clr = 'Red'
        elif 'TAKE_PROFIT_SENT' in event:
            obj = event
            clr = 'Green'
        else:
            obj = event
            clr = 'Orange'

        if color is not None: # user wants his own clor
            clr = color

        data = {
            'symbol': symbol,
            'time_frame': '1 min',
            'object': obj,
            'color': clr,
            'price_1': price_1,
            'date_1': date_1,
            'memo': f'{memo}',
            'unique_id': f'{symbol}--{obj}--{date_1}'
        }
        hovers_list.append(data)
    if len(hovers_list) > 0:
        # hover_df = pd.concat([hover_df, pd.DataFrame(hovers_list)], ignore_index=True)
        TradingLedger.add_to_dataframe("hover_df", hovers_list, drop_duplicates=True, subset_for_duplicate=['unique_id'] )
        # TradingLedger.clear_list("signals")
        # FIX ME hover_df = hover_df.drop_duplicates(subset=['symbol','object','date_1'],keep='first')




def mark_tolerance_to_the_level(app_config, application_state, symbol, level_name, market_data):
    level = application_state.get('levels',{}).get(symbol,{}).get(level_name, None)
    if level is None:
        logger.warning(f"level {level_name} not found for symbol {symbol}")
        return
    tolerance = market_data.data_store.get(symbol).get('dynamic_tolerance', {}).get('tolerance', 0)

    p1 = level - tolerance * app_config['symbols_meta'][symbol].get('retest_tolerance_multiplier', 1)
    p2 = level + tolerance * app_config['symbols_meta'][symbol].get('retest_tolerance_multiplier', 1)

    p1 = round(p1 ,2)
    p2 = round(p2 ,2)

    df = market_data.dfs_map.get(symbol)
    date = df['date'].iloc[-1]

    TradingLedger.add_to_list("signals", (symbol, f'{level_name}_SMALL_DOT', p1, date, f'tel: {p1}, l: {level} t: {tolerance} {date_utils.get_hhm_mm_of_last_record(df)}', 'yellow' ))

    TradingLedger.add_to_list("signals", (symbol, f'{level_name}_SMALL_DOT_1', p2, date, f'tel: {p2}, l: {level} t: {tolerance} {date_utils.get_hhm_mm_of_last_record(df)}' ,'yellow' ))

    return


def mark_atr_to_the_level(application_state, symbol, side, level_name, market_data):
    level = application_state.get('levels',{}).get(symbol,{}).get(level_name, None)
    if level is None:
        return
    df = market_data.dfs_map.get(symbol)

    date = df['date'].iloc[-1]
    atr =  df['atr_14'].iloc[-2]
    if side == 'up':
        p1 = round(level + atr, 2)
    else:
        p1 = round(level - atr, 2)

    TradingLedger.add_to_list("signals", (symbol, f'{level_name}_SMALL_DOT_2', p1, date, f'atr_14: p: {p1}, l: {level} atr: {round(atr,2)}  {date_utils.get_hhm_mm_of_last_record(df)}', 'red' ))

    return


def add_atr_to_candle_info(symbol, market_data):
    df = market_data.dfs_map.get(symbol)
    dynamic_tolerance = market_data.data_store.get(symbol).get('dynamic_tolerance', {}).get('tolerance', 0)

    add_to_candle_info_df(symbol, date=df['date'].iloc[-1], price=df['close'].iloc[-1], memo=f'{dynamic_tolerance}')

    return

def add_rs_relative_to_candle_info(symbol, intraday_rs_df, market_data):
    if symbol == 'QQQ':
        return
    df = market_data.dfs_map.get(symbol)
    rs_rel = round(intraday_rs_df['rs_rel'].iloc[-1], 2)
    rs_rel_ema = round(intraday_rs_df['rs_rel_ema'].iloc[-1], 2)
    add_to_candle_info_df(symbol, df['date'].iloc[-1], df['close'].iloc[-1], f"rs_rel: {rs_rel}, rs_rel_ema: {rs_rel_ema}" )

    return



def add_to_candle_info_df(symbol, date, price, memo):

    data = {
        'symbol': symbol,
        'date': date,
        'price': price,
        'memo': memo
    }
    # candle_info_df = pd.concat([candle_info_df, pd.DataFrame([data])])
    TradingLedger.add_to_dataframe("candle_info_df", data)

    return


def add_open_position_to_candle_info(application_state, symbol, market_data):
    df = market_data.dfs_map.get(symbol)

    candle_info_price = df['low'].iloc[-1]
    open_trade_info = application_state.get('open_trades_dic', {}).get(symbol)
    if open_trade_info:
        add_to_candle_info_df(symbol, df['date'].iloc[-1], candle_info_price, json_utils.polish_map_to_show_in_hover(open_trade_info))  # shoe open trade inc hart ...



def mark_close_levels(app_config, application_state, symbol, df):
    # df is used in the config file ...
    mode = application_state.get('mode', 'live')
    closeness_distance = eval(app_config['closeness_distance_for_chart'][mode])
    key_levels_list = [l for l in application_state.get('levels', {}).get(symbol, {}).values()]
    key_levels_list = sorted(key_levels_list)
    for i in range(len(key_levels_list) - 1):
        l1 = key_levels_list[i]
        l2 = key_levels_list[i + 1]
        diff = abs(l2 - l1)
        if diff < closeness_distance:
            memo = f"X, d: {round(diff, 2)} ,a: {round(closeness_distance, 2)}, {l1}, {l2}"
        else:
            memo = f"d: {round(diff, 2)} ,a: {round(closeness_distance, 2)}, {l1}, {l2}"
                            # symbol, line 1 , line 2, diff, memo
        # close_pairs.append((symbol, l1, l2, memo ))
        TradingLedger.add_to_list("close_levels", (symbol, l1, l2, memo ))


def detect_a_mark_market_gap(application_state, symbol, df):
    logger.info(f"[detect_a_mark_market_gap] symbol: {symbol}")
    df["trade_day"] = df["date"].dt.date
    unique_days = sorted(df["trade_day"].unique())
    today = unique_days[-1]
    yesterday = unique_days[-2] if len(unique_days) >= 2 else unique_days[-1]

    t = pd.Timestamp("09:30").time()
    res = df.loc[(df["trade_day"] == today) & (df["date"].dt.time == t), "open"]
    open_today_0930 = res.iloc[-1] if not res.empty else None

    t = pd.Timestamp("16:00").time()
    res = df.loc[(df["trade_day"] == yesterday) & (df["date"].dt.time == t), "close"]
    if res.empty:
        # no close for last day. This happnns only in the MNQ on Mnday. last day which is sunday doesn't have any close
        # so we consider the last record of yesterday as the close
        logger.warning(f"@ detect_a_mark_market_gap, no 16:00 close for yesterday {yesterday}, so we take the last record of that day as the close")
        close_yesterday_1600 = df.loc[df["trade_day"] == yesterday, "close"].iloc[-1]
    else:
        close_yesterday_1600 = res.iloc[-1]
    logger.info(f"[detect_a_mark_market_gap] {symbol}, open_today_0930: {open_today_0930} , close_yesterday_1600: {close_yesterday_1600}")
    if open_today_0930 is None or close_yesterday_1600 is None:
        logger.info(f"[detect_a_mark_market_gap] @, cannot detect market gap for {symbol}, open_today_0930: {open_today_0930}, close_yesterday_1600: {close_yesterday_1600}")
        return
    gap_size = round(open_today_0930 - close_yesterday_1600, 2)
    color = constants.COLOR_GREEN_TRANSPARENT if gap_size > 0 else constants.COLOR_RED_TRANSPARENT

    if open_today_0930 is not  None and close_yesterday_1600 is not None:
        add_to_drawing_objects_df(symbol=symbol, time_frame='1min', object='rect', color=color, date_1=f'{today} 09:00:00', price_1=close_yesterday_1600,
                                  date_2=f'{today} 09:30:00', price_2=open_today_0930, memo='Market Gap', unique_id=f'{symbol}--MARKET-GAP')
        application_state.setdefault('gaps', {}).setdefault(symbol, {}).update(
            {
            'date': str(df['date'].iloc[-1]),
            'open_today_0930': open_today_0930,
            'close_yesterday_1600': close_yesterday_1600,
            'gap_size': gap_size,
            'update_timestamp': str(date_utils.time_now()),
            }
        )
    return


def add_to_drawing_objects_df(symbol='TSLA', time_frame='1m', object='dash', color='Blue', date_1='', price_1=0, date_2='',price_2=0, memo = '', unique_id='' ):
    if price_1 != 0 and price_1 != -1:
        if unique_id == '':
            unique_id = f"{symbol}--{time_frame}--{price_1}"
        data = {
            'symbol':  symbol,
            'time_frame': time_frame.replace(' ', ''),
            'object': object,  #  ['solid', 'dot', 'dash', 'longdash', 'dashdot', 'longdashdot']
            'color': color,
            'date_1': date_1,
            'price_1': price_1,
            'date_2': date_2,
            'price_2': price_2,
            'memo': memo,
            'unique_id': unique_id
        }

        TradingLedger.add_to_dataframe("drawing_objects_df", data)

    return


def get_case_color(app_config, case):
    return app_config.get('cases', {}).get(case, {}).get('color', 'black')


def save_configs_in_chart_folder(app_config):
    file_name = f"{FileManager.dirs.charts}/config.yaml"
    FileManager.save_yaml(app_config, file_name)
    return

