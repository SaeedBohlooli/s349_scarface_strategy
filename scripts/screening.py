import traceback
from tabulate import tabulate
from ib_insync import *
import pprint
import logging
import logging.handlers
import sys
import time
import argparse
import datetime
import numpy as np
import json
import pandas as pd
from pytz import timezone
import os
import yaml
from pandas.tseries.offsets import BDay


print(f"os.path.join('../'): {os.path.join('../')}")
sys.path.insert(0, f'../')
for dir_1 in os.listdir(os.path.join('../')):
    if (dir_1.startswith("a") or dir_1.startswith("u") ):
        sys.path.insert(0, f'../{dir_1}')
from utils import miscutils
from utils import Constants
from utils import email_util_ver_02

logger = miscutils.setup_logger(__name__, level=Constants.LOGGING_LEVEL)

portfolio_id = 'p250'
configs_folder = f'../scripts/configs'
config_file = f'{configs_folder}/app-config.yaml'

portfolio_dir = f'../portfolios/results/{portfolio_id}'
reports_dir = f'../portfolios/reports/{portfolio_id}'
log_dir = f'../portfolios/logs/{portfolio_id}'
detailed_log_dir = f'../portfolios/detailed-logs/{portfolio_id}'
charts_dir = f'../portfolios/charts/{portfolio_id}'
ohlc_dir = f'../portfolios/ohlc/{portfolio_id}'

os.makedirs(portfolio_dir, exist_ok=True)
os.makedirs(reports_dir, exist_ok=True)
os.makedirs(log_dir, exist_ok=True)
os.makedirs(detailed_log_dir, exist_ok=True)
os.makedirs(charts_dir, exist_ok=True)
os.makedirs(ohlc_dir, exist_ok=True)
# ####
# common ...
# ####
def load_app_config(portfolio_id):
    global app_config
    logger.warning(f"loading app_config ....")
    app_config = miscutils.load_config(f'{configs_folder}/config-{portfolio_id}.yaml')
    logger.info(f"loaded.")
    return app_config

def load_ib_config():
    logger.warning(f"loading app_config ....")
    app_config = miscutils.load_config(f'{configs_folder}/ib-config.yaml')
    logger.info(f"loaded.")
    return app_config


def get_previous_bday():
    prev_day = (pd.Timestamp.today() - BDay(1)).normalize()
    return prev_day

def create_ib_connection():
    connected = False
    ib = None
    while not connected:
        try:
            ib = IB()
            ib.connect(ib_config['ip'], ib_config['port'], clientId=ib_config['client_id'], timeout=0)
            connected = True
            logger.info(f"IB connected.")
        except Exception as e:
            # TODO needs better exception handling
            logger.error(f"error: {e}")
            import traceback

            print(traceback.format_exc())
            time.sleep(60)
    return ib

def get_historical_data(contract, historical_days, time_frame):

    bars = ib.reqHistoricalData(
        contract,
        endDateTime='',
        durationStr=historical_days,
        barSizeSetting=time_frame,
        whatToShow='TRADES',  # for BTC  'AGGTRADES',
        useRTH=False,
        formatDate=1)

    # Create a Pandas dataframe from the historical data
    df = util.df(bars)
    logger.info(f"get_historical_data, len(df): {len(df)}")

    if time_frame != '1 day':
         # df["date"]=df["date"].dt.tz_convert(None)
        if df["date"].dt.tz is not None:
            df["date"] = df["date"].dt.tz_convert(None)
            df = miscutils.convert_column_timezone(df, 'date', 'date', from_zone='UTC', to_zone='America/New_York')

    return df


# ####
# for apps
# ###
def get_market_data(symbol, time_frame ='1 day'):
    historical_days = app_config['historical_days']
    logger.info(f"symbol: {symbol}, time_frame: {time_frame} , historical_days: {historical_days}")
    contract = create_contract(symbol)

    df = get_historical_data(contract, historical_days, time_frame)
    time_frame_x = time_frame.replace(' ', '')
    df.to_csv(f"{ohlc_dir}/{symbol}-{time_frame_x}.csv", index= False)
    logger.info(f"in get_market_data: \n{df[-5:].to_markdown()}")
    return df

def create_contract(symbol):
    if symbol == 'MNQ':
        contract = Future('MNQ', app_config['symbols_meta']['MNQ']['contract_month'], 'CME')
    elif symbol == 'BTC':
        contract_btc = Contract()
        contract_btc.symbol = "BTC"
        contract_btc.secType = "CRYPTO"
        contract_btc.currency = "USD"
        contract_btc.exchange = "PAXOS"
        contract = contract_btc
    else:
        contract = Stock(symbol, 'SMART', 'USD')
    return contract

def save_ohlc_for_chart(df):
    logger.info(f"in generate_for_chart, symbol: {symbol}, len(df): {len(df)}")
    df = df[['date','open', 'high', 'low', 'close', 'volume']]
    file = f"{charts_dir}/{symbol}-{time_frame.replace(' ', '')}.csv"
    df.to_csv(file, index=False, mode='w')
    return

def calculate_PDL_PDH(df):
    global support_resistance_map
    global key_levels_df

    df = df[['date','open','close', 'high', 'low', 'volume']]
    # filter to that day between 9:30–16:00

    unique_days = sorted(df['date'].dt.normalize().unique())

    if len(unique_days) < 2:
        raise ValueError("Not enough days in DataFrame to get previous day's data")

    # --- Select the previous day ---
    prev_day = unique_days[-2]

    # --- Filter to that day and RTH time window (09:30–16:00) ---
    mask_day = df['date'].dt.normalize() == prev_day
    mask_time = df['date'].dt.time.between(pd.to_datetime("09:30").time(),
                                           pd.to_datetime("16:00").time())

    df_rth = df[mask_day & mask_time]

    # --- Compute high and low ---
    day_high = df_rth["high"].max()
    day_low = df_rth["low"].min()

    logger.info(f"Previous weekday RTH High: {day_high}")
    logger.info(f"Previous weekday RTH Low: {day_low}" )

    add_to_drawing_objects_df(symbol=symbol, time_frame=time_frame,  object='dash', color='Blue', price_1=day_high, memo=f'PDH {day_high}', unique_id=f'{symbol}-{time_frame}-PDH' )
    add_to_drawing_objects_df(symbol=symbol, time_frame=time_frame,  object='dash', color='Blue', price_1=day_low, memo=f'PDL {day_low}' , unique_id=f'{symbol}-{time_frame}-LDH' )
    add_to_key_levels_df(symbol=symbol, time_frame=time_frame, key_level_name='PDH', price=day_high, memo=f'PDH {day_high}')
    add_to_key_levels_df(symbol=symbol, time_frame=time_frame, key_level_name='PDL', price=day_low, memo=f'PDH {day_high}')
    return


def  add_to_key_levels_df(symbol, time_frame, key_level_name, price, memo='', unique_id=''):
    global key_levels_df
    if price> 0:
        if unique_id == '':
            unique_id = f'{symbol}--{time_frame}--{key_level_name}'
        data = {'symbol': symbol , 'time_frame': time_frame, 'key_level': key_level_name, 'price': price, 'memo' : memo, 'unique_id': unique_id}
        key_levels_df = pd.concat([key_levels_df, pd.DataFrame([data])])
        key_levels_df = key_levels_df.drop_duplicates(subset=['unique_id'], keep='last') # TODO chage to unique_id later ...
    return key_levels_df

def add_to_drawing_objects_df(symbol='TSLA', time_frame='1m', object='dash', color='Blue', date_1='', price_1=0, date_2='',price_2=0, memo = '', unique_id='' ):
    global drawing_objects_df
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
        drawing_objects_df = pd.concat([drawing_objects_df, pd.DataFrame([data])], ignore_index=True)


def is_between(now=None, start_str="9:25", end_str="10:30"):
    if now is None:
        now = datetime.datetime.now().time()

    # parse strings into time objects
    start = datetime.datetime.strptime(start_str, "%H:%M").time()
    end = datetime.datetime.strptime(end_str, "%H:%M").time()

    return start <= now <= end
# def write_support_resitance_for_t_min_1_report():
#     file_path = os.path.join(charts_dir, 'support_resistance_1min_previous_day.json')
#
#     logger.warning(f"support_resistance_map:\n{pprint.pformat(support_resistance_map)}")
#
#     with open(file_path, 'w') as f:
#         logger.info(f"saving at file_path: {file_path}")
#         json.dump(support_resistance_map, f, indent=4)
#         logger.info(f"saving done. ")

def sleep_enough():
    run_spend_time = round(end_time - start_time, 2)
    if is_between():
        logger.warning(f'{j}) run_spend_time: {run_spend_time} seconds')
    else:
        run_should_take = app_config['run_should_take_seconds']
        need_sleep_seconds = 0
        if run_spend_time < run_should_take:
            need_sleep_seconds = run_should_take - run_spend_time
        logger.warning(f'{j}) run_spend_time: {run_spend_time} seconds, run_should_take: {run_should_take}')
        time.sleep(need_sleep_seconds)
    return


def find_session_high_and_low(df, start="09:30", end="09:35", wait_until_end_of_period=True):
    """
    Return the high between start and end time for the current day.
    Only calculates if the latest candle is past end time.
    """
    df = df.copy()
    # ensure datetime
    df['date'] = pd.to_datetime(df['date'])

    # get current day from latest row
    current_day = df['date'].dt.date.max()

    # check if we passed the end time
    latest_time = df['date'].max().time()
    end_time = pd.to_datetime(end).time()
    start_time = pd.to_datetime(start).time()
#  (df['date'].dt.date == current_day) &
    if latest_time >= end_time or not wait_until_end_of_period:
        mask = (
                (df['date'].dt.date == current_day) &
                (df['date'].dt.time >= start_time) &
                (df['date'].dt.time <= end_time)
        )
        return df.loc[mask, 'low'].min(), df.loc[mask, 'high'].max()
        #return df.loc[mask, 'high'][-1], df.loc[mask, 'low'][-1]
    else:
        return -1, -1  # not yet past end time



def drop_dupplicates(file_path, unique_column=None, keep='last'):
    # Drop dupplicaes
    if os.path.exists(file_path):
        df = pd.read_csv(file_path)
        if unique_column is None:
            df = df.drop_duplicates(keep=f'{keep}')
        else: # has fields ...
            df = df.drop_duplicates(subset=[f'{unique_column}'], keep=f'{keep}')
        df.to_csv(file_path, index=False, mode='w')
    return
def save_df_to_csv_a_tabular(df=None, file_name='', mode='w', dir=''):
    if len(df) > 0:
        file = f'{dir}/{file_name}'
        if mode == 'w':
            header = True
        else:
            if os.path.exists(file):
                header = False
            else:
                header = True
        df.to_csv(file, mode=mode, index=False, header=header)
        drop_dupplicates(file, unique_column='unique_id')  # 'event'
        write_file_in_tabulate(src_file_path=file)
    return

def write_file_in_tabulate(src_file_path, dest_file_path= None):

    df = pd.read_csv(src_file_path)
    if len(df) > 0:
        if dest_file_path is None:
            dest_file_path = f"{src_file_path}-txt.csv"
        # Convert only object and bool columns to string (vectorized)
        # FIXME not happy to do that as may affect performance ...
        # for col in df.select_dtypes(include=['object', 'bool']):
        #     df[col] = df[col].astype(str)
        with open(dest_file_path, 'w') as f:
            f.write(tabulate(df.astype(str), headers='keys', tablefmt='psql'))
    return

# 0.001
def detect_breakout_retest_ver1(df, key_levels, tolerance=0.0005, check_breakout=True):
    """
    Detect breakout or retest on the latest candle only.

    df: DataFrame with at least ['open','high','low','close']
    key_levels: list of floats (support/resistance levels)
    tolerance: allowable distance to treat as "touch" (default 0.1%)

    Returns: list of signals for the latest candle
             Each signal is a tuple: (event_type, level, candle_index)
             event_type ∈ {"breakout_up", "breakout_down", "retest_up", "retest_down"}
    """


    tolerance_percentage = app_config['symbols_meta'][symbol]['retest_tolerance_percentage'] # used in config
    telorance_amount = app_config['symbols_meta'][symbol]['retest_tolerance_amount'] # used in config

    if len(df) < 2:
        return signals  # need at least 2 candles to compare breakout

    latest = df.iloc[-1]
    prev = df.iloc[-2]
    idx = df.iloc[-1]['date']

    for level in key_levels:
        if check_breakout:
            # --- Breakout detection ---
            if prev["close"] < level and latest["close"] > level:
                add_to_signlas("breakout_up", level, idx)
            elif prev["close"] > level and latest["close"] < level:
                add_to_signlas("breakout_down", level, idx)

        if telorance_amount == -1:
            telorance_amount = level * tolerance_percentage

        # --- Retest detection ---
        if abs(latest["low"] - level) <= telorance_amount and latest["close"] > level:
            add_to_signlas("retest_up", level, idx)
        elif abs(latest["high"] - level) <= telorance_amount and latest["close"] < level:
            add_to_signlas("retest_down", level, idx)

    return signals


def add_to_key_levels_dic(level, memo):
    global key_levels_dic
    if level != -1:
        key_levels_dic[level] = (memo)
    return


def get_key_levels_list():
    df = key_levels_df.copy()
    if len(df)> 0:
        df = df[df['symbol'] == symbol]
        x = df['price'].tolist()
        return x
    else:
        return []


def convert_signals_to_hover_df(signals):
    global hover_df
    if len(signals) == 0:
        return hover_df

    hovers_list = []
    for s in signals:
        logger.info(f"convert_signals_to_hover_df, signal:{s}")
        event = s[0]
        price_1 = s[1]
        date_1 = s[2]
        memo = s[3]
        if memo == '':
            memo = event
        if 'breakout_up' in event:
            obj = 'FLASH_UP'
            clr = 'Green'
        elif 'breakout_down' in event:
            obj = 'FLASH_DOWN'
            clr = 'Red'
        elif 'retest_up' in event:
            obj = 'RETEST_UP'
            clr = 'Green'
        elif 'retest_down' in event:
            obj = 'RETEST_DOWN'
        elif 'C. Type:' in event:
            obj = 'Candle Type'
            clr = 'Green'
        elif 'res_case_1' in event :  # this is for buy sell entry
            obj = 'Screening_case_1'
            clr = 'Green'
        elif 'res_case_2' in event:  # this is for buy sell entry
            obj = 'Screening_case_2'
            clr = 'Blue'
        elif 'case_3' in event:  # this is for buy sell entry
            obj = 'Screening_case_3'
            clr = 'Orange'
        elif 'ENTRY-case_1' in event:  # this is for buy sell entry
            obj = event
            clr = 'Green'
        elif 'ENTRY-case_2' in event:  # this is for buy sell entry
            obj = event
            clr = 'Blue'
        elif 'CANDLE_INFO' in event:  # this is for buy sell entry
            obj = event
            clr = 'Orange'
        else:
            obj = event
            clr = 'Orange'

        data = {
            'symbol': symbol,
            'time_frame': time_frame,
            'object': obj,
            'color': clr,
            'price_1': price_1,
            'date_1': date_1,
            'memo': f'{memo}',
            'unique_id': f'{symbol}--{obj}--{date_1}'
        }
        hovers_list.append(data)
    if len(hovers_list) > 0:
        hover_df = pd.concat([hover_df, pd.DataFrame(hovers_list)], ignore_index=True)
        #hover_df = hover_df.drop_duplicates(keep='first')
    return hover_df

def add_test_key_levels():
    section = app_config.get('test', {})  # or loop through multiple sections later
    levels = section.get('levels', {})

    if levels:  # only run if levels exist
        for key_level, level_data in levels.items():
            symbol = level_data['symbol']
            price = level_data['price']
            memo = level_data.get('memo', '')

            add_to_key_levels_df(
                symbol=symbol,
                time_frame='1 min',
                key_level_name=key_level,
                price=price,
                memo=memo
            )
            add_to_drawing_objects_df(symbol=symbol, time_frame=time_frame, object='dot', color='Black',
                                      price_1=price, memo=f'{memo}',
                                      unique_id=f'{symbol}-{time_frame}-{key_level}')

def detect_candle_patterns(df):
    """
    Detects key candlestick patterns on the last candle of df and appends to `signals`.
    Format: ("C. Type: pattern_name", price, date)
    """

    if len(df) < 2:
        return

    c = df.iloc[-1]
    date = c["date"]
    o, h, l, close = c["open"], c["high"], c["low"], c["close"]

    body = abs(close - o)
    upper_wick = h - max(o, close)
    lower_wick = min(o, close) - l
    full_range = h - l
    if full_range == 0:
        return

    upper_ratio = upper_wick / full_range
    lower_ratio = lower_wick / full_range
    body_ratio = body / full_range

    # 📍 Place marker above high for visibility
    mark_price = h + app_config['symbols_meta'][symbol]['chart_entry_offset']

    # --- Doji ---
    if body_ratio < 0.1:
        add_to_signlas("C. Type: Doji", mark_price, date)

    # --- Hammer ---
    elif lower_ratio > 0.6 and upper_ratio < 0.2 and close > o:
        add_to_signlas("C. Type: Hammer", mark_price, date)

    # --- Inverted Hammer ---
    elif upper_ratio > 0.6 and lower_ratio < 0.2 and close > o:
        add_to_signlas("C. Type: Inverted Hammer", mark_price, date)

    # --- Shooting Star ---
    elif upper_ratio > 0.6 and lower_ratio < 0.2 and close < o:
        add_to_signlas("C. Type: Shooting Star", mark_price, date)

    # --- Engulfing Patterns ---
    prev = df.iloc[-2]
    if (prev["close"] < prev["open"]) and (close > o) and (close > prev["open"]) and (o < prev["close"]):
        add_to_signlas("C. Type: Bullish Engulfing", mark_price, date)
    elif (prev["close"] > prev["open"]) and (close < o) and (close < prev["open"]) and (o > prev["close"]):
        add_to_signlas("C. Type: Bearish Engulfing", mark_price, date)

    return signals


def find_add_key_levels_to_key_levels_df():

    low_for_5_min, high_for_5_min = find_session_high_and_low(df, start="09:30", end="09:35")
    add_to_drawing_objects_df(symbol=symbol, time_frame=time_frame, object='dot', color='Black', price_1=low_for_5_min, memo=f'5ML {low_for_5_min}', unique_id=f'{symbol}-{time_frame}-5ML')
    add_to_drawing_objects_df(symbol=symbol, time_frame=time_frame, object='dot', color ='Black', price_1=high_for_5_min, memo=f'5MH {high_for_5_min}', unique_id=f'{symbol}-{time_frame}-5MH')
    add_to_key_levels_df(symbol, time_frame, '5ML', low_for_5_min, f'5ML {low_for_5_min}')
    add_to_key_levels_df(symbol, time_frame, '5MH', high_for_5_min, f'5MH {high_for_5_min}')

    low_for_pre_market, high_for_pre_market = find_session_high_and_low(df, start="04:00", end="09:30", wait_until_end_of_period=False)
    add_to_drawing_objects_df(symbol=symbol, time_frame=time_frame, object='dash', color='Red', price_1=low_for_pre_market, memo=f'PML {low_for_pre_market}', unique_id=f'{symbol}-{time_frame}-PML')
    add_to_drawing_objects_df(symbol=symbol, time_frame=time_frame, object='dash', color ='Red', price_1=high_for_pre_market, memo=f'PMH {high_for_pre_market}', unique_id=f'{symbol}-{time_frame}-PMH')
    add_to_key_levels_df(symbol, time_frame, 'PML', low_for_pre_market, f'PML {low_for_pre_market}')
    add_to_key_levels_df(symbol, time_frame, 'PMH', high_for_pre_market, f'PMH {high_for_pre_market}')

def add_buy_a_sell_entries_to_signals(buy_sell_case_results_list):
    for buy_sell_case_result in buy_sell_case_results_list:

        logger.info(f"buy_sell_case_result: {buy_sell_case_result} , type(buy_sell_case_result): {type(buy_sell_case_result)}")
        case = buy_sell_case_result[0]
        can_buy = buy_sell_case_result[1]
        can_sell = buy_sell_case_result[2]
        res_str = f"{buy_sell_case_result[3]}"
        offset_symbol = app_config['symbols_meta'][symbol]['chart_entry_offset']

        if "1" in case:  # for case_1 goes -1
            offset = -1 * offset_symbol
        elif "2" in case: # for case_2 goes -2
            offset = -2 * offset_symbol
        else:
            offset = -3 * offset_symbol

        # This way we don't overlap entries in the chart ...

        if case == 'case_1':
            price = df['low'].iloc[-1]
        elif case == 'case_2':
            price = df['high'].iloc[-1]
        else:
            price = df['close'].iloc[-1]


        if can_buy:
            add_to_signlas(f"BUY_ENTRY-{case}", price, df['date'].iloc[-1], '')

        if can_sell:
            add_to_signlas(f"SELL_ENTRY-{case}", price, df['date'].iloc[-1], '')

        add_to_signlas( f"{res_str}", df['close'].iloc[-1] + offset , df['date'].iloc[-1], '')  #

    return

def check_buy_and_sell_cases():
    buy_sell_case_results = []

    for case in app_config['cases']:
        res = check_buy_sell_condition(case)
        buy_sell_case_results.append(res)

    return buy_sell_case_results


def check_buy_sell_condition(case):
    res_str = ""
    try:

        # retest_tolerance_percentage = app_config['symbols_meta'][symbol]['retest_tolerance_percentage'] # used in config
        levels = get_levels_dic()  # used in config
        levels_closeness_limit = app_config['symbols_meta'][symbol]['levels_closeness_limit']  # used in config
        min_required_move_from_level = app_config['symbols_meta'][symbol]['min_required_move_from_level']  # used in config
        price = df['close'].iloc[-1]  # used in config

        logger.info(f"in check_buy_sell_condition, levels: {levels}")

        can_buy = False
        can_sell = False

        buy_condition_01 = app_config['cases'][case]['long']['condition_01']
        sell_condition_01 = app_config['cases'][case]['short']['condition_01']
        buy_condition_02 = app_config['cases'][case]['long']['condition_02']
        sell_condition_02 = app_config['cases'][case]['short']['condition_02']
        buy_condition_03 = app_config['cases'][case]['long']['condition_03']
        sell_condition_03 = app_config['cases'][case]['short']['condition_03']
        buy_condition_04 = app_config['cases'][case]['long']['condition_04']
        sell_condition_04 = app_config['cases'][case]['short']['condition_04']
        buy_condition_05 = app_config['cases'][case]['long']['condition_05']
        sell_condition_05 = app_config['cases'][case]['short']['condition_05']

        eval_buy_condition_01 = eval(buy_condition_01)
        eval_buy_condition_02 = eval(buy_condition_02)
        eval_buy_condition_03 = eval(buy_condition_03)
        eval_buy_condition_04 = eval(buy_condition_04)
        eval_buy_condition_05 = eval(buy_condition_05)

        eval_sell_condition_01 = eval(sell_condition_01)
        eval_sell_condition_02 = eval(sell_condition_02)
        eval_sell_condition_03 = eval(sell_condition_03)
        eval_sell_condition_04 = eval(sell_condition_04)
        eval_sell_condition_05 = eval(sell_condition_05)

        logger.info(
            f"\nbuy_condition_01: {buy_condition_01}, "
            f"\nbuy_condition_02: {buy_condition_02}, "
            f"\nbuy_condition_03: {buy_condition_03}, "
            f"\nbuy_condition_04: {buy_condition_04}")
        logger.info(f"{eval_buy_condition_01}. {eval_buy_condition_02}. {eval_buy_condition_03}.{eval_buy_condition_04}")

        logger.info(
            f"\nsell_condition_01: {sell_condition_01}, "
            f"\nsell_condition_02: {sell_condition_02}, "
            f"\nsell_condition_03: {sell_condition_03}, "
            f"\nsell_condition_04: {sell_condition_04}")
        logger.info(f"{eval_sell_condition_01}. {eval_sell_condition_02}. {eval_sell_condition_03}. {eval_sell_condition_04}")

        if eval(app_config['cases'][case]['long']['master_condition']):
            can_buy = True
        if eval(app_config['cases'][case]['short']['master_condition']):
            can_sell = True

        logger.info(f"check_buy_sell_condition(), can_buy: {can_buy}, can_sell: {can_sell}")
        res_str = (f"res_{case}:{eval_buy_condition_01}.{eval_buy_condition_02}.{eval_buy_condition_03}.{eval_buy_condition_04}.{eval_buy_condition_05} ... "
                 f"{eval_sell_condition_01}.{eval_sell_condition_02}.{eval_sell_condition_03}.{eval_sell_condition_04}.{eval_sell_condition_05}")

    except Exception as e:
        print(traceback.format_exc())
        logger.error(f"error {e}")

    return case, can_buy, can_sell, res_str


def price_retest(side='up', idx_list=[-2], level=0, both_sides=False):

    global retest_for_level_in_previous_candle_dic
    global retest_idx_for_level_called_from_config
    if level == 0:
        return False

    telorance_amount = app_config['symbols_meta'][symbol]['retest_tolerance_amount']

    retest = False
    retest_idx = 0

    for idx in idx_list:
        row = df.iloc[idx]


        # --- Retest detection ---
        if side == 'up':
            if level > row["low"] and level - row["low"] <= telorance_amount and row["close"] > level:
                logger.info(f"symbol: {symbol}, level: {level}, date:{df.iloc[idx]['date']} , row: {row} ")
                retest = True
            if both_sides and abs(level - row["low"]) <= telorance_amount and row["close"] > level:   # close > level.  low is close to the level in both sides.
                retest = True
        else:
            if row["high"] > level and row["high"] - level <= telorance_amount and row["close"] < level:
                retest = True
            if both_sides and abs(level - row["high"]) <= telorance_amount and row["close"] < level:   # close < level.  high is close to the level in both sides.
                retest = True

        if retest: # we dont want continue if retest happened
            retest_idx = idx
            break

    if retest:
        add_to_candle_info_df(date=df['date'].iloc[retest_idx], price=df['close'].iloc[retest_idx],memo=f'retest @ {level}')
        retest_idx_for_level_called_from_config[level] = retest_idx

    return retest


def breakout_in_last_x_candles(side='up', idx_list=[-2], level=0):
    logger.info(f"in breakout_in_last_x_candles, symbol: {symbol}, idx_list: {idx_list}, level:{level}")

    if level == 0:
        return False
    gap = app_config['symbols_meta'][symbol]['breakout_confirmation_distance']
    cross_happend = False
    cross_idx = 0
    for idx in idx_list:
        row = df.iloc[idx]
        # --- Breakout detection ---
        if side == 'up':
            if row["low"] < level and row["close"] > level + gap:
                logger.info(f"in breakout_in_last_x_candles, idx: {idx}, level: {level}, retest happened!! ")
                cross_happend = True
        else:
            if row["high"] > level and row["close"] < level - gap:
                logger.info(f"in breakout_in_last_x_candles, idx: {idx}, level: {level}, retest happened!! ")
                cross_happend = True
        if cross_happend:
            cross_idx = idx
            break


    if cross_happend:
        add_to_candle_info_df(date=df['date'].iloc[cross_idx], price=df['close'].iloc[cross_idx],memo=f'cross @ {level}')

    return cross_happend



def get_levels_dic():
    global key_levels_df
    df = key_levels_df
    df['price'] = pd.to_numeric(df['price'], errors='coerce')
    levels = dict(zip(
        df.loc[df['symbol'] == symbol, 'key_level'],
        df.loc[df['symbol'] == symbol, 'price']
    ))
    return levels



def add_to_signlas(event, price, date, memo=''):

    global signals
    signals.append((event, price, date, memo))

    return


def check_entry_vs_retest(side='up', level=1):
    if retest_idx_for_level_called_from_config.get(level, -1) == -1:
        return False
    i = retest_idx_for_level_called_from_config.get(level, -1) # This is index for retest...
    if side == 'up':
        if df['close'].iloc[-1] > df['close'].iloc[i]:  # clode > retest close
            return True
        else:
            return False
    else:
        if df['close'].iloc[-1] < df['close'].iloc[i]:
            return True
        else:
            return False

def add_candle_info_df_to_signals():

    df = candle_info_df
    df = df.drop_duplicates() # for examomple multiple retest on one candle
    df_grouped = (
        df.groupby(['date', 'price'], as_index=False)
        .agg({'memo': lambda x: ' | '.join(x)})
    )

    offset_symbol = app_config['symbols_meta'][symbol]['chart_entry_offset']
    offset = offset_symbol + 1.5
    for index, row in df_grouped.iterrows():
        date = row['date']
        price = row['price']
        memo = f"{row['memo']} - {date}"  # adding date to the memo ...

        add_to_signlas("CANDLE_INFO", price + offset, date, memo)  #

    return

def add_to_candle_info_df(date, price, memo):
    global candle_info_df

    data = {
        'date': date,
        'price': price,
        'memo': memo
    }
    candle_info_df = pd.concat([candle_info_df, pd.DataFrame([data])])


if __name__ == "__main__":


    app_config = load_app_config(portfolio_id)
    ib_config = load_ib_config()
    ib = create_ib_connection()




    # support_resistance_map = {}
    drawing_objects_df = pd.DataFrame()
    hover_df = pd.DataFrame( columns=['symbol', 'time_frame', 'object', 'color', 'date_1', 'price_1', 'date_2', 'price_2', 'memo','unique_id'])
    key_levels_df = pd.DataFrame( columns=['symbol', 'time_frame', 'key_level', 'price', 'memo','unique_id'])
    consequence_exception = 0

    for symbol in app_config['symbols']:
        get_market_data('1 day')
        get_market_data('1 min')

    j = run_id = 0
    while True:
      try:
        start_time = time.time()
        j += 1
        now = datetime.datetime.now()
        run_date_time = now.strftime("%Y-%m-%d__%H-%M")
        unique_run_id = f"{now.strftime('%Y%m%d-%H%M%S')}-{run_id}"

        logger.info(f"==================== j: {j}  run_date_time: {run_date_time}")
        for symbol in app_config['symbols']:
            time_frame = '1 min'
            signals = []

            df = get_market_data('1 min')
            save_ohlc_for_chart(df)

            if j ==1:
                calculate_PDL_PDH(df)

            find_add_key_levels_to_key_levels_df()
            # add_test_key_levels()

            key_levels_list = get_key_levels_list()
            logger.info(f"key_levels_list: {key_levels_list}")
            if False:
                signals = detect_breakout_retest_ver1(df, key_levels_list)

            detect_candle_patterns(df)
            buy_sell_case_results_list = check_buy_and_sell_cases()
            add_buy_a_sell_entries_to_signals(buy_sell_case_results_list)

            add_candle_info_df_to_signals()

            #logger.info(f"key_levels_df:\n {key_levels_df.to_markdown()}")
            logger.info(f"signals: {signals}")
            hover_df = convert_signals_to_hover_df(signals)

            save_df_to_csv_a_tabular(drawing_objects_df, '10-drawing_objects_df.csv', mode='w', dir=charts_dir)
            save_df_to_csv_a_tabular(key_levels_df, dir=portfolio_dir, file_name='11-key_levels_df.csv', mode='w')
            save_df_to_csv_a_tabular(hover_df, dir=charts_dir, file_name='12-hover_df.csv', mode='a')

            if j % 4 == 0:
                app_config = load_app_config(portfolio_id)

        end_time = time.time()

        sleep_enough()
        consequence_exception = 0
      except Exception as e:
          consequence_exception = consequence_exception + 1
          # TODO needs better exception handling
          logger.error(f"X error: {e}")
          import traceback

          print(traceback.format_exc())
          time.sleep(60)

          if consequence_exception == 3:
              email_util_ver_02.send_email('saeed.bx1@yahoo.com', f'error in {portfolio_id}',
                                           body=f"{e}<br\><br\><br\>{traceback.format_exc()}")

          if isinstance(e, ConnectionError):
              # set a flag and set connection in loop .. exists if riase exceptin
              logger.error("It's a ConnectionError, try to reconnect ")
              ib = create_ib_connection()
              logger.warning("Done.")
