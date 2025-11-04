import datetime
import json
import logging.handlers
import math
import os
import pprint
import sys
import time
import traceback

import ib_insync.util as ib_util
import numpy as np
import pandas as pd
import requests
from finta import TA
from ib_insync import *
from pandas.tseries.offsets import BDay
from ruamel.yaml import YAML
from tabulate import tabulate

yaml = YAML()
yaml.preserve_quotes = True  # Optional: preserve quotes if any
yaml.width = 1000 # so will not wrap lines in the yaml file

sys.path.insert(0, f'../')
for dir_1 in os.listdir(os.path.join('../')):
    if (dir_1.startswith("a") or dir_1.startswith("u") ):
        sys.path.insert(0, f'../{dir_1}')
from utils import miscutils
from utils import email_util_ver_02
from utils import atr_tolerance_helper
from trading_utils import df_utils
from trading_utils import ib_utils
from trading_utils import global_state



portfolio_id = 'p250'
configs_folder = f'../configs'
config_file = f'{configs_folder}/app-config.yaml'

mode = 'back_test'

portfolio_dir = f'../../portfolios/results/{portfolio_id}'
reports_dir = f'../../portfolios/reports/{portfolio_id}'
log_dir = f'../../portfolios/logs/{portfolio_id}-{mode}/{datetime.datetime.now().strftime("%Y-%m-%d")}'
health_status_dir = f'../../portfolios/logs/{portfolio_id}-{mode}'
detailed_log_dir = f'../../portfolios/detailed-logs/{portfolio_id}-{mode}'
intermediate_dir = f'../../portfolios/intermediate/{portfolio_id}'

ohlc_dir = f'../../portfolios/backtest-ohlc/{portfolio_id}'
charts_dir = f'../../portfolios/charts/{portfolio_id}'
backtest_ohlc_dir = f'../../portfolios/backtest-ohlc/{portfolio_id}'

os.makedirs(portfolio_dir, exist_ok=True)
os.makedirs(reports_dir, exist_ok=True)
os.makedirs(log_dir, exist_ok=True)
os.makedirs(detailed_log_dir, exist_ok=True)
os.makedirs(ohlc_dir, exist_ok=True)
os.makedirs(intermediate_dir, exist_ok=True)
os.makedirs(charts_dir, exist_ok=True)
os.makedirs(backtest_ohlc_dir, exist_ok=True)

def load_app_config(portfolio_id):
    global app_config
    print(f"loading app_config ....")
    app_config = miscutils.load_config(f'{configs_folder}/config-{portfolio_id}.yaml')
    print(f"loaded.")
    return app_config

app_config = load_app_config(portfolio_id)
logging_level = app_config['logging_level']
# ###
# Logging setup ..
# ###

log_filename = f"{log_dir}/{portfolio_id}.log"
file_r_handler = logging.handlers.RotatingFileHandler(filename=f"{log_dir}/{portfolio_id}.log", maxBytes= 5 * 1024 * 1024, backupCount=150)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
file_r_handler.setFormatter(formatter)
logging.basicConfig(
    level=eval(logging_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        file_r_handler,
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

os.makedirs(portfolio_dir, exist_ok=True)
os.makedirs(reports_dir, exist_ok=True)
os.makedirs(log_dir, exist_ok=True)
os.makedirs(detailed_log_dir, exist_ok=True)
os.makedirs(ohlc_dir, exist_ok=True)
os.makedirs(intermediate_dir, exist_ok=True)
os.makedirs(charts_dir, exist_ok=True)
os.makedirs(backtest_ohlc_dir, exist_ok=True)

application_state_file_path = f'{intermediate_dir}/84-application_state.csv'

def load_ib_config():
    file = 'ib-config.yaml'
    logger.warning(f"loading ... {file}")
    app_config = miscutils.load_config(f'{configs_folder}/{file}')
    logger.info(f"loaded ... file")
    return app_config


def get_previous_bday():
    prev_day = (pd.Timestamp.today() - BDay(1)).normalize()
    return prev_day

def disconnect_ib(ib):
        try:
            logger.info("we need to diconnect first ...")
            ib.disconnect()  # 🔹 Important: ensure full teardown
            time.sleep(1)

        except Exception as e:
            logger.error(f"disconnect_ib: ⚠️ Exception: {e}")
            time.sleep(1)


def on_disconnect():
    try:
        logger.warning("⚠️ IB disconnected! Reconnecting...")
        create_ib_connection()
    except Exception as e:
        logger.error(f"disconnect_ib: ⚠️ Exception: {e}")
        time.sleep(1)
    return


def create_ib_connection():
    connected = False
    ib = None
    while not connected:
        try:
            ib = IB()
            disconnect_ib(ib)
            # ib.disconnectedEvent += on_disconnect
            ib.connect(ib_config['ip'], ib_config['port'], clientId=ib_config['client_id'], timeout=0)
            ib.commissionReportEvent += ib_utils.on_commission_report
            ib.updatePortfolioEvent += ib_utils.on_portfolio_update

            connected = True
            logger.info(f"IB connected.")
        except Exception as e:
            # TODO needs better exception handling
            logger.error(f"error: {e}")
            logger.error(f"--------------")
            logger.error(traceback.format_exc())
            logger.info("Sleeping for 60 secs and retrying again ...")
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
        if df["date"].dt.tz is not None:
            df["date"] = df["date"].dt.tz_convert(None)
            df = miscutils.convert_column_timezone(df, 'date', 'date', from_zone='UTC', to_zone='America/New_York')

    return df


def get_market_data(symbol, time_frame ='1 day', historical_days= ''):
    if historical_days == '':
        historical_days = app_config[mode]['historical_days']

    logger.info(f"get_market_data(), symbol: {symbol}, time_frame: {time_frame}, historical_days: {historical_days}")
    contract = create_equity_contract(symbol)

    df = get_historical_data(contract, historical_days, time_frame)

    logger.info(f"in get_market_data: \n{df[-2:].to_markdown()}")
    return df

def create_equity_contract(symbol):
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
    df = df[['date','open', 'high', 'low', 'close', 'volume', 'atr_14']]
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
        logger.warning(f"unique_days: {unique_days}")
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

    logger.debug(f"Previous weekday RTH High: {day_high}")
    logger.debug(f"Previous weekday RTH Low: {day_low}" )

    add_to_drawing_objects_df(symbol=symbol, time_frame=time_frame,  object='dash', color='Blue', price_1=day_high, memo=f'PDH {day_high}', unique_id=f'{symbol}-{time_frame}-PDH' )
    add_to_drawing_objects_df(symbol=symbol, time_frame=time_frame,  object='dash', color='Blue', price_1=day_low, memo=f'PDL {day_low}' , unique_id=f'{symbol}-{time_frame}-LDH' )
    add_to_key_levels_df(symbol=symbol, time_frame=time_frame, key_level_name='PDH', price=day_high, memo=f'PDH {day_high}')
    add_to_key_levels_df(symbol=symbol, time_frame=time_frame, key_level_name='PDL', price=day_low, memo=f'PDH {day_high}')
    return

def load_application_state_from_file():
    global application_state
    file_path = application_state_file_path
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            logger.info(f"loading from file_path: {file_path} ")
            application_state = json.load(f)
        logger.info(f"loaded, application_state: {application_state}")
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

    return

def is_between(now=None, start_str="9:25", end_str="11:00"):
    if now is None:
        now = datetime.datetime.now().time()

    # parse strings into time objects
    start = datetime.datetime.strptime(start_str, "%H:%M").time()
    end = datetime.datetime.strptime(end_str, "%H:%M").time()

    return start <= now <= end

def sleep_enough():
    run_spend_time = round(end_time - start_time, 2)
    if is_trade_time:
        logger.warning(f'{run_number}) run_spend_time: {run_spend_time} seconds, no sleep ...')
    else:
        run_should_take = app_config['run_should_take_seconds']
        need_sleep_seconds = 0
        if run_spend_time < run_should_take:
            need_sleep_seconds = run_should_take - run_spend_time
        logger.warning(f'{run_number}) run_spend_time: {run_spend_time} seconds, run_should_take: {run_should_take} unique_run_number: {unique_run_number}')
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









# 0.001

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
        logger.debug(f"convert_signals_to_hover_df, signal:{s}")
        symbol = s[0]
        event = s[1]
        price_1 = s[2]
        date_1 = s[3]
        memo = s[4]
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
            clr = 'Orange'
        elif 'ENTRY_case_1' in event:  # this is for buy sell entry
            obj = event
            clr = 'Green'
        elif 'ENTRY_case_2' in event:  # this is for buy sell entry
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
        hover_df = hover_df.drop_duplicates(subset=['symbol','object','date_1'],keep='first')
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
    Format: ("CANDLE_TYPE: pattern_name", price, date)
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
    mark_price = get_offseted_price('up',h)

    # --- Doji ---
    if body_ratio < 0.1:
        add_to_signlas(symbol, "CANDLE_TYPE", mark_price, date, f"Doji ... {df['date'].iloc[-1]}")

    # --- Hammer ---
    elif lower_ratio > 0.6 and upper_ratio < 0.2 and close > o:
        add_to_signlas(symbol, "CANDLE_TYPE", mark_price, date, f"Hammer {df['date'].iloc[-1]}")

    # --- Inverted Hammer ---
    elif upper_ratio > 0.6 and lower_ratio < 0.2 and close > o:
        add_to_signlas(symbol, "CANDLE_TYPE", mark_price, date, f"Inverted Hammer ... {df['date'].iloc[-1]}")

    # --- Shooting Star ---
    elif upper_ratio > 0.6 and lower_ratio < 0.2 and close < o:
        add_to_signlas(symbol, "CANDLE_TYPE", mark_price, date, f"Shooting Star ... {df['date'].iloc[-1]}")

    # --- Engulfing Patterns ---
    prev = df.iloc[-2]
    if (prev["close"] < prev["open"]) and (close > o) and (close > prev["open"]) and (o < prev["close"]):
        add_to_signlas(symbol, "CANDLE_TYPE", mark_price, date, f"Bullish Engulfing ... {df['date'].iloc[-1]}")
    elif (prev["close"] > prev["open"]) and (close < o) and (close < prev["open"]) and (o > prev["close"]):
        add_to_signlas(symbol, "CANDLE_TYPE", mark_price, date, f"Bearish Engulfing ... {df['date'].iloc[-1]}")

    return signals


def find_add_5MH_5ML_levels_to_key_levels_df():

    # ###
    # for back test
    # ###
    wait_until_end_of_period = False

    low_for_5_min, high_for_5_min = find_session_high_and_low(df, start="09:30", end="09:34", wait_until_end_of_period= wait_until_end_of_period)
    add_to_drawing_objects_df(symbol=symbol, time_frame=time_frame, object='dot', color='Black', price_1=low_for_5_min, memo=f'5ML {low_for_5_min}', unique_id=f'{symbol}-{time_frame}-5ML')
    add_to_drawing_objects_df(symbol=symbol, time_frame=time_frame, object='dot', color ='Black', price_1=high_for_5_min, memo=f'5MH {high_for_5_min}', unique_id=f'{symbol}-{time_frame}-5MH')
    add_to_key_levels_df(symbol, time_frame, '5ML', low_for_5_min, f'5ML {low_for_5_min}')
    add_to_key_levels_df(symbol, time_frame, '5MH', high_for_5_min, f'5MH {high_for_5_min}')

    return
def find_add_PDH_PDL_levels_to_key_levels_df():

    wait_until_end_of_period = True

    low_for_pre_market, high_for_pre_market = find_session_high_and_low(df, start="04:00", end="09:29", wait_until_end_of_period= wait_until_end_of_period)
    add_to_drawing_objects_df(symbol=symbol, time_frame=time_frame, object='dash', color='Red', price_1=low_for_pre_market, memo=f'PML {low_for_pre_market}', unique_id=f'{symbol}-{time_frame}-PML')
    add_to_drawing_objects_df(symbol=symbol, time_frame=time_frame, object='dash', color ='Red', price_1=high_for_pre_market, memo=f'PMH {high_for_pre_market}', unique_id=f'{symbol}-{time_frame}-PMH')
    add_to_key_levels_df(symbol, time_frame, 'PML', low_for_pre_market, f'PML {low_for_pre_market}')
    add_to_key_levels_df(symbol, time_frame, 'PMH', high_for_pre_market, f'PMH {high_for_pre_market}')

    return
def add_buy_a_sell_entries_to_signals(buy_sell_case_results_list):
    for buy_sell_case_result in buy_sell_case_results_list:

        logger.debug(f"add_buy_a_sell_entries_to_signals(), buy_sell_case_result: {buy_sell_case_result}")
        case = buy_sell_case_result[0]
        can_buy = buy_sell_case_result[1]
        can_sell = buy_sell_case_result[2]
        res_str = f"{buy_sell_case_result[3]}"


        # offseted_price = get_offseted_price(df['high'].iloc[-1])
        # This way we don't overlap entries in the chart ...

        if case == 'case_1':
            price = df['low'].iloc[-1]
        elif case == 'case_2':
            price = df['high'].iloc[-1]
        else:
            price = df['close'].iloc[-1]


        if can_buy:
            add_to_signlas(symbol, f"BUY_ENTRY_{case}", price, df['date'].iloc[-1], f"{case} - {res_str}")

        if can_sell:
            add_to_signlas(symbol, f"SELL_ENTRY_{case}", price, df['date'].iloc[-1], f"{case} - {res_str}")

        # add_to_signlas(symbol,  f"SCREENING_{case}", offseted_price, df['date'].iloc[-1], f'{case} - {res_str}')  #
        price = get_latest_offseted_price('down', df['low'].iloc[-1])
        add_to_candle_info_df(date=df['date'].iloc[-1], price=price, memo=f'{case} - {res_str}')

    return

def check_buy_and_sell_cases():
    buy_sell_case_results = []

    for case in app_config['cases']:
        res = check_buy_sell_condition(case)
        buy_sell_case_results.append(res)

    return buy_sell_case_results

def get_next_level(side, level):
    if side == 'up':
        next_level = get_levels_dic().get('PDH', -1)
    else:
        next_level = get_levels_dic().get('PDL', -1)

    return next_level


def replace_level_if_needed(side, can_replace_level, level):
    # If two levels are close, we replace with next one ...

    if not can_replace_level:
        return level
    closeness_distance = eval(app_config['closeness_distance'])
    next_level = get_next_level(side, level)

    if side == 'up':
        if next_level > level and abs(next_level - level) < closeness_distance:
            logger.info(f"replace_level_if_needed, level is replaced,{symbol}, {side}, level: {level}, next_level: {next_level}, {df['date'].iloc[-1]}")
            price = get_offseted_price('up', df['high'].iloc[-1])
            add_to_signlas(symbol, 'LEVEL_REPLACED', price, df['date'].iloc[-1], f'level is replaced. from: {level}, to: {next_level}')
            return next_level
    else:
        if next_level < level and abs(next_level - level) < closeness_distance:
            logger.info(f"replace_level_if_needed, level is replaced, {symbol}, {side}, level: {level}, next_level: {next_level}, {df['date'].iloc[-1]}")
            price = get_offseted_price('up', df['high'].iloc[-1])
            add_to_signlas(symbol, 'LEVEL_REPLACED', price,  df['date'].iloc[-1], f'level is replaced. from: {level}, to: {next_level}')
            return next_level
    return level

def check_buy_sell_condition(case):

    can_buy = False
    can_sell = False
    res_str = ''
    long_level = -1
    short_level = -1

    try:
        levels = get_levels_dic()  # used in config

        can_replace_level = app_config['cases'][case]['can_replace_level']
        long_level = eval(app_config['cases'][case]['long']['level'])
        short_level = eval(app_config['cases'][case]['short']['level'])

        long_level = replace_level_if_needed('up', can_replace_level, long_level)
        short_level = replace_level_if_needed('down', can_replace_level, short_level)

        min_required_move_from_level = app_config['symbols_meta'][symbol]['min_required_move_from_level']  # used in config
        price = df['close'].iloc[-1]  # used in config

        logger.debug(f"in check_buy_sell_condition, levels: {levels}")


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
        buy_condition_06 = app_config['cases'][case]['long']['condition_06']
        sell_condition_06 = app_config['cases'][case]['short']['condition_06']
        buy_condition_07 = app_config['cases'][case]['long']['condition_07']
        sell_condition_07 = app_config['cases'][case]['short']['condition_07']
        buy_condition_08 = app_config['cases'][case]['long']['condition_08']
        sell_condition_08 = app_config['cases'][case]['short']['condition_08']
        buy_condition_09 = app_config['cases'][case]['long']['condition_09']
        sell_condition_09 = app_config['cases'][case]['short']['condition_09']
        buy_condition_10 = app_config['cases'][case]['long']['condition_10']
        sell_condition_10 = app_config['cases'][case]['short']['condition_10']

        eval_buy_condition_01 = eval(buy_condition_01)
        eval_buy_condition_02 = eval(buy_condition_02)
        eval_buy_condition_03 = eval(buy_condition_03)
        eval_buy_condition_04 = eval(buy_condition_04)
        eval_buy_condition_05 = eval(buy_condition_05)
        eval_buy_condition_06 = eval(buy_condition_06)
        eval_buy_condition_07 = eval(buy_condition_07)
        eval_buy_condition_08 = eval(buy_condition_08)
        eval_buy_condition_09 = eval(buy_condition_09)
        eval_buy_condition_10 = eval(buy_condition_10)

        eval_sell_condition_01 = eval(sell_condition_01)
        eval_sell_condition_02 = eval(sell_condition_02)
        eval_sell_condition_03 = eval(sell_condition_03)
        eval_sell_condition_04 = eval(sell_condition_04)
        eval_sell_condition_05 = eval(sell_condition_05)
        eval_sell_condition_06 = eval(sell_condition_06)
        eval_sell_condition_07 = eval(sell_condition_07)
        eval_sell_condition_08 = eval(sell_condition_08)
        eval_sell_condition_09 = eval(sell_condition_09)
        eval_sell_condition_10 = eval(sell_condition_10)

        logger.info(
            f"\n{symbol}, case: {case} "
            f"\nbuy_condition_01: {buy_condition_01} "
            f"\nbuy_condition_02: {buy_condition_02} "
            f"\nbuy_condition_03: {buy_condition_03} "
            f"\nbuy_condition_04: {buy_condition_04} "
            f"\nbuy_condition_05: {buy_condition_05} "
            f"\nbuy_condition_06: {buy_condition_06} "
            f"\nbuy_condition_07: {buy_condition_07} "
            f"\nbuy_condition_08: {buy_condition_08} "
            f"\nbuy_condition_09: {buy_condition_09} "
            f"\nbuy_condition_10: {buy_condition_10} "
            f"\n"
            f"\n{symbol}, case: {case} "
            f"\nsell_condition_01: {sell_condition_01}"
            f"\nsell_condition_02: {sell_condition_02}"
            f"\nsell_condition_03: {sell_condition_03}"
            f"\nsell_condition_04: {sell_condition_04}"
            f"\nsell_condition_05: {sell_condition_05}"
            f"\nsell_condition_06: {sell_condition_06}"
            f"\nsell_condition_07: {sell_condition_07}"
            f"\nsell_condition_08: {sell_condition_08}"
            f"\nsell_condition_09: {sell_condition_09}"
            f"\nsell_condition_10: {sell_condition_10}"
            f"\n"
        )

        if eval(app_config['cases'][case]['long']['master_condition']):
            can_buy = True
        if eval(app_config['cases'][case]['short']['master_condition']):
            can_sell = True

        logger.info(f"check_buy_sell_condition(), {case}, can_buy: {can_buy}, can_sell: {can_sell}")

        long_breakup_idxs = break_out_indices_by_level_set.get(long_level, set())
        long_retest_idxs = retest_indices_by_level_set.get(long_level, set())

        short_breakup_idxs = break_out_indices_by_level_set.get(short_level, set())
        short_retest_idxs = retest_indices_by_level_set.get(short_level, set())




        # This is shown in the chart ..
        res_str = (f"res_{case}:<br>"
                   f"{eval_buy_condition_01}.{eval_buy_condition_02}.{eval_buy_condition_03}|{eval_buy_condition_04}.{eval_buy_condition_05}.{eval_buy_condition_06}|{eval_buy_condition_07}.{eval_buy_condition_08}.{eval_buy_condition_09}|{eval_buy_condition_10} .. {long_breakup_idxs}.{long_retest_idxs} <br>"
                   f"{eval_sell_condition_01}.{eval_sell_condition_02}.{eval_sell_condition_03}|{eval_sell_condition_04}.{eval_sell_condition_05}.{eval_sell_condition_06}|{eval_sell_condition_07}.{eval_sell_condition_08}.{eval_sell_condition_09}.{eval_sell_condition_10} .. {short_breakup_idxs}.{short_retest_idxs} <br>"
                   f"{df['date'].iloc[-1].strftime('%H:%M')}, breakout: {breakout_idx}, retest: {retest_idx}")
        res_str = res_str.replace('True', 'T')
        res_str = res_str.replace('False', 'F')

        res_str_log = res_str.replace('<br>', '\n')
        logger.info(f"\n{case}, res_str: {res_str_log}")
    except Exception as e:
        logger.error(f"in check_buy_sell_condition: {symbol} {case} error {e}")
        logger.error(traceback.format_exc())
        res_str = f'res_{case}'
    return case, can_buy, can_sell, res_str, long_level, short_level

def is_retest_after_breakout(side='up', level=1):
    global retest_idx, breakout_idx

    breakout_idxs = break_out_indices_by_level_set.get(level, set())
    retest_idxs = retest_indices_by_level_set.get(level, set())

    if retest_idxs == set() or breakout_idxs == set():
        return  False
    if max(retest_idxs) > min(breakout_idxs):
        retest_idx = max(retest_idxs)
        valid_breakouts = [b for b in breakout_idxs if b < retest_idx]   # all the breakout idxs that are before retest_idx
        if valid_breakouts:
            breakout_idx = max(valid_breakouts)  # closest (largest) breakout before retest

        return True
    else:
        return False

def price_retest(side='up', idx_list=[-2], level=0, both_sides=False):

    if level == 0:
        return False

    # tolerance_amount = app_config['symbols_meta'][symbol]['retest_tolerance_amount']
    tolerance_amount = dynamic_tolerance.get('tolerance', 0)
    tolerance_amount = tolerance_amount * app_config['symbols_meta'][symbol].get('retest_tolerance_multiplier', 1)
    logger.info(f"price_retest(), {symbol}, tolerance_amount: {tolerance_amount}")
    retest = False

    for idx in idx_list:
        row = df.iloc[idx]


        # --- Retest detection ---
        if side == 'up':
            if level > row["low"] and level - row["low"] <= tolerance_amount and row["close"] > level:
                add_to_retest_indices_by_level_set(level, idx)
                logger.info(f"price_retest(), symbol: {symbol}, level: {level}, date:{df.iloc[idx]['date']} ")
                retest = True
                diff = abs(row['low']-level)

            if both_sides and abs(level - row["low"]) <= tolerance_amount and row["close"] > level:   # close > level.  low is close to the level in both sides.
                add_to_retest_indices_by_level_set(level, idx)
                retest = True
                diff = abs(row['low']-level)
        else:
            if row["high"] > level and row["high"] - level <= tolerance_amount and row["close"] < level:
                add_to_retest_indices_by_level_set(level, idx)
                retest = True
                diff = abs(row['high'] - level)
            if both_sides and abs(level - row["high"]) <= tolerance_amount and row["close"] < level:   # close < level.  high is close to the level in both sides.
                add_to_retest_indices_by_level_set(level, idx)
                retest = True
                diff = abs(row['high']-level)

    return retest

def add_atr_to_candle_info(dynamic_tolerance):
    add_to_candle_info_df(date=df['date'].iloc[-1], price=df['close'].iloc[-1],memo=f'{dynamic_tolerance}')
    return


def dummy_call(level):
    return True

def archive_open_trade_dic(symbol, open_trade_dic_4_symbol):
    open_trade_dic_arcive = {}
    open_trade_dic_arcive[unique_run_number] = open_trade_dic_4_symbol
    file_path = f'{intermediate_dir}/84-{unique_run_number}-{symbol}.csv'

    file_path = file_path
    with open(file_path, 'w') as f:
        try:
            logger.info(f"saving at file_path: {file_path}")
            json.dump(application_state, f, indent=4)
            logger.info(f"saving done. ")
        except Exception as e:
            # TODO add
            logger.error(e)




def breakout_in_last_x_candles(side='up', idx_list=[-2], level=0):

    logger.debug(f"in breakout_in_last_x_candles, symbol: {symbol}, idx_list: {idx_list}, level:{level}")

    if level == 0:
        return False
    gap = app_config['symbols_meta'][symbol]['breakout_confirmation_distance']
    breakout_happened = False

    for idx in idx_list:
        row = df.iloc[idx]
        previous = df.iloc[idx-1]
        # --- Breakout detection ---


        # --- breakout condition ---
        if side == 'up':
            breakout = (
                (row["low"] < level and row["close"] > level + gap)
                or (previous["open"] < level and row["close"] > level)
            )
        else:
            breakout = (
                (row["high"] > level and row["close"] < level - gap)
                or (previous["open"] > level and row["close"] < level)
            )

        if not breakout:
            continue


        # --- candle body confirmation ---
        body = abs(row["close"] - row["open"])
        candle_range = row["high"] - row["low"]
        if candle_range > 0 and body / candle_range < 0.5: # do not remove candle_rage > 0 will raise devided by zero exception
            continue

        logger.info(f"in breakout_in_last_x_candles, idx: {idx}, level: {level}, retest happened!! ")
        add_to_break_out_indices_by_level_set(level, idx)
        breakout_happened = True


    return breakout_happened

def get_offseted_price(side='up', price=1):
    offset_symbol = app_config['symbols_meta'][symbol]['chart_entry_offset']
    price = price + get_offset_counter(side, add=True) * offset_symbol
    return price

def get_latest_offseted_price(side='up', price = 1):
    offset_symbol = app_config['symbols_meta'][symbol]['chart_entry_offset']
    if side == 'up':
        price = price + get_offset_counter(side=side, add=False) * offset_symbol
    else:
        price = price - get_offset_counter(side=side, add=False) * offset_symbol
    return price

def add_to_break_out_indices_by_level_set(level, idx):

    global break_out_indices_by_level_set
    logger.info(f"{df['date'].iloc[-1]}, break_out_indices_by_level_set: {break_out_indices_by_level_set}")
    # if level not in break_out_indices_by_level_set:
    if break_out_indices_by_level_set.get(level, set()) == set():
        break_out_indices_by_level_set[level] = set()

    break_out_indices_by_level_set[level].add(idx)
    # add_to_candle_info_df(date=df['date'].iloc[idx], price=df['low'].iloc[idx], memo=f'breakout @ {level}')
    offseted_price = get_offseted_price('up', df['close'].iloc[idx])
    add_to_signlas(symbol, 'BREAKOUT', offseted_price, df['date'].iloc[idx], f"BREAKOUT ... {df['date'].iloc[idx]}... " )
    return

def add_to_retest_indices_by_level_set(level, idx):
    global retest_indices_by_level_set
    logger.info(f"{df['date'].iloc[-1]}, retest_indices_by_level_set: {retest_indices_by_level_set}")
    # if level not in retest_indices_by_level_set:
    if retest_indices_by_level_set.get(level, set()) == set():
        retest_indices_by_level_set[level] = set()

    retest_indices_by_level_set[level].add(idx)
    # add_to_candle_info_df(date=df['date'].iloc[idx], price=df['high'].iloc[idx], memo=f'retest @ {level}')
    offseted_price = get_offseted_price('up', df['low'].iloc[idx])
    add_to_signlas(symbol, 'RETEST', offseted_price, df['date'].iloc[idx], f"RETEST ... {df['date'].iloc[idx]}")
    return

def get_levels_dic():
    global key_levels_df
    df = key_levels_df
    df['price'] = pd.to_numeric(df['price'], errors='coerce')
    levels = dict(zip(
        df.loc[df['symbol'] == symbol, 'key_level'],
        df.loc[df['symbol'] == symbol, 'price']
    ))
    return levels



def add_to_signlas(symbol, event, price, date, memo=''):

    global signals
    signals.append((symbol, event, price, date, memo))

    return


def check_entry_vs_retest(side='up', level=1, retest_ohlc=''):

    if retest_idx == 0 or breakout_idx == 0:
        return False

    if side == 'up':
        ohlc_field = 'high' if retest_ohlc == '' else retest_ohlc
        if df['high'].iloc[-1] > df[ohlc_field].iloc[retest_idx]:  # clode > retest high
            return True
        else:
            return False
    else:
        ohlc_field = 'low' if retest_ohlc == '' else retest_ohlc
        if df['low'].iloc[-1] < df[ohlc_field].iloc[retest_idx]:
            return True
        else:
            return False
    return False


def check_price_vs_level(side='up', price=0, level=0):

    min_required_move_from_level = app_config['symbols_meta'][symbol]['min_required_move_from_level']

    if side == 'up':
        return price + min_required_move_from_level > level
    else:
        return price < level - min_required_move_from_level


def get_offset_counter(side='up', add=True):
    # This is for to see what is the offset for the hover  for the cnalde.
    # resets in every candle ...
    global up_offset_counter
    global down_offset_counter
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
    # combine memo for candles for each date ...
    if len(candle_info_df) == 0:
        return

    df = candle_info_df
    df = df.drop_duplicates()
    # df_grouped = (  # for example multiple retest on one candle
    #     df.groupby(['date', 'price'], as_index=False)
    #     .agg({'memo': lambda x: ' <br> '.join(x)})
    # )

    df_grouped = (
        df.groupby('date', as_index=False)
        .agg({
            'price': 'min', # we put candle info below the candles ...
            'memo': lambda x: ' <br> '.join(x)
        })
    )

    for index, row in df_grouped.iterrows():
        date = row['date']
        date.strftime('%H:%M')  # just hh:mm from  2025-10-17 10:56:00-04:00
        price = row['price']
        memo = f"{row['memo']} <br> {date.strftime('%H:%M')}"  # adding date to the memo ...

        add_to_signlas(symbol, "CANDLE_INFO", price, date, memo)  #

    return

def add_to_candle_info_df(date, price, memo):
    global candle_info_df

    data = {
        'date': date,
        'price': price,
        'memo': memo
    }
    candle_info_df = pd.concat([candle_info_df, pd.DataFrame([data])])

    return


def no_failure_after_breakout(side='up', level=0, ohlc_field='open'):
    # we want make sure all closes after breakout are above the level.
    # for up, use 'open'
    # for down use 'close'


    if breakout_idx == 0:
        return False

    i = -1 # the last candle
    j = breakout_idx # This is index for breakout...

    if j == i:
        return  False

    start, end = sorted([i, j])  # in case you mix order
    # say start -5 end -3.  this get -5, -4, -3, -2.  it mean both -5 and -3 is included too.
    if side == 'up':
        if (df.iloc[start:][ohlc_field] > level).all(): # all highs are above level
            return True
    else:
        if (df.iloc[start:][ohlc_field] < level).all(): # all opens are less then elvel
            return True

    return False


def load_application_state_from_file():
    global application_state
    file_path = application_state_file_path
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r') as f:
                logger.info(f"loading from file_path: {file_path} ")
                application_state = json.load(f)
            logger.info(f"loaded, application_state: {application_state}")
        except Exception as e:
            logger.error(f"@@@@ error in loading file: {file_path}")
            application_state = {}

    return

# ###########
# START BACK TEST
# ############
def get_current_price_from_ib(symbol, max_retries=3, retry_delay=0.5):

    underlying = Stock(symbol, 'SMART', 'USD')
    for attempt in range(1, max_retries + 1):

        ib.qualifyContracts(underlying)
        ticker = ib.reqMktData(underlying)
        ib.sleep(0.2)
        price = ticker.last or ticker.close
        if price is not None and not (pd.isna(price) or math.isnan(price)):
            return price
        else:
            logger.warning(f"@@@ get_current_price_from_ib,{symbol}, price is nan, try again ... attempt: {attempt}")
            time.sleep(retry_delay)
    return price

def get_historical_data_from_start_date(contract, historical_days, time_frame, start_date):
    # calculate end date (20 days ago)
    # end_date = datetime.datetime.now() - datetime.timedelta(days=10)
    # end_date_str = end_date.strftime('%Y%m%d %H:%M:%S')

    bars = ib.reqHistoricalData(
        contract,
        endDateTime=start_date,
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

    logger.info(f"get_historical_data_from_start_date, {contract.symbol} ,df['date'].min(): {df['date'].min()}, df['date'].max(): {df['date'].max()}")
    return df


def get_historical_data_back_test(contract, start_date='2025-09-01', historical_days='', time_frame='1 min'):
    """
    Fetch historical data in chunks (e.g. 10-day periods) until today.
    """

    start = datetime.datetime.strptime(str(start_date), "%Y-%m-%d")


    today = datetime.datetime.now()
    df = pd.DataFrame()
    while start < today:
        end = start + datetime.timedelta(days=5)
        if end > today:
            end = today
            start_date_time = '' # leave it to empty as we want to get latest ...
        else:
            start_date_time = start.strftime("%Y%m%d %H:%M:%S")

        logger.info(f"start: {start}, end: {end} , historical_days:{historical_days}")
        # Call your inner function
        tmp_df = get_historical_data_from_start_date(
            contract=contract,
            historical_days=historical_days,
            time_frame=time_frame,
            start_date=start_date_time
        )
        if len(tmp_df)> 0:
            df = pd.concat([df,tmp_df])
        # Move start pointer forward
        start = end
    return df


def find_index(df, start="09:30" ):
    """
    Return the high between start and end time for the current day.
    Only calculates if the latest candle is past end time.
    """
    # ensure datetime
    df['date'] = pd.to_datetime(df['date'])

    # get current day from latest row
    current_day = df['date'].dt.date.max()

    # check if we passed the end time
    start_time = pd.to_datetime(start).time()
    mask = (
            (df['date'].dt.date == current_day) &
            (df['date'].dt.time >= start_time)
    )
    if mask.any():
        return df.loc[mask].index[0]
    else:
        return -1




def cut_df_until_x_days_ago(df, days_ago=0):
    """
    Cut DataFrame up to a certain number of days ago based on df['date'].

    Parameters:
        df : pd.DataFrame
        days_ago : int
            How many days ago to cut (0 = last day, 1 = day before last, etc.)

    Returns:
        pd.DataFrame : sliced DataFrame
    """
    # Ensure the 'date' column is datetime
    df['date'] = pd.to_datetime(df['date'])

    # Normalize to remove time
    dates = df['date'].dt.normalize()

    # Get sorted unique days
    unique_days = sorted(dates.unique())

    if days_ago >= len(unique_days):
        raise ValueError("days_ago is greater than the number of days in the DataFrame")

    # Pick the cut-off day
    cut_day = unique_days[-(days_ago + 1)]

    # Return rows up to that day
    return df[dates <= cut_day]


def cut_df_until_date(df, cutoff_date):
    """
    Cut DataFrame up to and including a specific calendar date.
    Handles timezone-aware datetimes safely.

    Parameters:
        df : pd.DataFrame
            Must contain a 'date' column (datetime or string).
        cutoff_date : str or datetime
            The last date (inclusive) to keep, e.g. '2025-08-30'.

    Returns:
        pd.DataFrame : sliced DataFrame up to cutoff_date (inclusive).
    """
    df = df.copy()
    df['date'] = pd.to_datetime(df['date'], utc=False, errors='coerce')

    # If df['date'] has timezone, align cutoff_date to the same tz
    cutoff_date = pd.to_datetime(cutoff_date).normalize()
    if hasattr(df['date'].dt, 'tz') and df['date'].dt.tz is not None:
        cutoff_date = cutoff_date.tz_localize(df['date'].dt.tz)

    # Compare safely (normalize removes time)
    df_dates = df['date'].dt.normalize()

    return df[df_dates <= cutoff_date]

def cut_df_strating_hour_x_on_last_day(df, cutoff_time="13:00"):
    df = df.copy()
    df['date'] = pd.to_datetime(df['date'])

    # Find the last trading day in the DataFrame
    last_day = df['date'].dt.normalize().max()

    # Create masks
    mask_time = df['date'].dt.time >= pd.to_datetime(cutoff_time).time()
    mask_day = df['date'].dt.normalize() == last_day

    # Keep everything aftere that cutoff on the last day, and all prior days
    cut_df = df[(mask_day & mask_time)]
    return cut_df

def cut_df_until_hour_x_on_last_day(df, cutoff_time="13:00"):
    """
    Cut the DataFrame up to (and including) a specific time on the last day in df['date'].

    Parameters:
        df : pd.DataFrame
            Must contain a 'date' column of datetime type.
        cutoff_time : str
            Time in HH:MM (24-hour) format. Default is '13:00'.

    Returns:
        pd.DataFrame : sliced DataFrame up to cutoff_time of the last day.
    """
    df = df.copy()
    df['date'] = pd.to_datetime(df['date'])

    # Find the last trading day in the DataFrame
    last_day = df['date'].dt.normalize().max()

    # Create masks
    mask_day = df['date'].dt.normalize() == last_day
    mask_time = df['date'].dt.time <= pd.to_datetime(cutoff_time).time()

    # Keep everything before that cutoff on the last day, and all prior days
    cut_df = df[(df['date'].dt.normalize() < last_day) | (mask_day & mask_time)]
    return cut_df

def get_back_test_data():   # get data from IB.... use
    global ib
    if app_config['back_test']['get_data_from_ib']: # if we need to go ti IB
        ib = create_ib_connection()

        historical_days = app_config['back_test']['historical_days']
        start_date = app_config['back_test']['start_date']

        for symbol in app_config['symbols']:
            contract = create_equity_contract(symbol)

            df = get_historical_data_back_test(contract, start_date=start_date, historical_days=historical_days, time_frame='1 min')
            df = df.drop_duplicates(subset=[f'date'], keep=f'last')
            df = df.sort_values(by='date')
            logger.info(f"{symbol}, get_back_test_data, df['date'].min(): {df['date'].min()}, df['date'].max(): {df['date'].max()}")
            file = os.path.join(backtest_ohlc_dir, f'{symbol}-1min.csv')
            logger.info(f"saving to file: {file}")
            if os.path.exists(file):  # load file and merge with new one ...
                logger.info(f"File {file} exists... loading it ...")
                existing_df = pd.read_csv(file)
                if len(existing_df) > 0:
                    existing_df['date'] = pd.to_datetime(existing_df['date'])
                    df = pd.concat([df, existing_df])
                    df = df.sort_values(by='date')
                    df = df.drop_duplicates(subset=[f'date'], keep=f'last')
            logger.info(f"saving df ....")
            df.to_csv(file, index=False)
            logger.info(f"saving done ....")

    return



def cut_df_starting_x_days_ago(df, days=5):
    last_date = df['date'].max()

    cutoff = last_date - datetime.timedelta(days=days)

    df = df[df['date'] >= cutoff]
    return df


# ###########
# END BACK TEST
# ############

# ############
# Start IB sending order - only for live
# ###########
def flatten(obj, prefix=''):
    """
    Recursively flatten an object (like Fill, Execution, CommissionReport) into a dict.
    """
    result = {}
    for attr in dir(obj):
        if attr.startswith('_') or callable(getattr(obj, attr)):
            continue
        value = getattr(obj, attr)
        if hasattr(value, '__dict__'):
            # nested object → recurse
            result.update(flatten(value, prefix=f'{prefix}{attr}_'))
        else:
            result[f'{prefix}{attr}'] = value
    return result



def send_order(contract, total_quantity=1):
    order = MarketOrder('BUY', totalQuantity=total_quantity)
    order_ref = f"OPEN-{symbol}-{unique_run_number}"
    order.orderRef = order_ref
    trade = ib.placeOrder(contract, order)
    # TODO convert to ib df
    trade.fillEvent += ib_utils.on_fill
    ib.sleep(1)
    logger.warning(f"Order sent ....")
    logger.warning(f"@@ trade: {trade}")
    return


def find_expiration_and_strikes(symbol):
    global options_meta_date_dic

    underlying = Stock(symbol, 'SMART', 'USD')
    ib.qualifyContracts(underlying)

    logger.info(f"underlying: {underlying}")

    #  Request all option chains for this symbol
    chains = ib.reqSecDefOptParams(symbol, '', 'STK', underlying.conId)

    # Look at what's available
    # for chain in chains:
    #     logger.info(f"Exchange:{chain.exchange}")
    #     logger.info(f"Trading class:{chain.tradingClass}")
    #     logger.info(f"Expirations:{sorted(chain.expirations)}")
    #     logger.info(f"Strikes (sample):{sorted(chain.strikes)[:10]}")
    #     logger.info("----------")

    #Go through each c in chains and give me the first one whose exchange equals 'SMART'.”
    chain = next(c for c in chains if c.exchange == 'SMART')
    expiry = sorted(chain.expirations)[0].replace('-', '')
    strikes = sorted(chain.strikes)
    options_meta_date_dic[symbol] = {}
    options_meta_date_dic.get(symbol)['expiry'] = expiry
    options_meta_date_dic.get(symbol)['strikes'] = strikes
    return

def create_option_contract(strike, expiry, right, exchange="CBOE", symbol='SPX', trading_class='SPXW', max_retries=2, wait_between=1.0):
    contracts = []
    # put in the loop
    contract = Option(
        symbol=symbol,
        lastTradeDateOrContractMonth=expiry,
        strike=strike,
        right=right,
        exchange=exchange,
        tradingClass=trading_class
    )
    contracts.append(contract)

    for attempt in range(0, max_retries):

        logger.info(f"calling qualifyContracts : ")
        qualified = ib.qualifyContracts(contract)
        logger.info("qualifyContracts is done.")

        if qualified:
            return contract
        else:
            logger.warning(f"@@@@ Contract not found, qualified: {qualified}, will retry ...")

        time.sleep(wait_between)

    return None
def calculate_number_of_contracts(ask):
    capital = app_config['live']['capital']
    capital_per_trade_percentage = app_config['live']['capital_per_trade_percentage']
    max_num_open_trades = app_config['live']['max_num_open_trades']

    # 4000 * 0.2 = 800.00  if the ask = 1,  quantitiy:  8  =  800/( 100  contract * 1 ask)
    #  num_of_contracts: 4
    logger.info(f"calculate_number_of_contracts(), capital: {capital}, capital_per_trade_percentage: {capital_per_trade_percentage}, max_num_open_trades: {max_num_open_trades}")

    capital_per_trade = capital * capital_per_trade_percentage
    num_of_contracts = round(capital_per_trade / (ask * 100))

    logger.info(f"capital_per_trade: {capital_per_trade}, ask: {ask}")
    logger.info(f"symbol: {symbol}, num_of_contracts: {num_of_contracts}")
    if num_of_contracts == 0:
        logger.warning(f"@@@@ we dont have enough capital ...")

    return num_of_contracts
def prepare_contract(symbol, right='C', max_retries=3, wait_between=1.0):

    underlying_price = get_current_price_from_ib(symbol)
    strikes = options_meta_date_dic.get(symbol, {}).get('strikes')
    expiry = options_meta_date_dic.get(symbol, {}).get('expiry')

    # --- Categorize ---
    itm_calls = [s for s in strikes if s < underlying_price]
    otm_calls = [s for s in strikes if s > underlying_price]
    itm_puts = [s for s in strikes if s > underlying_price]
    otm_puts = [s for s in strikes if s < underlying_price]
    if len(otm_calls) !=0 and len(otm_puts) != 0:
        if right == 'C':
            strike = otm_calls[0]
        else:
            strike = otm_puts[-1]

        contract = create_option_contract(strike=strike, expiry=expiry, right=right,exchange="SMART", symbol=symbol, trading_class='')
        logger.info(f"in prepare_contract, contract: {contract}")


        return contract

    else:
        logger.error (f"@@@@ prepare_contract(), we have issue, {symbol}, underlying_price: {underlying_price}, expiry: {expiry}, strikes: {strikes}")

        # TODO log the error
        #   File "C:\Users\saeed\Documents\13-code-git\s349_scarface_strategy\scripts\screening.py", line 2202, in <module>
        #     check_buy_sell_result_to_send_order(buy_sell_case_results_list)
        #   File "C:\Users\saeed\Documents\13-code-git\s349_scarface_strategy\scripts\screening.py", line 1525, in check_buy_sell_result_to_send_order
        #     option_contract = prepare_contract(symbol, right='C')
        #                       ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
        #   File "C:\Users\saeed\Documents\13-code-git\s349_scarface_strategy\scripts\screening.py", line 1486, in prepare_contract
        #     strike = otm_calls[0]
        #              ~~~~~~~~~^^^
        # IndexError: list index out of range
        return None


def number_of_trades_today(symbol):
    number_of_trades_today = application_state.get('number_of_trades', {}).get(date_yyyymmdd,{}).get(symbol,0)
    return number_of_trades_today

def add_to_number_of_trades_today(symbol):
    global application_state
    current_number = number_of_trades_today(symbol)
    if current_number == 0:
        application_state.setdefault('number_of_trades', {}).setdefault(date_yyyymmdd, {})[symbol] = 1
    else:
        application_state.setdefault('number_of_trades', {})[date_yyyymmdd][symbol] += 1
    return

def check_buy_sell_result_to_send_order(buy_sell_case_results_list):
    global  application_state

    for buy_sell_case_result in buy_sell_case_results_list:

        logger.debug(f"buy_sell_case_result: {buy_sell_case_result} , type(buy_sell_case_result): {type(buy_sell_case_result)}")
        case = buy_sell_case_result[0]
        can_buy = buy_sell_case_result[1]
        can_sell = buy_sell_case_result[2]
        case_result = buy_sell_case_result[3]
        long_level = buy_sell_case_result[4]
        short_level = buy_sell_case_result[5]
        level_used = long_level if can_buy else short_level

        logger.info(f"case: {case}, can_buy: {can_buy}, can_sell: {can_sell}")
        if symbol == 'MNQ' and (can_buy or can_sell):
            # create a new Thread for calling TopStep
            # side = 'BUY' if can_buy else 'SELL'
            # t = threading.Thread(target=call_api_top_step, args=(symbol, side))
            # t.start()
            continue
        if not app_config['symbols_meta'][symbol]['can_trade']:
            logger.info(f"We are not trading {symbol}.")
            continue
        if can_buy or can_sell:
            side = 'C' if can_buy else 'P'
            logger.info(f"in check_buy_sell_result_to_send_order, {symbol}, can_buy: {can_buy}, can_sell:{can_sell}")
            if application_state.get('open_trades_dic', {}).get(symbol,{}).get('available_quantity', 0) != 0:
                continue
            option_contract = prepare_contract(symbol, right=side)
            if option_contract == None:
                logger.warning(f"@@@ We are not sending order. option_contract: {option_contract}")
                continue
            bid, ask = get_quote_for_option_bid_ask(symbol=symbol, strike=option_contract.strike, right=option_contract.right, expiry=option_contract.lastTradeDateOrContractMonth)
            if bid ==0 or ask ==0:
                logger.warning(f"@@@@ We are not sending order. bid ==0 or ask ==0")
                continue
            total_quantity = calculate_number_of_contracts(ask)
            if total_quantity == 0:  # we dont have enough capital
                logger.warning(f"@@ We dont have enough capital {symbol} ....")
                continue
            if number_of_trades_today(symbol) >= app_config['live']['max_num_of_trade_per_symbol_per_day']:
                logger.warning(f"@@  We already send enough orders ..{symbol} ....number_of_trades_today{number_of_trades_today(symbol)}")
                continue
            send_order(option_contract, total_quantity=total_quantity)
            data = {
                'symbol' : symbol,
                'side': 'long',
                'right': side,
                'starting_quantity':total_quantity,
                'available_quantity':total_quantity,
                'underlying_open_price': df['close'].iloc[-1] ,
                'u_run_number': unique_run_number,
                'level_used_to_open': level_used,
                'level_name': '',
                'expiry': option_contract.lastTradeDateOrContractMonth,
                'strike': option_contract.strike,
                'open_bid': bid,
                'open_ask': ask
            }
            application_state.setdefault('open_trades_dic', {})[symbol] = data
            add_to_signlas(symbol, f'ORDER_SENT',df['close'].iloc[-1],df['date'].iloc[-1], json.dumps(data).replace(',','<br>') )
            add_to_order_history_df(data)
            add_to_number_of_trades_today(symbol)
            send_email(event='order_sent', symbol=symbol, body=json.dumps(data).replace(',','<br>'))

    return


def add_to_order_history_df(data):
    global order_history_df
    order_history_df = pd.concat([order_history_df, pd.DataFrame([data])])

    return


def add_to_take_profit_history_df(data):
    global take_profit_history_df
    take_profit_history_df = pd.concat([take_profit_history_df, pd.DataFrame([data])])

    return


def add_to_stop_loss_history_df(data):
    global stop_loss_history_df
    stop_loss_history_df = pd.concat([stop_loss_history_df, pd.DataFrame([data])])

    return


def dump_application_state_to_file():
    file_path = application_state_file_path
    with open(file_path, 'w') as f:
        try:
            logger.info(f"saving at file_path: {file_path}")
            json.dump(application_state, f, indent=4)
            logger.info(f"saving done. ")
        except Exception as e:
            # TODO add
            logger.error(e)
    return

def print_application_state(application_state, msg = ''):
    logger.warning(f"{msg}\n{pprint.pformat(application_state)}")
    return

def find_expiration_and_strikes_for_all():
    for symbol in app_config['symbols']:
        if app_config['symbols_meta'][symbol]['contract_type'] == 'Equity':
            find_expiration_and_strikes(symbol)
    return

def popualate_features(df):
    period = 14
    atr_df = pd.DataFrame()
    atr_df[f'atr_{period}'] = TA.ATR(df, 14)
    features_list = [df, atr_df]

    df = pd.concat(features_list, axis=1)
    return df

def get_quote_for_option_bid_ask(symbol, strike, right, expiry, exchange='SMART',max_retries=3, wait_between=1.0 ):
    option = Option(
        symbol=symbol,
        lastTradeDateOrContractMonth=expiry,
        strike=strike,
        right=right,
        exchange=exchange
    )
    bid = ask = 0

    for attempt in range(1, max_retries + 1):
        ticker = ib.reqMktData(option, snapshot=True)
        ib.sleep(0.2)  # Give IB a moment to return data

        bid = ticker.bid  if ticker.bid > 0 else 0
        ask = ticker.ask  if ticker.ask > 0 else 0
        last = ticker.last if ticker.last > 0 else 0
        logger.info(f"get_quote_for_option_bid_ask, bid: {bid}, ask:{ask}")
        if bid == 0 or ask == 0:
            logger.warning(f"@@@ get_quote_for_option_bid_ask(), {symbol}, bid: {bid}, ask:{ask}, option: {option}")
            time.sleep(wait_between)
        else:
            return bid, ask

    return bid, ask

def get_live_quote_for_option_positions(option_positions):
    portfolio_df = pd.DataFrame()
    for p in option_positions:
        contract = p.contract
        contract.exchange = 'CBOE'  # TODO why not smart!
        ticker = ib.reqMktData(contract, '', False, False)
        ib.sleep(0.3)  # short wait for data
        logger.info(f"{contract.symbol} {contract.lastTradeDateOrContractMonth} "
              f"{contract.right} {contract.strike} | "
              f"Bid: {ticker.bid}, Ask: {ticker.ask}, Last: {ticker.last}")
        qty = p.position
        data = {
            'conId': contract.conId,
            'symbol': contract.symbol,
            'localSymbol': contract.localSymbol,
            'expiry': contract.lastTradeDateOrContractMonth,
            'right': contract.right,
            'open_qty': abs(qty),
            'strike': contract.strike,
            'side': 'long' if qty > 0 else 'short',
            'bid': ticker.bid if ticker.bid > 0 else 0,
            'ask': ticker.ask if ticker.ask > 0 else 0,
            'last': ticker.last,
            'open_execution_price': 0,
            'open_execution_orderRef': '',
            'open_execution_execId': ''
        }
        portfolio_df = pd.concat([portfolio_df, pd.DataFrame([data])], ignore_index=True)

    logger.info(f"get_live_quote_for_option_positions(), portfolio_df:\n {portfolio_df.to_markdown()}")
    return portfolio_df

def get_bid_and_ask(df, symbol):
    if len(df) == 0:
        return -1, -1
    rows = df.loc[df['symbol'] == symbol]
    if rows.empty:
        return -1, -1  # symbol not found
    row = rows.iloc[0]
    bid = row['bid'] if pd.notna(row['bid']) else -1
    ask = row['ask'] if pd.notna(row['ask']) else -1

    return bid, ask


def get_all_open_positions():
    positions = ib.positions()
    logger.info(f"(get_all_open_option_positions(), positions: \n{tabulate(positions, headers='keys', tablefmt='psql')}")
    return positions

def my_tabulate(x):
    try:
        return tabulate(x, headers='keys', tablefmt='psql')
    except Exception as e:
        logger.error(f"e:{e}")
        logger.warning(f" type(x): {type(x)}")
        return "Error in tabular ..."


def find_positions_to_monitor():
    positions = get_all_open_positions()
    logger.info(f"positions_to_monitor: all open: \n{tabulate(positions, headers='keys', tablefmt='psql')}")
    ps = []
    for p in positions:
        logger.debug(f"p: {p}")
        c = p.contract
        if c.secType == 'OPT':
            logger.debug(f"It is an option")
            ps.append(p)

    logger.info(f"find_positions_to_monitor()\n{my_tabulate(ps)}")
    return ps


def close_option_positions(positions, symbol='', close_qty=0, alias_for_ref=''):

    for pos in positions:
        contract = pos.contract
        if close_qty == 0:
            qty = pos.position
        else:
            qty = close_qty

        # if close_qty > abs(qty):
        #     logger.warning(f"@@@@ Trying to close more than ope. so we ignore. close_qty: {close_qty}, qty: {qty}")

        if contract.secType == 'OPT' and qty != 0:
            if symbol != '' and symbol != contract.symbol:
                logger.info(f"We are not closing this symbol: {symbol}, contract.symbol: {contract.symbol}")
                continue

            # --- Step 2: Determine opposite action ---
            action = 'SELL' if qty > 0 else 'BUY'

            # --- Step 3: Create market order to close ---
            qty = abs(qty)

            order = MarketOrder(action, qty)
            if alias_for_ref  == '':
                order_ref = f"CLOSE-{symbol}-{unique_run_number}"
            else:
                order_ref = f"CLOSE-{symbol}-{alias_for_ref}-{unique_run_number}"

            order.orderRef = order_ref

            # --- Step 4: Place the order ---
            contract.exchange = 'SMART'  # or 'CBOE' if your account requires it
            trade = ib.placeOrder(contract, order)
            trade.fillEvent += ib_utils.on_fill
            ib.sleep(0.5)  # small delay to avoid pacing violations

            logger.info(f"close_option_positions(), trade: {trade}")
            # Convert to DataFrame automatically
            df = ib_util.df([trade])

            logger.info(f"close_option_positions, trade:\n{df.to_markdown()}")
            logger.info(f"Closing {contract.localSymbol}, action: {action}, qty: {qty}")

    return


def load_config(path = 'config.yaml') -> dict:
    with open(path, 'r') as file:
        config = yaml.load(file)
    return config

def reload_app_config():
    global app_config
    logger.info('loading config file ....')
    config = load_config(f'{configs_folder}/config-{portfolio_id}.yaml')#['default']
    logger.info('loading config file is done ....')
    app_config = config
    return app_config

def update_config_and_save(config, key, value):
    global app_config
    existing_value = app_config[key]
    if value != existing_value:
        logger.info(f"in update_config_and_save, key: {key}, existing value: {existing_value}, new value: {value} ")
        app_config = reload_app_config()
        app_config[key] = value
        file = f'{configs_folder}/config-{portfolio_id}.yaml'
        with open(file, 'w') as f:  #TODO fix it
            yaml.dump(app_config, f)

    return

def close_all_open_option_positions():
    update_config_and_save(app_config, 'close_all_open_option_positions', False)
    positions_to_monitor = find_positions_to_monitor()
    close_option_positions(positions_to_monitor)



# ##
# This needs to be called once only after trade open ...
# ##
def update_for_avg_cost(positions):
    for position in positions:
        symbol = position.contract.symbol
        if application_state.get('open_trades_dic', {}) != {}:
            if application_state.get('open_trades_dic', {}).get(symbol, {}) != {}: # There is open order ...
                if application_state.get('open_trades_dic', {}).get(symbol, {}).get('avg_cost', 0) == 0:  # only if not set before ...
                    logger.info(f"setting avgCost in {position.avgCost}")
                    application_state['open_trades_dic'][symbol]['avg_cost'] = position.avgCost
                    application_state['open_trades_dic'][symbol]['cost_for_trade'] = position.avgCost * abs(position.position)
                    application_state['open_trades_dic'][symbol]['avg_cost_for_1_position'] = position.avgCost
                    application_state['open_trades_dic'][symbol]['avg_cost_for_1_contract'] =  position.avgCost / 100

    return



def is_next_level_close_a_price_crossed(side='up', level=-1, current_price=-1, underlying_open_price=-1):
    # If price touches next level, we are in 5MH, next lelve is PDH,
    closeness_distance = eval(app_config['closeness_distance'])
    if side == 'up':
        next_level = get_next_level(side, level)
        # next level is > level AND levels are close AND price above the level
        if (next_level > level and  abs(next_level - level) < closeness_distance and # next_level is close
                current_price > next_level and next_level > underlying_open_price) : # price is crossed AND we opened below the next level ...
            return True
    else:
        next_level = get_next_level(side, level)
        if (next_level < level and abs(next_level - level) < closeness_distance and current_price < next_level and
                current_price < next_level and next_level < underlying_open_price):  # price is crossed AND we opened above the next level ...
            return True

    return False
def check_for_stop_loss_and_take_profit():
    global application_state

    for symbol, open_trade_info in application_state.get('open_trades_dic', {}).items():
        logger.info(f"check_for_stop_loss_and_take_profit(), symbol {symbol}" )

        # ###
        # stop loss
        # ###
        if open_trade_info.get('available_quantity', 0) == 0:
            logger.info(f"{symbol}, check_for_stop_loss_and_take_profit(), available_quantity: 0")
            continue
        logger.info(f"in check_for_stop_loss, {symbol} ,\n{pprint.pformat(open_trade_info)}" )

        symbol_df = dfs_map.get(symbol, pd.DataFrame())
        underlying_open_price = float(open_trade_info.get('underlying_open_price', -1))  # used in config ...
        level_used_to_open = float(open_trade_info.get('level_used_to_open', -1)) # used in config ...
        avg_cost_for_1_contract = open_trade_info.get('avg_cost_for_1_contract', -1) # used in config
        right = application_state['open_trades_dic'][symbol]['right'] # used in config
        side = application_state['open_trades_dic'][symbol]['side'] # used in config
        level_used_to_open = application_state['open_trades_dic'][symbol]['level_used_to_open'] # used in config
        tolerance_amount = dynamic_tolerance.get('tolerance', 0)  # used in config

        underlying_current_price = get_current_price_from_ib(symbol) # used in config
        if len(symbol_df) == 0:
            # it maybe first run and we dont have it yet in the dic ...
            underlying_previous_candle_close = underlying_current_price
        else:
            underlying_previous_candle_close = symbol_df['close'].iloc[-2] # used in config


        current_bid, current_ask = get_bid_and_ask(portfolio_df, symbol) #used in config

        # update app status ...
        application_state['open_trades_dic'][symbol]['current_bid'] = current_bid
        application_state['open_trades_dic'][symbol]['current_ask'] = current_ask
        application_state['open_trades_dic'][symbol]['current_value'] = current_ask * application_state['open_trades_dic'][symbol]['starting_quantity'] * 100
        application_state['open_trades_dic'][symbol]['current_pnl'] = application_state['open_trades_dic'][symbol].get('current_value', 0) - application_state['open_trades_dic'][symbol].get('cost_for_trade', 0)


        logger.info(f"level_used_to_open: {level_used_to_open}, underlying_open_price: {underlying_open_price}, "
                    f"underlying_current_price:, {underlying_current_price}, underlying_previous_candle_close: {underlying_previous_candle_close} ,tolerance_amount: {tolerance_amount}")
        logger.info(f"current_bid: {current_bid}, current_ask: {current_ask}, avg_cost_for_1_contract: {avg_cost_for_1_contract}")

        stop_loss_condition = app_config['stop_losses'][right]['stop_loss_condition']
        stop_loss_condition_evaluated = eval(stop_loss_condition)

        logger.info(f"symbol {symbol}, stop_loss_condition: {stop_loss_condition}, stop_loss_condition_evaluated: {stop_loss_condition_evaluated}")

        if stop_loss_condition_evaluated:
            logger.warning("SL condition met ...")
            close_option_positions(positions_to_monitor, symbol, alias_for_ref='SL')
            data = {
                'symbol': symbol,
                'right': application_state['open_trades_dic'][symbol]['right'],
                'strike':  application_state['open_trades_dic'][symbol]['strike'],
                'expiry': application_state['open_trades_dic'][symbol]['expiry'],
                'stop_loss_condition': stop_loss_condition,
                'current_bid': current_bid,
                'current_ask': current_ask,
                'sl_u_run_number': unique_run_number,
                'open_u_run_number': '',
                'sl_order_ref': '',
                'open_order_ref': ''
                }
            add_to_stop_loss_history_df(data)
            add_to_signlas(symbol, 'STOP_LOSS_SENT', df['close'].iloc[-1], df['date'].iloc[-1], f"STOP_LOSS  <BR> {json.dumps(data).replace(',','<br>')}")
            send_email(event='stop_loss_sent', symbol=symbol, body=json.dumps(data).replace(',','<br>'))
            archive_open_trade_dic(symbol, open_trade_info)
            data = {}
            application_state.setdefault('open_trades_dic', {})[symbol] = data  # This need to be ahppened after we get required inf from dic...

        # ###
        # Take profit
        # ###
        for take_profit in app_config['take_profits']:
            logger.info(f"check_for_stop_loss_and_take_profit(), symbol {symbol}, take_profit: {take_profit}")
            if application_state['open_trades_dic'][symbol].get('available_quantity',0) == 0:
                logger.info(f"{symbol}, {take_profit}, check_for_stop_loss_and_take_profit(), available_quantity is 0 ")
                continue
            if application_state['open_trades_dic'][symbol].get('take_profits',{}).get(take_profit,None ) != None:
                logger.info(f"{symbol}, TP already is executed ... {take_profit}")
                continue
            take_profit_condition = app_config['take_profits'][take_profit].get('condition', '1 == 2')
            close_quantity_percentage = app_config['take_profits'][take_profit].get('close_quantity_percentage', 0)

            take_profit_condition_evaluated = eval(take_profit_condition)

            start_quantity = application_state.get('open_trades_dic', {}).get(symbol, {}).get('starting_quantity', 0)
            available_quantity = application_state.get('open_trades_dic', {}).get(symbol, {}).get('available_quantity', 0)

            if close_quantity_percentage == -1: # close all
                close_quantity = available_quantity
            else:
                close_quantity = round(start_quantity * close_quantity_percentage )
                close_quantity = 1 if close_quantity == 0 else close_quantity  # we want to make sure 0.4 * 1 will return 1.

            logger.info(f"available_quantity: {available_quantity}, close_quantity_percentage: {close_quantity_percentage}, close_quantity: {close_quantity}, start_quantity:{start_quantity}")
            logger.info(f"take_profit_condition: {take_profit_condition}, take_profit_condition_evaluated: {take_profit_condition_evaluated}")

            if take_profit_condition_evaluated and available_quantity > 0 and close_quantity != 0 and close_quantity <= available_quantity :
                logger.info(f"Sending TP ...{take_profit}")
                close_option_positions(positions_to_monitor, symbol, close_quantity, alias_for_ref=take_profit)
                application_state['open_trades_dic'][symbol]['available_quantity'] = available_quantity - close_quantity

                data = {
                    'status': 'SENT',
                    'available_quantity_b4_tp' : available_quantity,
                    'close_quantity': close_quantity,
                    'u_run_number': unique_run_number
                }
                application_state['open_trades_dic'][symbol].setdefault('take_profits', {})[take_profit] = data

                data = {
                    'symbol': symbol,
                    'right': application_state['open_trades_dic'][symbol]['right'],
                    'strike': application_state['open_trades_dic'][symbol]['strike'],
                    'expiry': application_state['open_trades_dic'][symbol]['expiry'],
                    'current_bid': current_bid,
                    'current_ask': current_ask,
                    'available_quantity_b4_tp': available_quantity,
                    'take_profit_case': take_profit,
                    'take_profit_condition': take_profit_condition,
                    'close_quantity': close_quantity,
                    'u_run_number': unique_run_number,
                }
                add_to_take_profit_history_df(data)
                add_to_signlas(symbol, 'TAKE_PROFIT_SENT', df['close'].iloc[-1], df['date'].iloc[-1], f"TAKE-PROFIT-{take_profit} <BR>{json.dumps(data).replace(',','<br>')}")
                send_email(event='take_profit_sent', symbol=symbol, body=json.dumps(data).replace(',','<br>'))

            else:
                logger.warning(f"{symbol}. {take_profit} TP condition didn't meet ...  ")


        # check to clean up
        if application_state['open_trades_dic'].get(symbol, {}) != {} and application_state['open_trades_dic'][symbol].get('available_quantity', 0) == 0:
            logger.info(f"{symbol}, the available_quantity is zero, so we set empty dic for it")
            archive_open_trade_dic(symbol, open_trade_info)
            application_state['open_trades_dic'][symbol] = {}

    return

def send_email(event='order_sent', symbol='', subject='', body=''):
    if app_config['email']['send_email']:
        recipients = app_config['email']['recipients']

        if event.lower() == 'order_sent':
            subject = f'Order Sent {symbol}'
            body = (f"Order Sent ... <br> {body}"
                    f"<br>Later more detail will come ...<br>")

        elif event.lower() == 'stop_loss_sent':
            subject = f'Stop Loss {symbol}'
            body = (f"Stop Loss Sent ... <br> {body}"
                    f"<br>Later more detail will come ...<br>")

        elif event.lower() == 'take_profit_sent':
            subject = f'Take Profit {symbol}'
            body = (f"Take Profit Sent ... <br> {body}"
                    f"<br>Later more detail will come ...<br>")

        email_util_ver_02.send_email(recipients, subject=subject, body=body)

    return

def compute_relative_strength(stock_df: pd.DataFrame, qqq_df: pd.DataFrame, period: int = 20):
    # Ensure aligned timeframes
    merged = pd.merge(stock_df[['date', 'close']], qqq_df[['date', 'close']], on='date', suffixes=('_stock', '_qqq'))

    merged['rs_ratio'] = merged['close_stock'] / merged['close_qqq']
    merged['rs_ema'] = merged['rs_ratio'].ewm(span=period, adjust=False).mean()
    merged['rs_roc'] = merged['rs_ema'].pct_change(periods=period)

    merged = merged.fillna(0)
    return merged[['date', 'rs_ratio', 'rs_ema', 'rs_roc']]

def preppare_qqq_df(qqq_df):
    qqq_df = qqq_df[qqq_df['date'].isin(df['date'])]
    qqq_df.reset_index(drop=True, inplace=True)  # reset index start from 0

    return qqq_df


def compute_intraday_rs(stock_df: pd.DataFrame, qqq_df: pd.DataFrame):
    """
    Computes intraday relative strength (RS) of a stock vs QQQ
    anchored at the 9:30 open (regular session open).

    Returns merged DataFrame with:
        - stock_pct: stock % change since 9:30
        - qqq_pct: QQQ % change since 9:30
        - rs_rel: ratio of their changes
        - rs_delta: difference of their changes
    """

    # --- Ensure datetime is parsed ---
    stock_df['date'] = pd.to_datetime(stock_df['date'])
    qqq_df['date'] = pd.to_datetime(qqq_df['date'])

    # --- Find latest trading date ---

    # --- Get 9:30 open prices for that day ---
    def get_930_open(df):
        latest_date = df['date'].dt.date.max()
        mask = (
                (df['date'].dt.date == latest_date) &
                (df['date'].dt.time == pd.Timestamp("09:30").time())
        )
        if not df.loc[mask].empty:
            return df.loc[mask].iloc[0]['open']
        else:
            # Fallback to first bar of session if not exactly 09:30
            logger.warning("@@ get_930_open(), df doe not have open for 9:30.")
            tmp_df = df[df['date'].dt.date == latest_date]
            if len(tmp_df) >0:
                return tmp_df['open'].iloc[-1]
            else:
                logger.warning("@@ get_930_open(), df doe not have open for same day, so we retrun last recrod")
                logger.warning(f"\n{df[-1:].to_markdown()}")
                return 600 # on Sunday night, MNQ is there but QQQ will start on Monday. so no data for Sunday QQQ. so let's return 600
                # TODO

    stock_open = get_930_open(stock_df)
    qqq_open = get_930_open(qqq_df)

    # --- Merge both dataframes on datetime (nearest or exact match) ---
    merged = pd.merge_asof(
        stock_df.sort_values('date'),
        qqq_df.sort_values('date'),
        on='date',
        suffixes=('_stock', '_qqq')
    )

    logger.info(f'stock_open: {stock_open}, qqq_open: {qqq_open}')
    # --- Compute % change from 9:30 anchor ---
    merged['stock_pct'] = merged['close_stock'] / stock_open - 1
    merged['qqq_pct'] = merged['close_qqq'] / qqq_open - 1
    merged['qqq_930'] = qqq_open
    merged['stock_930'] = stock_open

    # --- Relative performance ---

    merged['rs_rel'] = np.where(
        merged['qqq_pct'].abs() > 0.0005,
        merged['stock_pct'] / merged['qqq_pct'],
        np.nan
    ).clip(-10, 10)

    merged['rs_delta'] = merged['stock_pct'] - merged['qqq_pct']

    smooth_span = 3
    merged['rs_rel_ema'] = merged['rs_rel'].ewm(span=smooth_span, adjust=False).mean()
    merged['rs_delta_ema'] = merged['rs_delta'].ewm(span=smooth_span, adjust=False).mean()

    merged['rs_delta'] = merged['stock_pct'] - merged['qqq_pct']

    # Directional filter
    # merged['same_direction'] = np.where("YES",  (
    #                                    (merged['stock_pct'] > 0) & (merged['qqq_pct'] > 0)
    #                            ) | (
    #                                    (merged['stock_pct'] < 0) & (merged['qqq_pct'] < 0)
    #                            ), "NO")
    # , 'same_direction',
    return merged[['date', 'close_stock', 'close_qqq', 'stock_pct', 'qqq_pct', 'rs_rel', 'rs_delta', 'qqq_930', 'stock_930', 'rs_rel_ema', 'rs_delta_ema']]


def call_api_top_step(symbol, side):
    try:
        # app_config['topstep']['session']
        print(" in thread ...")
        url = "https://api.example.com/data"
        params = {"symbol": "AAPL"}
        response = requests.get(url, params=params)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
    except Exception as e:
        # TODO needs better exception handling
        print(f"error: {e}")
        import traceback
        print(f"--------------")
        print(traceback.format_exc())
    return
# ############
# End of IB sending order - only for live
# ###########


def cancel_open_orders(symbol = ''):
    if not app_config['cancel_open_orders_on_start']:
        return
    update_config_and_save(app_config, 'cancel_open_orders_on_start', False)

    open_orders = ib.reqAllOpenOrders()
    # Cancel all open orders
    for order in open_orders:
        logger.info('----')
        logger.warning(f"Canceling open order, order_id: {order.order.orderId}, order: {order}")
        contract = order.contract

        if not isinstance(contract, Option):
            logger.warning(f"it is NOT an option!!!")
        else:
            logger.warning(f"it is an option!!!")
            if symbol != '' and order.contract.symbol != symbol:
                logger.warning(f"in cancel_all_open_orders, not canceling order.contract.symbol: {order.contract.symbol}")
                continue
            else:
                trade = ib.cancelOrder(order.order)
                trade.fillEvent += ib_utils.on_fill

                logger.warning(f"open order canceled, trade: {trade}")
                while not trade.isDone():
                    logger.warning(f"sleep until is done, trade.isDone(): {trade.isDone()}")
                    ib.sleep(0.5)
    return




def check_application_state_vs_positions():
    global application_state
    for symbol, open_trade_info in application_state.get('open_trades_dic', {}).items():
        if open_trade_info.get('available_quantity', 0) != 0:  # There is in the dic
            if len(portfolio_df) >0:
                x_df = portfolio_df[portfolio_df['symbol'] == symbol]
                if len(x_df) == 0:
                    logger.warning(f"@@@@ This symbol exist in the application_state but not in the portfolio_df. symbol:{symbol}")
                    logger.warning(f"@@@@ open_trade_info: {open_trade_info}")
                    logger.warning(f"@@@@ portfolio_df\n{portfolio_df.to_markdown()}")

    return


def write_health_status(log_path=f"{health_status_dir}/health_status.log"):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    message = f"{now} - APPLICATION IS HEALTHY\n"

    with open(log_path, "w", encoding="utf-8") as f:
        f.write(message)

    print(f"✅ Health status written: {message.strip()}")

    return




def is_executed_take_profits(symbol, take_profit_list=[]): # used in config
    for tp in take_profit_list:
        if application_state.get('open_trades_dic',{}).get(symbol,{}).get('take_profits',{}).get(tp, {}) != {}: # it is there
            return True
    return False


def save_list_to_csv(close_pairs, file, mode='w'):
    if len(close_pairs) > 0:
        df = pd.DataFrame(close_pairs, columns=["symbol", "level1", "level2", "memo"])
        # df = df.drop_duplicates(subset=['symbol',"level1", "level2"], keep='last')
        df = df.drop_duplicates(keep='last')
        df.to_csv(file, mode=mode, index=False)
    return


def mark_close_levels(key_levels_list):
    global close_pairs
    closeness_distance = eval(app_config['closeness_distance_for_chart'][mode])

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
        close_pairs.append((symbol, l1, l2, memo ))

    return close_pairs


def are_levels_close_to_each_other_for_case_1(side):
    levels = get_levels_dic()
    closeness_distance = eval(app_config['closeness_distance_for_case_1'])
    result = False
    if side == 'up':
        result = abs(levels['PDH'] - levels['PMH']) < closeness_distance and abs( levels['5MH'] - levels['PDH']) < closeness_distance
    else: # down
        result = abs(levels['PDL'] - levels['PML']) < closeness_distance and abs(levels['5ML'] - levels['PDL']) < closeness_distance

    return result

def save_all_csv_files():
    logger.info(f"save_all_csv_files, start ...")
    save_list_to_csv(close_pairs, file=f'{charts_dir}/13-close_levels_df.csv', mode='w')
    drawing_objects_df_file_path = f"{charts_dir}/10-drawing_objects_df.csv"
    df_utils.save_df_to_csv_a_tabular(drawing_objects_df, file_path=drawing_objects_df_file_path, mode='w')
    key_levels_df_file_path = f"{portfolio_dir}/11-key_levels_df.csv"
    df_utils.save_df_to_csv_a_tabular(key_levels_df, file_path=key_levels_df_file_path, mode='w')
    hover_df_file_path = f"{charts_dir}/12-hover_df.csv"
    df_utils.save_df_to_csv_a_tabular(hover_df, file_path=hover_df_file_path, mode='a')
    order_history_df_file_path = f"{portfolio_dir}/13-order_history_df.csv"
    df_utils.save_df_to_csv_a_tabular(order_history_df, file_path=order_history_df_file_path, mode='a', drop_dupplicates=True)
    stop_loss_history_df_file_path = f"{portfolio_dir}/14-stop_loss_history_df.csv"
    df_utils.save_df_to_csv_a_tabular(stop_loss_history_df, file_path=stop_loss_history_df_file_path, mode='a', drop_dupplicates=True)
    take_profit_history_df_file_path = f"{portfolio_dir}/15-take_profit_history_df.csv"
    df_utils.save_df_to_csv_a_tabular(take_profit_history_df, file_path=take_profit_history_df_file_path, mode='a', drop_dupplicates=True)

    ib_utils.save_ib_dfs(portfolio_dir,ib)
    logger.info(f"save_all_csv_files, finished ...")

if __name__ == "__main__":

    ib_portfolio_df = pd.DataFrame()
    app_config = load_app_config(portfolio_id)

    ib_config = load_ib_config()
    ib = None
    get_back_test_data()

    back_test_date_start = app_config['back_test']['back_test_date_start']
    back_test_date_end = app_config['back_test']['back_test_date_end']

    back_test_dates = pd.date_range(start=back_test_date_start, end=back_test_date_end)

    now = datetime.datetime.now()
    run_date_time = now.strftime("%Y-%m-%d__%H-%M")
    unique_run_number = f"{now.strftime('%Y%m%d-%H%M%S')}"

    # Print each date in YYYY-MM-DD format
    for d in back_test_dates:

        drawing_objects_df = pd.DataFrame()
        hover_df = pd.DataFrame(columns=['symbol', 'time_frame', 'object', 'color', 'date_1', 'price_1', 'date_2', 'price_2', 'memo', 'unique_id'])
        key_levels_df = pd.DataFrame(columns=['symbol', 'time_frame', 'key_level', 'price', 'memo', 'unique_id'])
        close_pairs = []
        back_test_date = d.strftime('%Y-%m-%d')
        logger.info(f"back_test_date: {back_test_date}")
        charts_dir = f'../../portfolios/backtest-charts/{unique_run_number}--{back_test_date}/{portfolio_id}'
        for symbol in app_config['symbols']:
            time_frame = '1min'

            df = pd.read_csv(f'{backtest_ohlc_dir}/{symbol}-{time_frame}.csv')
            df = df.drop_duplicates(subset=[f'date'], keep=f'last') # KEEP IT

            df['date'] = pd.to_datetime(df['date'], utc=True) # bcs of carsh when they change summer time ...
            df['date'] = df['date'].dt.tz_convert('America/New_York')

            if back_test_date == '2025-10-xx':
                logger.info('Stop for debug')


            df_filtered = df[df['date'].dt.strftime("%Y-%m-%d") == back_test_date]
            if len(df_filtered) ==0: # no data so go for next one ....
                logger.warning(f"no data ...{symbol} {d}")
                break
            os.makedirs(charts_dir, exist_ok=True)

            cutoff_date = back_test_date
            df = cut_df_until_date(df, cutoff_date=cutoff_date)

            df = cut_df_starting_x_days_ago(df, days=5) # we want to kieep 5 days until end ...

            df = cut_df_until_hour_x_on_last_day(df, cutoff_time="11:00")
            df.reset_index(drop=True, inplace=True) # reset index start from 0

            df = popualate_features(df)
            orig_df = df.copy()
            for_chart_ohlc_df = df.copy()


            calculate_PDL_PDH(df)
            starting_index = find_index(df, start="09:31")
            four_pm_index = find_index(df, start="12:00")
            last_index = df.index[-1] # four_pm_index

            logger.info(f"starting_index: {starting_index}")


            my_index = starting_index
            run_id = 0
            signals = []
            key_levels_list = [] # we need it here.
            candle_info_df = pd.DataFrame(columns=['date', 'price', 'memo'])
            relative_strength_df = pd.DataFrame()

            orig_qqq_df = pd.read_csv(f'{backtest_ohlc_dir}/QQQ-1min.csv')
            orig_qqq_df['date'] = pd.to_datetime(orig_qqq_df['date'], utc=True) # bcs of carsh when they change summmer time ...
            orig_qqq_df['date'] = orig_qqq_df['date'].dt.tz_convert('America/New_York')
            while my_index < last_index:
                run_id += 1
                start_time = time.time()
                now = datetime.datetime.now()
                logger.info(f"-------------------- {symbol}, run_date_time: {run_date_time}  unique_run_id: {unique_run_number}")
                logger.info(f"------ {symbol} {df['date'].iloc[-1]}, my_index: {my_index}")
                logger.info(f"{symbol}, last row:\n{df[-1:].to_markdown()}")
                up_offset_counter = 0 # this is for hovers on the candles ... need to be renamed ..
                down_offset_counter = 0 # this is for hovers on the candles ... need to be renamed ..
                df = orig_df.iloc[:my_index]

                if df['date'].iloc[-1].strftime('%Y-%m-%d %H:%M') == '2025-10-01 10:04':
                    logger.info('Stop for debug')

                qqq_df = orig_qqq_df.copy()
                # cit it exactly like df
                qqq_df['date'] = pd.to_datetime(qqq_df['date'])
                qqq_df = qqq_df[qqq_df['date'].isin(df['date'])]
                qqq_df.reset_index(drop=True, inplace=True)  # reset index start from 0
                if True:
                    missing_rows_in_qqq_df = df.loc[~df['date'].isin(qqq_df['date'])]
                    logger.warning(f"{missing_rows_in_qqq_df[-10:].to_markdown()}")

                logger.debug(f"df[-2:]: \n{df[-2:].to_markdown()}")
                logger.debug(f"qqq_df[-2:]:\n{qqq_df[-2:].to_markdown()}")
                logger.debug(f"df[:2]: \n{df[:2].to_markdown()}")
                logger.debug(f"qqq_df[:2]: \n{qqq_df[:2].to_markdown()}")

                relative_strength_df = compute_relative_strength(df, qqq_df, period=20)
                intraday_rs_df = compute_intraday_rs(df, qqq_df)
                dynamic_tolerance = atr_tolerance_helper.get_dynamic_tolerance(df, level=0, min_tick=0.01)

                logger.info(f"relative_strength_df:\n{relative_strength_df[-2:].to_markdown()} ")
                if symbol == 'AMD':
                # if symbol == 'NVDA' and back_test_date == '2025-10-14' and df['date'].iloc[-1].strftime('%Y-%m-%d %H:%M:%S') == '2025-10-14 09:42:00':
                    logger.info('Stop for debug')

                my_index += 1


                retest_indices_by_level_set = {}
                break_out_indices_by_level_set = {}
                retest_idx = 0
                breakout_idx = 0

                find_add_PDH_PDL_levels_to_key_levels_df()
                find_add_5MH_5ML_levels_to_key_levels_df()

                key_levels_list = get_key_levels_list()

                buy_sell_case_results_list = check_buy_and_sell_cases()

                add_buy_a_sell_entries_to_signals(buy_sell_case_results_list)

                add_atr_to_candle_info(dynamic_tolerance)
                detect_candle_patterns(df)
                end_time = time.time()

                # sleep_enough()
                # pass
                # break

            # FOR EACH SYMBOL ...
            logger.info(f"signals: {signals}")
            add_candle_info_df_to_signals()
            mark_close_levels(key_levels_list)

            hover_df = convert_signals_to_hover_df(signals)  # for whole symbol ...
            logger.debug(f"hover_df[-3:]: \n{hover_df[-10:].to_markdown()}")

            for_chart_ohlc_df = cut_df_strating_hour_x_on_last_day(for_chart_ohlc_df, cutoff_time="09:15")
            save_ohlc_for_chart(for_chart_ohlc_df)

            extra_features_df = for_chart_ohlc_df.copy()
            extra_features_df = extra_features_df.merge(relative_strength_df, on='date', how='left')
            extra_features_df = extra_features_df.merge(intraday_rs_df, on='date', how='left')
            extra_features_df = cut_df_strating_hour_x_on_last_day(extra_features_df, cutoff_time="09:15")



            file = f"{charts_dir}/{symbol}-{time_frame.replace(' ', '')}-extra_features_df.csv"
            extra_features_df.to_csv(file, index=False)
            write_file_in_tabulate(src_file_path=file, number_of_rows=230)
        # for each date ..
        save_df_to_csv_a_tabular(drawing_objects_df, file_path=f'{charts_dir}/10-drawing_objects_df.csv', mode='w')
        save_df_to_csv_a_tabular(key_levels_df, file_path=f'{portfolio_dir}/11-key_levels_df.csv', mode='w')
        save_df_to_csv_a_tabular(hover_df, file_path=f'{charts_dir}/12-hover_df.csv', mode='w')
        save_list_to_csv(close_pairs, file=f'{charts_dir}/13-close_levels_df.csv', mode='w')

    logger.info("Done!")