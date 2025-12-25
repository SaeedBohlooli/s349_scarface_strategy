import logging

from trading_core.trading_ledger import TradingLedger

logger = logging.getLogger(__name__)

def add_miscs():
    add_to_drawing_objects_df(symbol=symbol, time_frame=time_frame,  object='dash', color='Blue', price_1=day_high, memo=f'PDH {day_high}', unique_id=f'{symbol}-{time_frame}-PDH' )

    add_to_drawing_objects_df(symbol=symbol, time_frame=time_frame,  object='dash', color='Blue', price_1=day_low, memo=f'PDL {day_low}' , unique_id=f'{symbol}-{time_frame}-LDH' )
    add_to_key_levels_df(symbol=symbol, time_frame=time_frame, key_level_name='PDH', price=day_high, memo=f'PDH {day_high}')
    add_to_key_levels_df(symbol=symbol, time_frame=time_frame, key_level_name='PDL', price=day_low, memo=f'PDH {day_high}')


    add_to_drawing_objects_df(symbol=symbol, time_frame=time_frame, object='dash', color='Red', price_1=low_for_pre_market, memo=f'PML {low_for_pre_market}', unique_id=f'{symbol}-{time_frame}-PML')
    add_to_drawing_objects_df(symbol=symbol, time_frame=time_frame, object='dash', color ='Red', price_1=high_for_pre_market, memo=f'PMH {high_for_pre_market}', unique_id=f'{symbol}-{time_frame}-PMH')
    add_to_key_levels_df(symbol, time_frame, 'PML', low_for_pre_market, f'PML {low_for_pre_market}')
    add_to_key_levels_df(symbol, time_frame, 'PMH', high_for_pre_market, f'PMH {high_for_pre_market}')


    add_to_drawing_objects_df(symbol=symbol, time_frame=time_frame, object='dot', color='Black', price_1=low_for_5_min, memo=f'5ML {low_for_5_min}', unique_id=f'{symbol}-{time_frame}-5ML')
    add_to_drawing_objects_df(symbol=symbol, time_frame=time_frame, object='dot', color ='Black', price_1=high_for_5_min, memo=f'5MH {high_for_5_min}', unique_id=f'{symbol}-{time_frame}-5MH')
    add_to_key_levels_df(symbol, time_frame, '5ML', low_for_5_min, f'5ML {low_for_5_min}')
    add_to_key_levels_df(symbol, time_frame, '5MH', high_for_5_min, f'5MH {high_for_5_min}')




# for replacement
             price = get_offseted_price('up', df['high'].iloc[-1])
             add_to_signlas(symbol, 'LEVEL_REPLACED', price, df['date'].iloc[-1], f'level is replaced. from: {level}, to: {next_level}')


            price = get_offseted_price('up', df['high'].iloc[-1])
            add_to_signlas(symbol, 'LEVEL_REPLACED', price,  df['date'].iloc[-1], f'level is replaced. from: {level}, to: {next_level}')



def add_buy_a_sell_entries_to_signals(app_config, application_state, buy_sell_case_results_list, symbol, market_data ):
    for buy_sell_case_result in buy_sell_case_results_list:
        df = market_data.get_symbol_df(symbol)

        logger.debug(f"add_buy_a_sell_entries_to_signals(), buy_sell_case_result: {buy_sell_case_result}")
        # case, can_buy, can_sell, details_map
        case = buy_sell_case_result[0]
        can_buy = buy_sell_case_result[1]
        can_sell = buy_sell_case_result[2]
        result_map = buy_sell_case_result[3]

        res_str = result_map.get('res_str')

        if case == 'case_1':
            price = df['high'].iloc[-1]
        elif case == 'case_2':
            price = df['low'].iloc[-1]
        else:
            price = df['close'].iloc[-1]


        if can_buy:
            # add_to_signlas(symbol, f"BUY_ENTRY_{case}", price, df['date'].iloc[-1], f"{case} - {res_str}")
            TradingLedger.add_to_list("signals", (f"BUY_ENTRY_{case}", price, df['date'].iloc[-1], f"{case} - {res_str}"))

        if can_sell:
            # add_to_signlas(symbol, f"SELL_ENTRY_{case}", price, df['date'].iloc[-1], f"{case} - {res_str}")
            TradingLedger.add_to_list("signals", (f"SELL_ENTRY_{case}", price, df['date'].iloc[-1], f"{case} - {res_str}"))


        # add_to_signlas(symbol,  f"SCREENING_{case}", offseted_price, df['date'].iloc[-1], f'{case} - {res_str}')  #
        price = get_offseted_price(app_config, application_state, symbol,'down', df['low'].iloc[-1])

        memo = f'{case} - {res_str}'
        data = {
            'symbol': symbol,
            'date': str(df['date'].iloc[-1]),
            'price': price,
            'memo': memo
        }

        # add_to_candle_info_df(symbol, date=df['date'].iloc[-1], price=price, memo=f'{case} - {res_str}')
        TradingLedger.add_to_dataframe("candle_info_df", data)

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
    up_offset_counter = application_state.setdefault('up_offset_counter', 0)
    down_offset_counter = application_state.setdefault('down_offset_counter', 0)

    if side == 'up':
        if add:
            up_offset_counter += 1
        up_offset_counter = 1 if up_offset_counter == 0 else up_offset_counter  # return 1 if is 0
        return up_offset_counter
    else:
        if add:
            down_offset_counter += 1
        down_offset_counter = 1 if down_offset_counter == 0 else down_offset_counter # return 1 if it is 0
        return down_offset_counter


def add_candle_info_df_to_signals():
    candle_info_df = TradingLedger.get_dataframe("candle_info_df")


    # combine memo for candles for each date ...
    if len(candle_info_df) == 0:
        return

    # logger.info(f"@ type(candle_info_df): {type(candle_info_df)}")

    df = candle_info_df
    df = df.drop_duplicates(subset=['symbol', 'date', 'price']) # no memo as it has jdon and it thrrwos errror
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
        date = row['date']
        symbol = row['symbol']
        date.strftime('%H:%M')  # just hh:mm from  2025-10-17 10:56:00-04:00
        price = row['price']
        memo = f"{row['memo']} <br> {date.strftime('%H:%M')}"  # adding date to the memo ...

        # add_to_signlas(symbol, "CANDLE_INFO", price, date, memo)  #
        TradingLedger.add_to_list("signals", ("CANDLE_INFO", price, date, memo))

    return


def convert_signals_to_hover_df():
    signals = TradingLedger.get_list("signals")

    if len(signals) == 0:
        return

    hovers_list = []
    for s in signals:
        logger.debug(f"convert_signals_to_hover_df, signal:{s}")
        symbol = s[0]
        event = s[1]
        price_1 = s[2]
        date_1 = s[3]
        memo = s[4]
        color = s[5]
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

        if color != '': # user wants his own clor
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
        TradingLedger.add_to_dataframe("hover_df",hovers_list)

        # FIX ME hover_df = hover_df.drop_duplicates(subset=['symbol','object','date_1'],keep='first')


