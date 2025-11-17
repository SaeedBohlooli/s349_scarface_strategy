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
from tabulate import tabulate
from ruamel.yaml import YAML
sys.path.insert(0, f'../')

from utils import miscutils
from utils import atr_tolerance_helper
from trading_utils import df_utils
from trading_utils import ib_utils
from trading_utils import ib_orders
from trading_utils import ib_pricing
from trading_utils import ib_posttrade
from trading_utils import global_state
from trading_utils import config_utils
from trading_utils import ruamel_confg_util
from trading_utils import email_utils
from trading_utils import check_health_status
from trading_utils import date_utils
from trading_utils import constants
from trading_utils import file_utils

yaml = YAML()
yaml.preserve_quotes = True  # Optional: preserve quotes if any
yaml.width = 1000 # so will not wrap lines in the yaml file


portfolio_id = 'p250'
configs_folder = f'../configs'

mode = 'live'
if mode == 'live':
    dir_alias = ''
    wait_until_end_of_period = True
else:
    dir_alias = '-backtest'
    wait_until_end_of_period = False

portfolio_dir = f'../../portfolios/results/{portfolio_id}{dir_alias}'
ib_dir = f'../../portfolios/ib/{portfolio_id}{dir_alias}'
reports_dir = f'../../portfolios/reports/{portfolio_id}{dir_alias}'
log_dir = f'../../portfolios/logs/{portfolio_id}{dir_alias}/{datetime.datetime.now().strftime("%Y-%m-%d")}'
detailed_log_dir = f'../../portfolios/detailed-logs/{portfolio_id}{dir_alias}'
intermediate_dir = f'../../portfolios/intermediate/{portfolio_id}{dir_alias}'
ohlc_dir = f'../../portfolios/backtest-ohlc/{portfolio_id}{dir_alias}'
charts_dir = f'../../portfolios/charts/{portfolio_id}{dir_alias}'
ohlc_archie_dir = f'../../portfolios/ohlc-archive/{portfolio_id}'

os.makedirs(portfolio_dir, exist_ok=True)
os.makedirs(reports_dir, exist_ok=True)
os.makedirs(log_dir, exist_ok=True)
os.makedirs(detailed_log_dir, exist_ok=True)
os.makedirs(ohlc_dir, exist_ok=True)
os.makedirs(intermediate_dir, exist_ok=True)
os.makedirs(charts_dir, exist_ok=True)
os.makedirs(ohlc_archie_dir, exist_ok=True)


def update_config_and_save(config, key, value):
    global app_config
    existing_value = app_config[key]
    if value != existing_value:
        logger.info(f"in update_config_and_save, key: {key}, existing value: {existing_value}, new value: {value} ")
        app_config = ruamel_confg_util.load_app_config(portfolio_id)
        app_config[key] = value
        file = f'{configs_folder}/config-{portfolio_id}.yaml'
        with open(file, 'w') as f:  #TODO fix it
            yaml.dump(app_config, f)
    return

def load_ib_config():
    file = 'ib-config.yaml'
    logger.warning(f"loading ... {file}")
    app_config = config_utils.load_config(f'{configs_folder}/{file}')
    logger.info(f"loaded ... file")
    return app_config


app_config = config_utils.load_app_config(portfolio_id)
logging_level = app_config['logging_level']
# ###
# Logging setup ..
# ###

log_filename = f"{log_dir}/{portfolio_id}.log"
file_r_handler = logging.handlers.RotatingFileHandler(filename=f"{log_dir}/{portfolio_id}.log", maxBytes= 5 * 1024 * 1024, backupCount=200)
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
os.makedirs(ohlc_archie_dir, exist_ok=True)

application_state_file_path = f'{intermediate_dir}/84-application_state.csv'


def get_previous_bday():
    prev_day = (pd.Timestamp.today() - BDay(1)).normalize()
    return prev_day

def create_ib_connection():
    ib = ib_utils.create_ib_connection(ib_config['ip'], ib_config['port'], client_id=ib_config['client_id'])
    ib.commissionReportEvent += ib_posttrade.on_commission_report
    ib.updatePortfolioEvent += ib_posttrade.on_portfolio_update
    ib.errorEvent += ib_posttrade.on_error

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
    contract = create_contract(symbol) # todo FOR MNQ ...

    df = get_historical_data(contract, historical_days, time_frame)

    logger.info(f"in get_market_data, start: \n{df[:2].to_markdown()}")
    logger.info(f"in get_market_data, end: \n{df[-2:].to_markdown()}")
    return df


def save_ohlc_for_chart(df):
    logger.info(f"in save_ohlc_for_chart, symbol: {symbol}, len(df): {len(df)}")
    if mode == 'live':
        df = df[['date','open', 'high', 'low', 'close', 'volume', 'atr_14']]

    file = f"{charts_dir}/{symbol}-{time_frame.replace(' ', '')}.csv"
    df.to_csv(file, index=False, mode='w')
    return

def save_ohlc_tabluar_for_chart():
    file = f"{charts_dir}/{symbol}-{time_frame.replace(' ', '')}.csv" # TODO duplicate ...
    df_utils.write_file_in_tabulate(file)
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
    if symbol == 'MNQ' and day_of_week == 'Monday':  # the -1 goes to Sunday, so go to Friday
        # TODO how about if we have
        prev_day = unique_days[-3]



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
    # global run_spend_time
    run_spend_time = round(end_time - start_time, 2)
    if is_trade_time:
        logger.warning(f' ==================== run_number: {run_number}, date_run_number: {date_run_number}, run_spend_time: {run_spend_time} seconds, no sleep ...')
    else:
        run_should_take = app_config['run_should_take_seconds']
        need_sleep_seconds = 0
        if run_spend_time < run_should_take:
            need_sleep_seconds = run_should_take - run_spend_time
        logger.warning(f' ==================== run_number: {run_number}, date_run_number: {date_run_number}, run_spend_time: {run_spend_time}, run_should_take: {run_should_take}, so sleep ...')
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
    if symbol == 'PLTR':
        logger.debug('for holding debug')
    # get current day from latest row
    current_day = df['date'].dt.date.max()

    # check if we passed the end time
    latest_time = df['date'].max().time()
    end_time = pd.to_datetime(end).time()
    start_time = pd.to_datetime(start).time()
#  (df['date'].dt.date == current_day) &
    if latest_time > end_time or not wait_until_end_of_period:
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

# def add_to_key_levels_dic(level, memo):
#     global key_levels_dic
#     if level != -1:
#         key_levels_dic[level] = (memo)
#     return


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

# def add_test_key_levels():
#     section = app_config.get('test', {})  # or loop through multiple sections later
#     levels = section.get('levels', {})
#
#     if levels:  # only run if levels exist
#         for key_level, level_data in levels.items():
#             symbol = level_data['symbol']
#             price = level_data['price']
#             memo = level_data.get('memo', '')
#
#             add_to_key_levels_df(
#                 symbol=symbol,
#                 time_frame='1 min',
#                 key_level_name=key_level,
#                 price=price,
#                 memo=memo
#             )
#             add_to_drawing_objects_df(symbol=symbol, time_frame=time_frame, object='dot', color='Black',
#                                       price_1=price, memo=f'{memo}',
#                                       unique_id=f'{symbol}-{time_frame}-{key_level}')

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


    low_for_5_min, high_for_5_min = find_session_high_and_low(df, start="09:30", end="09:34", wait_until_end_of_period= wait_until_end_of_period)
    add_to_drawing_objects_df(symbol=symbol, time_frame=time_frame, object='dot', color='Black', price_1=low_for_5_min, memo=f'5ML {low_for_5_min}', unique_id=f'{symbol}-{time_frame}-5ML')
    add_to_drawing_objects_df(symbol=symbol, time_frame=time_frame, object='dot', color ='Black', price_1=high_for_5_min, memo=f'5MH {high_for_5_min}', unique_id=f'{symbol}-{time_frame}-5MH')
    add_to_key_levels_df(symbol, time_frame, '5ML', low_for_5_min, f'5ML {low_for_5_min}')
    add_to_key_levels_df(symbol, time_frame, '5MH', high_for_5_min, f'5MH {high_for_5_min}')

    return

def find_add_PMH_PML_levels_to_key_levels_df():

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
            add_to_signlas(symbol, f"BUY_ENTRY_{case}", price, df['date'].iloc[-1], f"{case} - {res_str}")

        if can_sell:
            add_to_signlas(symbol, f"SELL_ENTRY_{case}", price, df['date'].iloc[-1], f"{case} - {res_str}")


        # add_to_signlas(symbol,  f"SCREENING_{case}", offseted_price, df['date'].iloc[-1], f'{case} - {res_str}')  #
        price = get_offseted_price('down', df['low'].iloc[-1])
        add_to_candle_info_df(symbol, date=df['date'].iloc[-1], price=price, memo=f'{case} - {res_str}')

    return

def backtest_has_open_position():
    if position == 0:
        return False
    else:
        return  True

def backtest_has_long_position():
    if position == 1:
        return True
    else:
        return  False

def backtest_has_short_position():
    if position == -1:
        return True
    else:
        return  False
def backtest_create_long_position():
    global position
    position = 1
    return

def backtest_create_short_position():
    global position
    position = -1
    return

def backtest_close_position():
    global position
    position = 0
    return


def mark_stop_loss_take_profit_for_futures(buy_sell_case_results_list):
    global screening_log_list

    for buy_sell_case_result in buy_sell_case_results_list:

        logger.debug(f"add_buy_a_sell_entries_to_signals(), buy_sell_case_result: {buy_sell_case_result}")
        # case, can_buy, can_sell, details_map
        case = buy_sell_case_result[0]
        can_buy = buy_sell_case_result[1]
        can_sell = buy_sell_case_result[2]
        result_map = buy_sell_case_result[3]

        res_str = result_map.get('res_str')
        long_level = result_map.get('long_level')
        short_level = result_map.get('short_level')

        if (can_buy or can_sell) : # we want to add SL TP in the chart in BT
            contract_type = app_config['symbols_meta'][symbol]['contract_type']
            side = 'long' if can_buy else 'short'
            right = 'C' if can_buy else 'P'
            level_used = long_level if can_buy else short_level # used in config SL and TP
            if contract_type.lower() == 'future':

                level_used = long_level if can_buy else short_level # used in SL canlcualtion
                stop_loss_price = eval(app_config['symbols_meta'][symbol][side]['stop_loss'])
                take_profit_price = eval(app_config['symbols_meta'][symbol][side]['take_profit'])

                add_to_signlas(symbol, f'STOP_LOSS_SENT', stop_loss_price, df['date'].iloc[-1], f"SL:{round(stop_loss_price,2)}, sl-to-close: {abs(round(df['close'].iloc[-1]- stop_loss_price, 2))}<br> " )
                add_to_signlas(symbol, f'TAKE_PROFIT_SENT', take_profit_price, df['date'].iloc[-1], f"TP:{round(take_profit_price,2)},  tp-to-close: {abs(round(take_profit_price - df['close'].iloc[-1] , 2))}")

    return

def reset_row():
    global df
    df.at[df.index[-1], "position"] = 0
    df.at[df.index[-1], "side"] = ''
    df.at[df.index[-1], "right"] = ''
    df.at[df.index[-1], "open_price"] = 0
    df.at[df.index[-1], "close_price"] = 0
    df.at[df.index[-1], "stop_loss_price"] = 0
    df.at[df.index[-1], "take_profit_price"] = 0


def add_to_screening_log_list(side):
    global  screening_log_list
    data = {
        'symbol': symbol,
        'trade_date': back_test_date,
        'day_of_week': pd.to_datetime(back_test_date).day_name(),
        'date': str(df['date'].iloc[-1]),
        'side': side,
        'open_price': df['open'].iloc[-1],
        'close_price': 0,
        'pnl': 0,
        'entry_time': str(df['date'].iloc[-1]),
        'entry_atr': df['atr_14'].iloc[-1],
        'entry_volume': df['volume'].iloc[-1],
        'entry_volume_ratio': df['VR'].iloc[-1],
        'retest_atr': df['atr_14'].iloc[retest_idx],
        'retest_volume': df['volume'].iloc[retest_idx],
        'retest_volume_ratio': df['VR'].iloc[retest_idx],
        'breakout_atr': df['atr_14'].iloc[breakout_idx],
        'breakout_volume': df['volume'].iloc[breakout_idx],
        'breakout_volume_ratio': df['VR'].iloc[breakout_idx],
        'rs_relative': intraday_rs_df['rs_rel'].iloc[-1],
        'rs_delta': intraday_rs_df['rs_delta'].iloc[-1],
        'exit_time': '',
        'qqq_context':'',
        'memo': f"{app_config['back_test']['memo']} - {app_config['back_test']['runs'][run]['memo']}",
    }
    screening_log_list.append(data)

def do_back_test(buy_sell_case_results_list):
    global df
    global screening_log_list

    if backtest_has_open_position():

        # first we pu them ther,e and then may be overwrite ...
        df.at[df.index[-1], "position"] = df['position'].iloc[-2]
        df.at[df.index[-1], "side"] = df['side'].iloc[-2]
        df.at[df.index[-1], "right"] = df['right'].iloc[-2]
        df.at[df.index[-1], "stop_loss_price"] = df['stop_loss_price'].iloc[-2]
        df.at[df.index[-1], "take_profit_price"] = df['take_profit_price'].iloc[-2]
        df.at[df.index[-1], "open_price"] = df['open_price'].iloc[-2]
        df.at[df.index[-1], "close_price"] = df['close_price'].iloc[-2]
    else: # no open position
        reset_row()

    for buy_sell_case_result in buy_sell_case_results_list:

        logger.debug(f"add_buy_a_sell_entries_to_signals(), buy_sell_case_result: {buy_sell_case_result}")
        # case, can_buy, can_sell, details_map
        case = buy_sell_case_result[0]
        can_buy = buy_sell_case_result[1]
        can_sell = buy_sell_case_result[2]
        result_map = buy_sell_case_result[3]

        res_str = result_map.get('res_str')
        long_level = result_map.get('long_level')
        short_level = result_map.get('short_level')



        if (can_buy or can_sell) : # we want to add SL TP in the chart in BT
            side = 'long' if can_buy else 'short'
            market_trend = 'up' if can_buy else 'down'
            right = 'C' if can_buy else 'P'
            level_used = long_level if can_buy else short_level # used in config SL and TP

            retest_idx = result_map.get('retest_idx')
            breakout_idx = result_map.get('breakout_idx')

            score, score_memo = calculate_score(market_trend)
            offseted_price = get_offseted_price('down', df['low'].iloc[-1]) # we to go down a little bit
            offseted_price = get_offseted_price('down', df['low'].iloc[-1]) # we to go down a little bit
            offseted_price = get_offseted_price('down', df['low'].iloc[-1])
            add_to_signlas(symbol=symbol, event='TEXT', price=offseted_price, date=df['date'].iloc[-1], memo=f'{score_memo}', color='blue')

            if not backtest_has_open_position():
                stop_loss_price = eval(app_config['back_test'][side]['stop_loss'])
                take_profit_price = eval(app_config['back_test'][side]['take_profit'])
                open_price = df['close'].iloc[-1]

                if can_buy:
                    position = 1
                    entry_price = -1
                    backtest_create_long_position()
                    add_to_screening_log_list(side)

                if can_sell :
                    position = -1
                    entry_price = -1
                    backtest_create_short_position()
                    add_to_screening_log_list(side)

                df.at[df.index[-1], "position"] = position
                df.at[df.index[-1], "side"] = side
                df.at[df.index[-1], "right"] = right
                df.at[df.index[-1], "open_price"] = open_price
                df.at[df.index[-1], "stop_loss_price"] = stop_loss_price
                df.at[df.index[-1], "take_profit_price"] = take_profit_price
                add_to_signlas(symbol, 'BACKTEST_STOP_LOSS', stop_loss_price, df['date'].iloc[-1], f'SL @ {stop_loss_price}','Purple')
                add_to_signlas(symbol, 'BACKTEST_TAKE_PROFIT', take_profit_price, df['date'].iloc[-1], f'TP @ {take_profit_price}', 'Purple')

    price = df['close'].iloc[-1]
    stop_loss_price = df['stop_loss_price'].iloc[-1]
    take_profit_price = df['take_profit_price'].iloc[-1]


    if backtest_has_long_position():
        if price <= stop_loss_price:
            backtest_close_position()
            df.at[df.index[-1], 'close_price'] = stop_loss_price
            screening_log_list[-1]['close_price'] = stop_loss_price
            screening_log_list[-1]['pnl'] = (screening_log_list[-1]['close_price'] - screening_log_list[-1]['open_price'])
            add_to_signlas(symbol, 'BACKTEST_CLOSE_POSITION', stop_loss_price, df['date'].iloc[-1], f"close @ {price} - pnl: {round(screening_log_list[-1]['pnl'] , 2)}", 'RED')
        elif price >= take_profit_price:
            backtest_close_position()
            df.at[df.index[-1], 'close_price'] = take_profit_price
            screening_log_list[-1]['close_price'] = take_profit_price
            screening_log_list[-1]['pnl'] = (screening_log_list[-1]['close_price'] - screening_log_list[-1]['open_price'])
            add_to_signlas(symbol, 'BACKTEST_CLOSE_POSITION', take_profit_price, df['date'].iloc[-1], f"close @ {price} - pnl: {round(screening_log_list[-1]['pnl'] , 2)}", 'GREEN')
    elif backtest_has_short_position():
        if price >= stop_loss_price:
            backtest_close_position()
            df.at[df.index[-1], 'close_price'] = stop_loss_price
            screening_log_list[-1]['close_price'] = stop_loss_price
            screening_log_list[-1]['pnl'] = (screening_log_list[-1]['open_price'] - screening_log_list[-1]['close_price'])
            add_to_signlas(symbol, 'BACKTEST_CLOSE_POSITION', stop_loss_price, df['date'].iloc[-1], f"close @ {price} - pnl: {round(screening_log_list[-1]['pnl'] , 2)}", 'RED')

        elif price <= take_profit_price:
            backtest_close_position()
            df.at[df.index[-1], 'close_price'] = take_profit_price
            screening_log_list[-1]['close_price'] = take_profit_price
            screening_log_list[-1]['pnl'] = (screening_log_list[-1]['open_price'] - screening_log_list[-1]['close_price'])
            add_to_signlas(symbol, 'BACKTEST_CLOSE_POSITION', take_profit_price, df['date'].iloc[-1], f"close @ {price} - pnl: {round(screening_log_list[-1]['pnl'] , 2)}", 'GREEN')



    return

def check_buy_and_sell_cases():
    buy_sell_case_results = []

    for case in app_config['cases']:
            # TODO check precondtions here
        res = check_buy_sell_condition(case)
        buy_sell_case_results.append(res)

    return buy_sell_case_results

def get_next_level(side, level):
    if side == 'up':
        next_level = get_levels_map().get('PDH', -1)
    else:
        next_level = get_levels_map().get('PDL', -1)

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
        levels = get_levels_map()  # used in config

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

        logger.info(f"check_buy_sell_condition(), {case}, {symbol}, {can_buy}, {can_sell}")

        long_breakup_idxs = break_out_indices_by_level_set.get(long_level, set())
        long_retest_idxs = retest_indices_by_level_set.get(long_level, set())

        short_breakup_idxs = break_out_indices_by_level_set.get(short_level, set())
        short_retest_idxs = retest_indices_by_level_set.get(short_level, set())




        # This is shown in the chart ..
        res_str = (f"res_{case}:<br>"
                   f"{eval_buy_condition_01}.{eval_buy_condition_02}.{eval_buy_condition_03}|{eval_buy_condition_04}.{eval_buy_condition_05}.{eval_buy_condition_06}|{eval_buy_condition_07}.{eval_buy_condition_08}.{eval_buy_condition_09}|{eval_buy_condition_10} .. {long_breakup_idxs}.{long_retest_idxs} <br>"
                   f"{eval_sell_condition_01}.{eval_sell_condition_02}.{eval_sell_condition_03}|{eval_sell_condition_04}.{eval_sell_condition_05}.{eval_sell_condition_06}|{eval_sell_condition_07}.{eval_sell_condition_08}.{eval_sell_condition_09}.{eval_sell_condition_10} .. {short_breakup_idxs}.{short_retest_idxs} <br>"
                   f"breakout: {breakout_idx}, retest: {retest_idx} <br>"
                   f"{df['date'].iloc[-1].strftime('%H:%M')}")
        res_str = res_str.replace('True', 'T')
        res_str = res_str.replace('False', 'F')

        res_str_log = res_str.replace('<br>', '\n')
        logger.info(f"\nres_str: {res_str_log}")
    except Exception as e:
        logger.error(f"@@ in check_buy_sell_condition: {symbol} {case} error {e}")
        logger.error(traceback.format_exc())
        res_str = f'res_{case}'
    details_map = {
        'can_buy': can_buy,
        'can_sell': can_sell,
        'res_str': res_str,
        'long_level': long_level,
        'short_level': short_level,
        'breakout_idx': breakout_idx,
        'retest_idx': retest_idx
    }
    return case, can_buy, can_sell, details_map

def get_hhm_mm_of_last_record(df=None):
    if df is None or len(df) == 0:
        return "N/A"
    return df['date'].iloc[-1].strftime('%H:%M')

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
    add_to_candle_info_df(symbol, date=df['date'].iloc[-1], price=df['close'].iloc[-1],memo=f'{dynamic_tolerance}')
    return

def dummy_call(level):
    return True

def remove_symbol_from_open_trade_dic(symbol):
    global application_state
    application_state['open_trades_dic'][symbol] = {}
    return

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
                (row["low"] < level and row["close"] > level + gap)    # The price above level + gap
                or (previous["open"] < level and row["close"] > level)  # The prev open is below level and current above the level.
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
    if side == 'up':
        price = price + get_offset_counter(side, add=True) * offset_symbol
    else:
        price = price - get_offset_counter(side, add=True) * offset_symbol
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

def get_levels_map():
    global key_levels_df
    df = key_levels_df
    df['price'] = pd.to_numeric(df['price'], errors='coerce')
    levels = dict(zip(
        df.loc[df['symbol'] == symbol, 'key_level'],
        df.loc[df['symbol'] == symbol, 'price']
    ))
    return levels


def add_to_signlas(symbol, event, price, date, memo='', color=''):

    global signals
    signals.append((symbol, event, price, date, memo, color))

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

        add_to_signlas(symbol, "CANDLE_INFO", price, date, memo)  #

    return

def add_to_candle_info_df(symbol, date, price, memo):
    global candle_info_df

    data = {
        'symbol': symbol,
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

def get_current_price(symbol):
    if app_config['symbols_meta'][symbol]['contract_type'] == 'Equity':
        return ib_pricing.get_current_price_from_ib(ib, symbol)
    elif app_config['symbols_meta'][symbol]['contract_type'] == 'Future':
        contract = create_contract(symbol)
        return ib_pricing.get_current_price(ib, contract)
    else:
        logger.warning(f"@@@@ TODO")
        return None


def get_historical_data_from_start_date(contract, historical_days, time_frame, start_date, max_retries=3, retry_delay=2):
    # calculate end date (20 days ago)
    # end_date = datetime.datetime.now() - datetime.timedelta(days=10)
    # end_date_str = end_date.strftime('%Y%m%d %H:%M:%S')
    for attempt in range(1, max_retries + 1):
        try:
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
            logger.info(f"get_historical_data_from_start_date, start_date: {start_date}, len(df): {len(df)}")

            if time_frame != '1 day':
                 # df["date"]=df["date"].dt.tz_convert(None)
                if df["date"].dt.tz is not None:
                    df["date"] = df["date"].dt.tz_convert(None)
                    df = miscutils.convert_column_timezone(df, 'date', 'date', from_zone='UTC', to_zone='America/New_York')

            logger.info(f"get_historical_data_from_start_date, {contract.symbol}, df['date'].min(): {df['date'].min()}, df['date'].max(): {df['date'].max()}")
            return df
        except Exception as e:
            # TODO add
            logger.error(e)
            logger.warning("we going try again")
            time.sleep(retry_delay)
    # if we are here, means that we could not get data
    return pd.DataFrame()

def get_historical_data_back_test(contract, start_date='2025-09-01', end_date= '', historical_days='', time_frame='1 min'):
    """
    Fetch historical data in chunks (e.g. 10-day periods) until today.
    """

    start = datetime.datetime.strptime(str(start_date), "%Y-%m-%d")
    end_date = datetime.datetime.strptime(str(end_date), "%Y-%m-%d")


    df = pd.DataFrame()
    while start < end_date:
        end = start + datetime.timedelta(days=5)
        if end > end_date:
            end = end_date
            start_date_time = '' # leave it to empty as we want to get latest ...
        else:
            start_date_time = start.strftime("%Y%m%d %H:%M:%S")

        logger.info(f"start: {start}, end: {end}, historical_days:{historical_days}")
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
    if app_config['back_test']['data']['get_data_from_ib']: # if we need to go ti IB
        ib = create_ib_connection()

        historical_days = app_config['back_test']['data']['historical_days']
        start_date = app_config['back_test']['data']['start_date']
        end_date = app_config['back_test']['data']['end_date']

        for symbol in app_config['symbols']:
            contract = create_contract(symbol)

            df = get_historical_data_back_test(contract, start_date=start_date, end_date=end_date,  historical_days=historical_days, time_frame='1 min')
            df = df.drop_duplicates(subset=[f'date'], keep=f'last')
            df = df.sort_values(by='date')
            logger.info(f"{symbol}, get_back_test_data, df['date'].min(): {df['date'].min()}, df['date'].max(): {df['date'].max()}")
            file = os.path.join(ohlc_archie_dir, f'{symbol}-1min.csv')
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

def get_order_ref(event, symbol, alias_for_ref='', unique_run_number=''):
    order_ref = ''
    portofilio_oreder_ref_alias = 'p250'
    if event.lower() == 'open':
        order_ref += f'OP-{portofilio_oreder_ref_alias}-{symbol}'
    else:
        order_ref += f'CL-{portofilio_oreder_ref_alias}-{symbol}'

    if alias_for_ref != '':
        order_ref += f'-{alias_for_ref}'

    if unique_run_number != '':
        order_ref += f'--{unique_run_number}'

    return order_ref

def send_order(contract, total_quantity=1, order_ref='NA'): #TODO move to utils ...
    order = MarketOrder('BUY', totalQuantity=total_quantity)

    order.orderRef = order_ref
    trade = ib.placeOrder(contract, order)
    # TODO convert to ib df
    trade.fillEvent += ib_posttrade.on_fill
    ib.sleep(1)
    logger.warning(f"Order sent ....")
    logger.warning(f"@@ trade: {trade}")
    return


def get_best_option_chain(chains):
    """
    Selects the option chain with the most expirations,
    preferring SMART first, then CBOE variants.
    """
    # Filter only relevant exchanges
    # candidates = [c for c in chains if c.exchange.startswith('SMART') or c.exchange.startswith('CBOE')]
    candidates = [c for c in chains if c.exchange.startswith('SMART')]
    if not candidates:
        return None

    # Pick the one with the most expirations
    best = max(candidates, key=lambda c: len(c.expirations))
    logger.info(f" Using {best.exchange} ({best.tradingClass}) with {len(best.expirations)} expirations")
    return best

def find_expiration_and_strikes(symbol, exchange):
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
    if symbol in ['QQQ', 'SPY']:
        chain = get_best_option_chain(chains) # we choose the one has more
    else:
        chain = next(c for c in chains if c.exchange == 'SMART') # leave it ias is ... go with firsto ne

    expiry = sorted(chain.expirations)[0]
    strikes = sorted(chain.strikes)
    strikes = [s for s in strikes if abs(s * 10 % 5) < 1e-6]  # keeps only .0 and .5 . IB has messy data ...


    options_meta_date_dic[f'{symbol}-strikes'] = strikes
    options_meta_date_dic[f'{symbol}-expirations'] = sorted(chain.expirations)

    if symbol in ['NVDA', 'TSLL']:
        logger.debug('hold it here....')

    if False and not is_trade_time : #TODO need to be m,reoved
        for c in chains:
            if c.exchange == 'SMART':
                options_meta_date_dic.get(symbol)[f'{c.exchange}-expirations'] = sorted(c.expirations)
                options_meta_date_dic.get(symbol)[f'{c.exchange}-strikes'] = sorted(c.strikes)
            if c.exchange == 'CBOE':
                options_meta_date_dic.get(symbol)[f'{c.exchange}-expirations'] = sorted(c.expirations)
                options_meta_date_dic.get(symbol)[f'{c.exchange}-strikes'] = sorted(c.strikes)

    if False:  # TODO need to be rmeoved .
        dump_a_map_to_file(options_meta_date_dic[symbol], file_path=f'{intermediate_dir}/{date_run_number}-{symbol}-strikes-expiry.csv')
    return

def create_option_contract(strike, expiry, right, exchange="CBOE", symbol='SPX', trading_class='SPXW', max_retries=4, wait_between=1.0):
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

    for attempt in range(1, max_retries+1):

        logger.info(f"calling qualifyContracts : ")
        qualified = ib.qualifyContracts(contract)
        logger.info("qualifyContracts is done.")

        if qualified:
            if attempt > 1:
                logger.warning(f"@@ Contract is qualified,  {symbol}, qualified: {qualified}, attempt: {attempt} ")
            return contract
        else:
            logger.warning(f"@@@@ Contract not qualified for {symbol}, qualified: {qualified}, attempt: {attempt}")

        # if attempt > 2:  # try to update expirations and symbols
        #     logger.warning(f"@@@ Let's try to call find_expiration_and_strikes ... attempt: {attempt} ")
        #     exchange = app_config['symbols_meta'][symbol].get('exchange', 'SMART')
        #     find_expiration_and_strikes(symbol, exchange)

        time.sleep(wait_between)

    return None

def calcualte_number_of_open_trades():
    """
    Count open trades across all symbols.
    A trade is considered open if available_quantity > 0.
    """
    open_trades = application_state.get("open_trades_dic", {})
    count = 0

    for symbol, trade in open_trades.items():
        if not trade:  # empty dict → skip
            continue
        if trade.get("available_quantity", 0) > 0:
            count += 1
    return count

def calcualte_availale_capital():
    global application_state

    available_capital = application_state.get('risk', {}).get('available_capital', None)
    if available_capital is None:
       available_capital = app_config['live']['capital']
       application_state.setdefault('risk', {}).setdefault('available_capital', available_capital )
    return available_capital

def calculate_number_of_contracts(strike, ask):
    global application_state

    available_capital = calcualte_availale_capital()

    capital_per_trade_percentage = app_config['live']['capital_per_trade_percentage']
    max_num_open_trades = app_config['live']['max_num_open_trades']

    # 4000 * 0.2 = 800.00  if the ask = 1,  quantitiy:  8  =  800/( 100  contract * 1 ask)
    #  num_of_contracts: 4
    logger.info(f"calculate_number_of_contracts(), {symbol}, available_capital: {available_capital}, capital_per_trade_percentage: {capital_per_trade_percentage}, max_num_open_trades: {max_num_open_trades}")

    capital_per_trade = max(available_capital * capital_per_trade_percentage, 800)  # TODO put in a function
    num_of_contracts = round(capital_per_trade / (ask * 100))

    logger.info(f"capital_per_trade: {capital_per_trade}, ask: {ask} strike: {strike}")
    logger.info(f"symbol: {symbol}, num_of_contracts: {num_of_contracts}")
    if num_of_contracts == 0:
        logger.warning(f"@@@@ we don't have enough capital ...")
    capital_used = num_of_contracts * 100 * ask
    capital_remaining_after_order = available_capital - capital_used
    open_trades_count_at_entry = calcualte_number_of_open_trades()
    # update ...
    application_state.get('risk')['available_capital'] = capital_remaining_after_order

    data = {'symbol': symbol,
            'unique_run_number': unique_run_number,
            'starting_capital': available_capital,
            'allowed_capital_per_trade': capital_per_trade,
            'capital_used': capital_used,
            'capital_remaining_after_order': capital_remaining_after_order,
            'strike': strike,
            'ask': ask,
            'num_of_contracts': num_of_contracts,
            'daily_loss_so_far': 0,
            'daily_win_so_far': 0,
            'open_trades_count_at_entry': open_trades_count_at_entry,
            'memo': '',
            }
    return num_of_contracts, data
def prepare_contract(symbol, right='C', max_retries=3, wait_between=1.0):

    underlying_price = get_current_price(symbol)
    strikes = options_meta_date_dic.get(f'{symbol}-strikes')

    # example: "expirations": [
    #     "20251205",
    #     "20251209",
    #     "20251212"
    # ]
    expiry_offset = app_config['symbols_meta'][symbol].get('expiry_offset', 0) # 0 means first one ... for QQQ/SPY we get the seond one ...

    expiry_list = options_meta_date_dic.get(f'{symbol}-expirations',[])
    expiry = expiry_list[expiry_offset] if expiry_list else None
    if strikes is None:
        logger.warning(f"@@@@@ prepare_contract, strikes is None. {symbol}, {right}, underlying_price: {underlying_price}")
        return  None
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

        return None

    return None

def number_of_trades_today(symbol):
    number_of_trades_today = application_state.get('number_of_trades', {}).get(date_yyyy_mm_dd, {}).get(symbol, 0)
    return number_of_trades_today

def add_to_number_of_trades_today(symbol):
    global application_state
    current_number = number_of_trades_today(symbol)
    if current_number == 0:
        application_state.setdefault('number_of_trades', {}).setdefault(date_yyyy_mm_dd, {})[symbol] = 1
    else:
        application_state.setdefault('number_of_trades', {})[date_yyyy_mm_dd][symbol] += 1
    return

def mark_score_in_the_chart(market_trend):
    score, score_memo = calculate_score(market_trend)
    offseted_price = get_offseted_price('down', df['low'].iloc[-1])  # we to go down a little bit
    offseted_price = get_offseted_price('down', df['low'].iloc[-1])  # we to go down a little bit
    offseted_price = get_offseted_price('down', df['low'].iloc[-1])
    add_to_signlas(symbol=symbol, event='TEXT', price=offseted_price, date=df['date'].iloc[-1], memo=f'{score_memo}', color='blue')
    return


def add_order_ref_to_application_state(open_order_ref='', close_order_ref=''):
    global application_state
    global open_close_refs_df
    if open_order_ref != '' and close_order_ref == '': # this is for open order ...
        application_state.setdefault('open_close_refs_map', {})[open_order_ref] = []
    elif open_order_ref != '' and close_order_ref != '': # this is for close ...
        entry = {open_order_ref: close_order_ref}
        application_state.setdefault('open_close_refs_list', []).append(entry) # add to the list ...

        if  not application_state.get('open_close_refs_map', {}).get(open_order_ref): #  opn is not there,sso add it ..
            application_state.setdefault('open_close_refs_map', {})[open_order_ref] = []

        application_state.get('open_close_refs_map', {}).get(open_order_ref).append(close_order_ref) # now add the close ...
    else:
        logger.info(f"@@@ add_order_ref_to_application_state, is not supported, open_order_ref: {open_order_ref}, close_order_ref: {close_order_ref}")
    data = {
        'open_order_ref': open_order_ref,
        'close_order_ref': close_order_ref,
        'ib_exec_id': ''
    }

    open_close_refs_df = pd.concat([open_close_refs_df, pd.DataFrame([data])])
    return


def check_buy_sell_result_to_send_order(buy_sell_case_results_list):
    global application_state
    global capital_allocation_df

    for buy_sell_case_result in buy_sell_case_results_list:

        logger.debug(f"buy_sell_case_result: {buy_sell_case_result} , type(buy_sell_case_result): {type(buy_sell_case_result)}")
        case = buy_sell_case_result[0]
        can_buy = buy_sell_case_result[1]
        can_sell = buy_sell_case_result[2]
        details_map = buy_sell_case_result[3]
        case_result = details_map.get('res_str')
        long_level = details_map.get('long_level')
        short_level = details_map.get('short_level')
        level_used = long_level if can_buy else short_level
        contract_type = app_config['symbols_meta'][symbol]['contract_type']

        logger.info(f"{symbol}, case: {case}, can_buy: {can_buy}, can_sell: {can_sell}")

        if can_buy == False and can_sell == False: # no sucess ...
            continue
        logger.info(f"check_buy_sell_result_to_send_order, {symbol}, can_buy: {can_buy}, can_sell:{can_sell}")

        if not app_config['symbols_meta'][symbol]['can_trade']:
            logger.info(f"We are not trading {symbol}.")
            continue
        if not is_trade_time:
            logger.warning(f"@@ is_trade_time:{is_trade_time}, {symbol}, {app_config['live']['trade_time']}")
            continue
        if application_state.get('open_trades_dic', {}).get(symbol,{}).get('available_quantity', 0) != 0:
            logger.warning(f"@@ You already have open position. Don't be greedy!!!  symbol: {symbol}")
            continue
        if number_of_trades_today(symbol) >= app_config['live']['max_num_of_trade_per_symbol_per_day']:
            logger.warning(f"@@  We already sent enough orders for {symbol} .... number_of_trades_today: {number_of_trades_today(symbol)}")
            continue

        market_trend = 'up' if can_buy else 'down' #
        mark_score_in_the_chart(market_trend)

        if contract_type.lower() == 'equity' and (can_buy or can_sell): # go for buy
            right = 'C' if can_buy else 'P'
            option_contract = prepare_contract(symbol, right=right)
            if option_contract == None:
                logger.warning(f"@@@@ We are not sending order. {symbol}, option_contract: {option_contract}")
                continue
            bid, ask = get_quote_for_option_bid_ask(symbol=symbol, strike=option_contract.strike, right=option_contract.right, expiry=option_contract.lastTradeDateOrContractMonth)
            if bid == 0 or ask == 0:
                logger.warning(f"@@@@ We are not sending order. bid ==0 or ask ==0")
                continue
            total_quantity, capital_data = calculate_number_of_contracts(option_contract.strike, ask)
            application_state.setdefault('risk', {}).setdefault('records', []).append(capital_data)
            capital_allocation_df = pd.concat([capital_allocation_df, pd.DataFrame([capital_data])])
            if total_quantity == 0:  # we don't have enough capital
                logger.warning(f"@@ We dont have enough capital {symbol} ....")
                continue
            order_ref = get_order_ref('OPEN', symbol, alias_for_ref='', unique_run_number=unique_run_number)
            send_order(option_contract, total_quantity=total_quantity, order_ref= order_ref)
            data = {
                'date': f'{date_utils.time_now()}',
                'symbol': symbol,
                'side': 'long',
                'right': right,
                'starting_quantity':total_quantity,
                'available_quantity':total_quantity,
                'entry_underlying_price': df['close'].iloc[-1] ,
                'entry_bid': bid,
                'entry_ask': ask,
                "current_bid": 0,
                "current_ask": 0,
                "current_underlying_price": 0,
                "current_value": 0,
                "current_pnl": 0,
                "current_roi": 0,
                'unique_run_number': unique_run_number,
                'level_used_to_open': level_used,
                'level_name': '',
                'position_type': 'OPTION',
                'expiry': option_contract.lastTradeDateOrContractMonth,
                'strike': option_contract.strike,
                'local_symbol': option_contract.localSymbol,
                'con_id': option_contract.conId,
                'order_ref': order_ref
            }
            application_state.setdefault('open_trades_dic', {})[symbol] = data
            add_to_signlas(symbol, f'ORDER_SENT',df['close'].iloc[-1],df['date'].iloc[-1], polish_map_to_show_in_hover(data) )
            add_to_order_history_df(data)
            add_to_number_of_trades_today(symbol)
            send_email(event='order_sent', symbol=symbol, body=polish_map_to_show_in_hover(data))
            add_order_ref_to_application_state(open_order_ref=order_ref)

        elif contract_type.lower() == 'future' and (can_buy or can_sell):
            right = 'long' if can_buy else 'short'
            side = 'long' if can_buy else 'short'


            contract_month =  app_config['symbols_meta'][symbol]['contract_month']
            contract = create_contract(symbol)
            stop_loss_price = eval(app_config['symbols_meta'][symbol][side.lower()]['stop_loss'])
            take_profit_price = eval(app_config['symbols_meta'][symbol][side.lower()]['take_profit'])
            total_quantity = 1
            order_ref = get_order_ref('OPEN', symbol, alias_for_ref='', unique_run_number=unique_run_number)
            candle_date = str(df['date'].iloc[-1])
            result_dic = ib_orders.send_market_order_w_sl_tp(ib, side, contract, stop_loss_price, take_profit_price, total_quantity, order_ref, candle_date)

            data = {
                'symbol': symbol,
                'side': side,
                'right': right,
                'position_type': 'FUTURE',
                'starting_quantity':total_quantity,
                'available_quantity':total_quantity,
                'entry_underlying_price': df['close'].iloc[-1],
                'unique_run_number': unique_run_number,
                'level_used_to_open': level_used,
                'level_name': '',
            }
            data.update(result_dic)

            print_map_pretty(data, msg = 'after MNQ order ')

            application_state.setdefault('open_trades_dic', {})[symbol] = data
            add_to_signlas(symbol, f'ORDER_SENT', df['close'].iloc[-1], df['date'].iloc[-1], polish_map_to_show_in_hover(data) )
            add_to_signlas(symbol, f'STOP_LOSS_SENT', stop_loss_price, df['date'].iloc[-1], polish_map_to_show_in_hover(data) )
            add_to_signlas(symbol, f'TAKE_PROFIT_SENT', take_profit_price, df['date'].iloc[-1], polish_map_to_show_in_hover(data) )
            add_to_futures_order_history_df(data)
            add_to_number_of_trades_today(symbol)
            send_email(event='order_sent', symbol=symbol, body=polish_map_to_show_in_hover(data))
            add_order_ref_to_application_state(open_order_ref=order_ref)
            add_order_ref_to_application_state(open_order_ref=order_ref, close_order_ref=f'{order_ref}-TP')  #TODO need to be passed to the send order ...
            add_order_ref_to_application_state(open_order_ref=order_ref, close_order_ref=f'{order_ref}-SL')  #TODO need to be passed to the send order ...

    return

def create_contract(symbol):
    if symbol == 'MNQ':
        contract_month = app_config['symbols_meta'][symbol].get('contract_month', None)
    else:
        contract_month = None
    return ib_pricing.create_equity_contract(symbol, contract_month)


def add_to_order_history_df(data):
    global order_history_df
    order_history_df = pd.concat([order_history_df, pd.DataFrame([data])])

    return

def test_get_bid_ask_for_symbols():
    global bid_ask_history_df
    for symbol in app_config['symbols']:
        for right in ['C', 'P']:
            logger.info(f"---- {symbol} {right}")
            option_contract = prepare_contract(symbol, right=right)
            logger.info(f"test_get_bid_ask_for_symbols ...")
            if option_contract == None:
                logger.warning(f"@@@ test_x. {symbol}, option_contract: {option_contract}")
                continue
            bid, ask = get_quote_for_option_bid_ask(symbol=symbol, strike=option_contract.strike, right=option_contract.right,
                                                    expiry=option_contract.lastTradeDateOrContractMonth)
            data = {'symbol': symbol,
                    'date': date_yyyy_mm_dd_hh_mm,
                    'strike': option_contract.strike,
                    'expiry': option_contract.lastTradeDateOrContractMonth,
                    'right': right,
                    'bid': bid,
                    'ask': ask,
                    'unique_run_number': unique_run_number,
                    }
            bid_ask_history_df = pd.concat([bid_ask_history_df, pd.DataFrame([data])], ignore_index=True)
    return
def add_to_futures_order_history_df(data):
    global futures_order_history_df
    futures_order_history_df = pd.concat([futures_order_history_df, pd.DataFrame([data])])
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

def dump_a_map_to_file(map, file_path):
    with open(file_path, 'w') as f:
        try:
            logger.info(f"saving at file_path: {file_path}")
            json.dump(map, f, indent=4)
            logger.info(f"saving done. ")
        except Exception as e:
            # TODO add
            logger.error(e)
    return

def print_application_state(application_state, msg = ''):
    logger.warning(f"{msg}\n{pprint.pformat(application_state)}")
    return

def print_map_pretty(map, msg = ''):
    logger.warning(f"{msg}\n{pprint.pformat(map)}")
    return

def find_expiration_and_strikes_for_all():
    for symbol in app_config['symbols']:
        if app_config['symbols_meta'][symbol]['contract_type'] in ['Equity']:
            exchange = app_config['symbols_meta'][symbol].get('exchange', 'SMART')
            find_expiration_and_strikes(symbol, exchange)

    return
def populate_volume_ratio(df):
    df['volume_sma10'] = df['volume'].rolling(window=10).mean()
    df['VR'] = df['volume'] / df['volume_sma10']
    cap = df['VR'].quantile(0.95)  # 95th percentile
    df['VR'] = df['VR'].clip(upper=cap)
    df['VR_sma10'] = df['VR'].rolling(window=10).mean()
    return df
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
        logger.info(f"get_quote_for_option_bid_ask, {symbol}, bid: {bid}, ask:{ask}")
        if bid == 0 or ask == 0:
            logger.warning(f"@@@ get_quote_for_option_bid_ask(), retrying ... {symbol}, attempt: {attempt}, bid: {bid}, ask:{ask}, option: {option}")
            time.sleep(wait_between)
        else:
            return bid, ask

    return bid, ask

def get_live_quote_for_option_positions(option_positions):
    options_portfolio_df = pd.DataFrame()
    for p in option_positions:
        contract = p.contract
        symbol = contract.symbol
        if symbol not in app_config['symbols']:
            continue
        contract.exchange = 'CBOE'  # TODO why not smart!
        ticker = ib.reqMktData(contract, '', False, False)   # TODO if the symbol is in our list, why query for SPXW
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
        options_portfolio_df = pd.concat([options_portfolio_df, pd.DataFrame([data])], ignore_index=True)

    logger.info(f"get_live_quote_for_option_positions(), options_portfolio_df:\n {options_portfolio_df.to_markdown()}")
    return options_portfolio_df


def get_live_quote_for_future_positions(future_positions):
    future_portfolio_df = pd.DataFrame()
    for p in future_positions:
        contract = p.contract
        qty = p.position
        data = {
            'conId': contract.conId,
            'symbol': contract.symbol,
            'localSymbol': contract.localSymbol,
            # 'expiry': contract.lastTradeDateOrContractMonth,
            # 'right': contract.right,
            'open_qty': abs(qty),
            # 'strike': contract.strike,
            'side': 'long' if qty > 0 else 'short',
            'bid': 0, # we update it later ...
            'ask': 0, # we update it later ...
            'last': 0, # we update it later ...
            'open_execution_price': 0,
            'open_execution_orderRef': '',
            'open_execution_execId': ''
        }
        future_portfolio_df = pd.concat([future_portfolio_df, pd.DataFrame([data])], ignore_index=True)

    logger.info(f"get_live_quote_for_future_positions(), future_portfolio_df:\n {future_portfolio_df.to_markdown()}")
    return future_portfolio_df

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


def find_option_positions_to_monitor(positions):
    logger.info(f"option_positions_to_monitor: all open: \n{tabulate(positions, headers='keys', tablefmt='psql')}")
    ps = []
    for p in positions:
        logger.debug(f"p: {p}")
        c = p.contract
        if c.secType == 'OPT':
            logger.debug(f"It is an option")
            ps.append(p)

    logger.info(f"find_option_positions_to_monitor()\n{my_tabulate(ps)}")
    return ps

def find_future_positions_to_monitor(positions):
    logger.info(f"find_future_positions_to_monitor(): here are oen positions: \n{tabulate(positions, headers='keys', tablefmt='psql')}")
    ps = []
    for p in positions:
        logger.debug(f"p: {p}")
        c = p.contract
        if c.secType == 'FUT':
            logger.info(f"It is a Future")
            ps.append(p)

    logger.info(f"find_future_positions_to_monitor()\n{my_tabulate(ps)}")
    return ps

#TODO move to utils ...
def close_option_positions(positions, symbol='', close_qty=0, order_ref='Order_Ref'):

    close_qty = int(close_qty)

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

            order.orderRef = order_ref
            order.tif = 'GTC' # if we don't set, will throw errorCode=10349

            # --- Step 4: Place the order ---
            contract.exchange = 'SMART'  # or 'CBOE' if your account requires it
            trade = ib.placeOrder(contract, order)
            trade.fillEvent += ib_posttrade.on_fill
            ib.sleep(0.5)  # small delay to avoid pacing violations

            logger.info(f"close_option_positions(), trade: {trade}")
            # Convert to DataFrame automatically
            df = ib_util.df([trade])

            logger.info(f"close_option_positions, trade:\n{df.to_markdown()}")
            logger.info(f"Closing {contract.localSymbol}, action: {action}, qty: {qty}")

    return


def close_future_positions(positions, symbol='', close_qty=0, order_ref=''):

    for pos in positions:
        contract = pos.contract
        pos_qty = pos.position
        if pos_qty == 0:
            continue

        if symbol != '' and symbol != contract.symbol:
            logger.debug(f"We are not closing this symbol: {symbol}, contract.symbol: {contract.symbol}")
            continue

        if close_qty == 0:
            qty = pos.position
        else:
            qty = close_qty

        # --- Step 2: Determine opposite action ---
        action = 'SELL' if pos_qty > 0 else 'BUY'

        # --- Step 3: Create market order to close ---
        qty = abs(qty)

        order = MarketOrder(action, qty)

        order.orderRef = order_ref

        # --- Step 4: Place the order ---
        contract.exchange = 'CME'  # or 'CBOE' if your account requires it   # CME This is for MNQ.
        trade = ib.placeOrder(contract, order)
        trade.fillEvent += ib_posttrade.on_fill
        ib.sleep(0.5)  # small delay to avoid pacing violations

        logger.info(f"close_future_positions(), trade: {trade}")

        # Convert to DataFrame automatically
        df = ib_util.df([trade])
        logger.info(f"close_future_positions, trade(ib_util.df):\n{df.to_markdown()}")
        logger.info(f"Closing {contract.localSymbol}, action: {action}, qty: {qty}")

    return

def close_all_open_option_positions():
    update_config_and_save(app_config, 'close_all_open_option_positions', False)
    option_positions_to_monitor = find_option_positions_to_monitor()
    close_option_positions(option_positions_to_monitor)


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

                    application_state['open_trades_dic'][symbol]['cost_for_trade'] = round(position.avgCost * abs(position.position), 3)
                    application_state['open_trades_dic'][symbol]['avg_cost_for_1_position'] = round(position.avgCost, 3)
                    application_state['open_trades_dic'][symbol]['avg_cost_for_1_contract'] = round(position.avgCost / 100, 3)

    return


# def is_next_level_close_a_price_crossed(side='up', level=-1, current_price=-1, entry_underlying_price=-1):
#     # If price touches next level, we are in 5MH, next lelve is PDH,
#     closeness_distance = eval(app_config['closeness_distance'])  #atr_14
#     if side == 'up':
#         next_level = get_next_level(side, level)  # PDH
#         # PDH > 5MH AND  price => PDH
#         if (next_level > level and  abs(next_level - level) < closeness_distance and # next_level is close
#                 current_price > next_level and next_level > entry_underlying_price) : # price is crossed AND we opened below the next level ...
#             return True
#     else:
#         next_level = get_next_level(side, level)
#         if (next_level < level and abs(next_level - level) < closeness_distance and current_price < next_level and
#                 current_price < next_level and next_level < entry_underlying_price):  # price is crossed AND we opened above the next level ...
#             return True
#
#     return False


def polish_map_to_show_in_hover(data):
    logger.warning(f"@ {type(data)},  data: {data}, ")
    return json.dumps(data).replace(',', ',<br>')


def check_mark_revers_candles(symbol):
    # TODO remove try later ...
    try:
        logger.info(f"check_mark_revers_candles ... {symbol}")
        result = False
        t1_candle_date = application_state['open_trades_dic'].get(symbol,{}).get('take_profits',{}).get('t1',{}).get('candle_date',None)
        logger.info(f"check_mark_revers_candles, {symbol}, t1_candle_date: {t1_candle_date}")

        if t1_candle_date == None:
           return False

        right = application_state['open_trades_dic'].get(symbol,{}).get('right', '')
        logger.info(f"check_mark_revers_candles, {symbol}, right: {right} ")

        df = dfs_map.get(symbol, pd.DataFrame())
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

        target_date = pd.Timestamp(t1_candle_date)

        df = df[df["date"] >= target_date]
        logger.info(f"@@ check_mark_revers_candles, {symbol}, prev_close: {prev_close}. ")
        logger.info(f"check_mark_revers_candles, {symbol}, first two \n {df[:2].to_markdown()}")
        logger.info(f"check_mark_revers_candles, {symbol}, last two \n {df[-2:].to_markdown()}")

        df = df[:-2]                           # cut the latest row and the prev one as we comparing against it ...
        logger.info(f"@@ check_mark_revers_candles, {symbol}, candles we checking - after cutting last two (need to be verified)\n {df.to_markdown()}")
        if right == 'C':

            df["is_bearish"] = df["close"] < df["open"]
            lowest_bearish_low = df.loc[df["is_bearish"], "low"].min()

            result = prev_close < lowest_bearish_low and crossed_ema9
            logger.info(f"check_mark_revers_candles, {symbol}, lowest_bearish_low: {lowest_bearish_low}, prev_close: {prev_close}, {result}, \n {df.to_markdown()}")
            if result:
                logger.info(f"check_mark_revers_candles, {symbol}, The break happened. lowest_bearish_low: {lowest_bearish_low}, prev_close: {prev_close}")
                add_to_signlas(symbol, 'LEVEL_REPLACED', df['close'].iloc[-1], check_date, f'Level is break out {check_date}<br> t_date: {target_date} <br>  lowest_bearish_low: {lowest_bearish_low} <br> prev_close: {prev_close}' )

        else:

            df["is_bulish"] = df["close"] > df["open"]
            highest_bulish_high = df.loc[df["is_bulish"], "high"].max()

            result = prev_close > highest_bulish_high and crossed_ema9
            logger.info(f"check_mark_revers_candles, {symbol}, highest_bulish_high: {highest_bulish_high}, prev_close: {prev_close}, result: {result}, \n {df.to_markdown()}")
            if result:
                logger.info(f"check_mark_revers_candles, {symbol}, The break happened. highest_bulish_high: {highest_bulish_high}, prev_close: {prev_close}")
                add_to_signlas(symbol, 'LEVEL_REPLACED', df['close'].iloc[-1], check_date, f'Level is break out {check_date}<br> t_date: {target_date} <br>  highest_bulish_high: {highest_bulish_high} <br> prev_close: {prev_close}' )

        if result:
            logger.info(f"check_mark_revers_candles, The break happened. ")

        return result
    except Exception as e:
        logger.error(f"@@@ error: {e}")
        logger.error(traceback.format_exc())
    return result
def check_for_stop_loss_and_take_profit():
    global application_state

    for symbol, open_trade_info in application_state.get('open_trades_dic', {}).items():
        logger.info(f"check_for_stop_loss_and_take_profit(), symbol {symbol}, " )

        # ###
        # stop loss
        # ###
        logger.info(f"in check_for_stop_loss, {symbol} ,\n{pprint.pformat(open_trade_info)}" )
        if open_trade_info.get('available_quantity', 0) == 0:
            logger.info(f"{symbol}, check_for_stop_loss_and_take_profit(), available_quantity: 0")
            continue

        symbol_df = dfs_map.get(symbol, pd.DataFrame())
        entry_underlying_price = float(open_trade_info.get('entry_underlying_price', -1))  # used in config ...
        level_used_to_open = float(open_trade_info.get('level_used_to_open', -1)) # used in config ...
        avg_cost_for_1_contract = open_trade_info.get('avg_cost_for_1_contract', -1) # used in config
        right = application_state['open_trades_dic'][symbol].get('right', '') # used in config
        side = application_state['open_trades_dic'][symbol].get('side') # used in config
        level_used_to_open = application_state['open_trades_dic'][symbol]['level_used_to_open'] # used in config
        tolerance_amount = dynamic_tolerance.get('tolerance', 0)  # used in config
        start_quantity = application_state.get('open_trades_dic', {}).get(symbol, {}).get('starting_quantity', 0) # used in config
        available_quantity = application_state.get('open_trades_dic', {}).get(symbol, {}).get('available_quantity', 0)  # used in config

        underlying_current_price = get_current_price(symbol) # used in config  #TODO do we need to have call ?
        if len(symbol_df) == 0:
            # it maybe first run and we dont have it yet in the dic ...
            underlying_previous_candle_close = underlying_current_price
        else:
            underlying_previous_candle_close = symbol_df['close'].iloc[-2] # used in config


        current_bid, current_ask = get_bid_and_ask(options_portfolio_df, symbol) #used in config

        # update app status ...
        if app_config['symbols_meta'][symbol]['contract_type'] == 'Equity':
            application_state['open_trades_dic'][symbol]['current_bid'] = current_bid
            application_state['open_trades_dic'][symbol]['current_ask'] = current_ask
            application_state['open_trades_dic'][symbol]['current_underlying_price'] = underlying_current_price
            application_state['open_trades_dic'][symbol]['current_value'] = round( current_ask * application_state['open_trades_dic'][symbol]['starting_quantity'] * 100 , 3)
            application_state['open_trades_dic'][symbol]['current_pnl'] = round(application_state['open_trades_dic'][symbol].get('current_value', 0) - application_state['open_trades_dic'][symbol].get('cost_for_trade', 0) , 2)
            application_state['open_trades_dic'][symbol]['current_roi'] = round(application_state['open_trades_dic'][symbol]['current_bid'] / application_state['open_trades_dic'][symbol].get('avg_cost_for_1_contract', 1) - 1, 3)
        else: # it is future ...
            application_state['open_trades_dic'][symbol]['current_bid'] = current_bid
            application_state['open_trades_dic'][symbol]['current_ask'] = current_ask
            application_state['open_trades_dic'][symbol]['current_underlying_price'] = underlying_current_price
            application_state['open_trades_dic'][symbol]['current_value'] = underlying_current_price * 1 # TODO avaialbe...
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
            order_ref = get_order_ref('CLOSE', symbol, alias_for_ref='SL', unique_run_number=unique_run_number)
            close_option_positions(option_positions_to_monitor, symbol=symbol, order_ref=order_ref)
            data = {
                'symbol': symbol,
                'right': application_state['open_trades_dic'][symbol]['right'],
                'strike':  application_state['open_trades_dic'][symbol]['strike'],
                'expiry': application_state['open_trades_dic'][symbol]['expiry'],
                'current_bid': current_bid,
                'current_ask': current_ask,
                'underlying_current_price': underlying_current_price,
                'available_quantity_b4': available_quantity,
                'sl_u_run_number': unique_run_number,
                'stop_loss_condition': stop_loss_condition,
                'candle_date': str(df['date'].iloc[-1]),
                'open_u_run_number': '',
                'open_order_ref': '',
                'sl_order_ref': order_ref,
                'local_symbol': application_state['open_trades_dic'][symbol].get('local_symbol'),
                'con_id': application_state['open_trades_dic'][symbol].get('con_id'),
                }
            application_state['open_trades_dic'][symbol].setdefault('stop_loss', {})['s1'] = data # save it in the
            archive_open_trade_dic(symbol, open_trade_info)
            application_state.setdefault('open_trades_dic', {})[symbol] = {}  # This need to be happened after we get required inf from dic...
            add_order_ref_to_application_state(open_order_ref=open_trade_info.get('order_ref'), close_order_ref=order_ref)
            add_to_stop_loss_history_df(data)
            add_to_signlas(symbol, 'STOP_LOSS_SENT', underlying_current_price, df['date'].iloc[-1], f"STOP_LOSS  <BR> {polish_map_to_show_in_hover(data)}")
            send_email(event='stop_loss_sent', symbol=symbol, body=polish_map_to_show_in_hover(data))



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


            if close_quantity_percentage == -1: # close all
                close_quantity = available_quantity
            else:
                close_quantity = round(start_quantity * close_quantity_percentage )
                close_quantity = 1 if close_quantity == 0 else close_quantity  # we want to make sure 0.4 * 1 will return 1.

            logger.info(f"available_quantity: {available_quantity}, close_quantity_percentage: {close_quantity_percentage}, close_quantity: {close_quantity}, start_quantity:{start_quantity}")
            logger.info(f"take_profit_condition: {take_profit_condition}, take_profit_condition_evaluated: {take_profit_condition_evaluated}")

            if take_profit_condition_evaluated and available_quantity > 0 and close_quantity != 0 and close_quantity <= available_quantity :
                logger.info(f"Sending TP ...{take_profit}")
                if app_config['symbols_meta'][symbol]['contract_type'] == 'Equity':
                    order_ref = get_order_ref('CLOSE', symbol, alias_for_ref='SL', unique_run_number=unique_run_number)
                    close_option_positions(option_positions_to_monitor, symbol=symbol, close_qty=close_quantity, order_ref=order_ref)
                elif app_config['symbols_meta'][symbol]['contract_type'] == 'Future':
                    order_ref = get_order_ref('CLOSE', symbol, alias_for_ref=take_profit, unique_run_number=unique_run_number)
                    close_future_positions(future_positions_to_monitor, symbol=symbol, close_qty=close_quantity, order_ref=order_ref )
                else:
                    logger.warning(f"@@@@ TBD")

                application_state['open_trades_dic'][symbol]['available_quantity'] = available_quantity - close_quantity

                data = {
                    'status': 'SENT',
                    'available_quantity_b4' : available_quantity,
                    'close_quantity': close_quantity,
                    'candle_date': str(df['date'].iloc[-1]),
                    'tp_u_run_number': unique_run_number,
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
                    'candle_date': str(df['date'].iloc[-1]),
                    'tp_u_run_number': unique_run_number,
                    'order_ref': order_ref,
                    'local_symbol': application_state['open_trades_dic'][symbol].get('local_symbol'),
                    'con_id': application_state['open_trades_dic'][symbol].get('con_id'),
                }
                add_order_ref_to_application_state(open_order_ref=open_trade_info.get('order_ref'), close_order_ref=order_ref)
                add_to_take_profit_history_df(data)
                add_to_signlas(symbol, 'TAKE_PROFIT_SENT', underlying_current_price, df['date'].iloc[-1], f"TAKE-PROFIT-{take_profit} <BR>{polish_map_to_show_in_hover(data)}")
                send_email(event='take_profit_sent', symbol=symbol, body=polish_map_to_show_in_hover(data))

                # This is very import. There was a case that after t1 execution, t2 conditon meet also
                # but the avaialble_quantitiy was not updates. look at the for iterator. we are updating what we are iterating it ...
                # DO MOT DELETE THIS. we go out and we will come back i next .... if break didn't work we need to use return ...
                break

            else:
                logger.warning(f"{symbol}, {take_profit} TP condition didn't meet ...  ")


        # check to clean up
        if application_state['open_trades_dic'].get(symbol, {}) != {} and application_state['open_trades_dic'][symbol].get('available_quantity', 0) == 0:
            logger.info(f"{symbol}, the available_quantity is zero, so we set empty dic for it")
            archive_open_trade_dic(symbol, open_trade_info)
            remove_symbol_from_open_trade_dic(symbol)

    return

def send_email(event='order_sent', symbol='', subject='', body=''):
    if app_config['email']['send_email']:
        recipients = app_config['email']['recipients']

        if event.lower() == 'order_sent':
            subject = f"Order Sent {symbol} - {app_config['user_name']}"
            body = (f"Order Sent ... <br> {body}"
                    f"<br>Later more detail will come ...<br>")

        elif event.lower() == 'stop_loss_sent':
            subject = f"Stop Loss {symbol} - {app_config['user_name']}"
            body = (f"Stop Loss Sent ... <br> {body}"
                    f"<br>Later more detail will come ...<br>")

        elif event.lower() == 'take_profit_sent':
            subject = f"Take Profit {symbol} - {app_config['user_name']}"
            body = (f"Take Profit Sent ... <br> {body}"
                    f"<br>Later more detail will come ...<br>")

        logger.info(f"send_email, recipientse {recipients}, subject: {subject}")
        email_utils.send_email(recipients, subject=subject, body=body)

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
                trade.fillEvent += ib_posttrade.on_fill

                logger.warning(f"open order canceled, trade: {trade}")
                while not trade.isDone():
                    logger.warning(f"sleep until is done, trade.isDone(): {trade.isDone()}")
                    ib.sleep(0.5)
    return



def check_application_state_vs_ib_positions():
    global application_state
    for symbol, open_trade_info in application_state.get('open_trades_dic', {}).items():
        found = False
        if open_trade_info.get('available_quantity', 0) != 0:  # There is in the dic
            if 'OPTION' == open_trade_info.get('position_type'):
                if len(options_portfolio_df) > 0:
                    x_df = options_portfolio_df[options_portfolio_df['symbol'] == symbol]
                    if len(x_df) > 0:
                        found = True

            elif 'FUTURE' == open_trade_info.get('position_type'):
                if len(future_portfolio_df) > 0:
                    x_df = future_portfolio_df[future_portfolio_df['symbol'] == symbol]
                    if len(x_df) > 0:
                        found = True


            if not found:
                logger.warning(f"@@@@ This symbol exist in the application_state but not in the ib. symbol:{symbol}")
                logger.warning(f"@@@@ open_trade_info: {open_trade_info}")
                logger.warning(f"@@@@ options_portfolio_df\n{options_portfolio_df.to_markdown()}")
                logger.warning(f"@@@@ future_portfolio_df\n{future_portfolio_df.to_markdown()}")
                archive_open_trade_dic(symbol, open_trade_info)
                remove_symbol_from_open_trade_dic(symbol)

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
    levels_map = get_levels_map()
    closeness_distance = eval(app_config['closeness_distance_for_case_1'])
    result = False
    if side == 'up':
        result = abs(levels_map['PDH'] - levels_map['PMH']) < closeness_distance and abs( levels_map['5MH'] - levels_map['PDH']) < closeness_distance
    else: # down
        result = abs(levels_map['PDL'] - levels_map['PML']) < closeness_distance and abs(levels_map['5ML'] - levels_map['PDL']) < closeness_distance

    return result

def save_extra_features_df():
    extra_features_df = df.copy()
    extra_features_df = extra_features_df.merge(relative_strength_df, on='date', how='left')
    extra_features_df = extra_features_df.merge(intraday_rs_df, on='date', how='left')

    file = f"{charts_dir}/{symbol}-{time_frame.replace(' ', '')}-extra_features_df.csv"

    if mode == 'back_test':
        extra_features_df = cut_df_strating_hour_x_on_last_day(extra_features_df, cutoff_time="09:15")

    extra_features_df.to_csv(file, index=False)

def generate_df_file_map():
    return {
        "drawing_objects_df": f"{charts_dir}/10-drawing_objects_df.csv",
        "key_levels_df": f"{portfolio_dir}/11-key_levels_df.csv",
        "hover_df": f"{charts_dir}/12-hover_df.csv",
        "close_levels_df": f'{charts_dir}/13-close_levels_df.csv',
        "screening_log_df": f"{charts_dir}/12-screening_log_df.csv",
        "order_history_df": f"{portfolio_dir}/13-order_history_df.csv",
        "stop_loss_history_df": f"{portfolio_dir}/14-stop_loss_history_df.csv",
        "take_profit_history_df": f"{portfolio_dir}/15-take_profit_history_df.csv",
        "futures_order_history_df": f"{portfolio_dir}/16-futures_order_history_df.csv",
        "screening_log_for_run_df": f"{portfolio_dir}/17-screening_log_for_run_df.csv", # TODO rename
        "screening_summary_df" :  f"{portfolio_dir}/18-screening_summary_df.csv",  # TODO rename
        "bid_ask_history_df" :  f"{portfolio_dir}/19-bid_ask_history_df.csv",  # TODO rename
        "screening_summary_agg_df" :  f"{portfolio_dir}/20-screening_summary_agg_df.csv",  # TODO rename
        "capital_allocation_df" :  f"{portfolio_dir}/21-capital_allocation_df.csv",  # TODO rename
        "open_close_refs_df" :  f"{portfolio_dir}/22-open_close_refs_df.csv",  # TODO rename

    }

df_file_map = generate_df_file_map()

def save_all_csv_files():
    global df_file_map
    start_time = time.time()

    if mode == 'back_test': # we need to re assign ...
        df_file_map = generate_df_file_map()

    logger.info(f"save_all_csv_files, start ...")

    save_list_to_csv(close_pairs, file=df_file_map.get('close_levels_df'), mode='w')
    df_utils.save_df_to_csv_a_tabular(drawing_objects_df, file_path=df_file_map.get('drawing_objects_df'), mode='w')
    df_utils.save_df_to_csv_a_tabular(key_levels_df, file_path=df_file_map.get('key_levels_df'), mode='w')
    df_utils.save_df_to_csv_a_tabular(hover_df, file_path=df_file_map.get('hover_df'), mode='a')
    df_utils.save_df_to_csv_a_tabular(order_history_df, file_path=df_file_map.get('order_history_df'), mode='a', drop_dupplicates=True)
    df_utils.save_df_to_csv_a_tabular(stop_loss_history_df, file_path=df_file_map.get('stop_loss_history_df'), mode='a', drop_dupplicates=True)
    df_utils.save_df_to_csv_a_tabular(take_profit_history_df, file_path=df_file_map.get('take_profit_history_df'), mode='a', drop_dupplicates=True)
    df_utils.save_df_to_csv_a_tabular(futures_order_history_df, file_path=df_file_map.get('futures_order_history_df'), mode='a', drop_dupplicates=True)
    df_utils.save_df_to_csv_a_tabular(screening_log_df, file_path=add_unique_run_number_start_end_date(df_file_map.get('screening_log_df')), mode='a', drop_dupplicates=True)
    df_utils.save_df_to_csv_a_tabular(bid_ask_history_df, file_path=add_unique_run_number_start_end_date(df_file_map.get('bid_ask_history_df')), mode='a', drop_dupplicates=True)
    df_utils.save_df_to_csv_a_tabular(capital_allocation_df, file_path=add_unique_run_number_start_end_date(df_file_map.get('capital_allocation_df')), mode='a', drop_dupplicates=True)
    df_utils.save_df_to_csv_a_tabular(open_close_refs_df, file_path=add_unique_run_number_start_end_date(df_file_map.get('open_close_refs_df')), mode='a', drop_dupplicates=True)

    if mode == 'live':
        ib_posttrade.save_ib_dfs(ib_dir,ib)
    logger.info(f"save_all_csv_files, finished ...")

    end_time = time.time()
    spent_time = round(end_time - start_time, 2)
    logger.warning(f'save_all_csv_files(), spent_time: {spent_time} seconds')
    return

def add_rs_relative_to_candle_info(symbol):
    if symbol == 'QQQ':
        return

    rs_rel = round(intraday_rs_df['rs_rel'].iloc[-1], 2)
    rs_rel_ema = round(intraday_rs_df['rs_rel_ema'].iloc[-1], 2)
    add_to_candle_info_df(symbol, df['date'].iloc[-1], df['close'].iloc[-1], f"rs_rel: {rs_rel}, rs_rel_ema: {rs_rel_ema}" )
    return

def mark_tolerance_to_the_level(level, level_name):
    if level == 0:
        return

    tolerance = dynamic_tolerance.get('tolerance', 0)
    p1 = level - tolerance * app_config['symbols_meta'][symbol].get('retest_tolerance_multiplier', 1)
    p2 = level + tolerance * app_config['symbols_meta'][symbol].get('retest_tolerance_multiplier', 1)
    p1 = round(p1 ,2)
    p2 = round(p2 ,2)
    date = df['date'].iloc[-1]
    add_to_signlas(symbol, f'{level_name}_SMALL_DOT', p1, date, f'tel: {p1}, l: {level} t: {tolerance}', 'yellow' )
    add_to_signlas(symbol, f'{level_name}_SMALL_DOT_1', p2, date, f'tel: {p2}, l: {level} t: {tolerance}' ,'yellow' )

    return

def mark_atr_to_the_level(side, level, level_name):
    if level == 0:
        return
    date = df['date'].iloc[-1]
    atr =  df['atr_14'].iloc[-1]
    if side == 'up':
        p1 = round(level + atr, 2)
    else:
        p1 = round(level - atr, 2)
    add_to_signlas(symbol, f'{level_name}_SMALL_DOT_2', p1, date, f'atr_14: p: {p1}, l: {level} atr: {round(atr,2)}', 'red' )

    return


def add_list_to_dic(df, data_list):
    df = pd.concat([df, pd.DataFrame(data_list)])
    return df




def add_unique_run_number_start_end_date(str):
    if mode == 'live':
        return str
    return str.replace('.csv', f'-{unique_run_number}-{back_test_date_start}-{back_test_date_end}.csv')

def populate_backtest_columns(df):
    df['position'] = 0
    df["side"] = ''
    df["right"] = ''
    df["open_price"] = 0
    df["close_price"] = 0
    df["stop_loss_price"] = 0.0
    df["take_profit_price"] = 0.0
    df["trade_return"] = 0.0
    df["close_profit"] = 0
    return df

def detect_a_mark_market_gap(symbol, df):
    df["trade_day"] = df["date"].dt.date
    unique_days = sorted(df["trade_day"].unique())
    today = unique_days[-1]
    yesterday = unique_days[-2] if len(unique_days) >= 2 else unique_days[-1]

    t = pd.Timestamp("09:30").time()
    res = df.loc[(df["trade_day"] == today) & (df["date"].dt.time == t), "open"]
    open_today_0930 = res.iloc[-1] if not res.empty else None

    t = pd.Timestamp("16:00").time()
    res = df.loc[(df["trade_day"] == yesterday) & (df["date"].dt.time == t), "close"]
    close_yesterday_1600 = res.iloc[-1] if not res.empty else None

    if open_today_0930 is not  None and close_yesterday_1600 is not None:
        add_to_drawing_objects_df(symbol=symbol, time_frame='1min', object='rect', color=constants.COLOR_GREEN_TRANSPARENT, date_1=f'{today} 09:00:00', price_1=close_yesterday_1600,
                                  date_2=f'{today} 09:30:00', price_2=open_today_0930, memo='Market Gap', unique_id=f'{symbol}--MARKET-GAP')

    return


def hold_for_debug():
    if df['date'].iloc[-1].strftime('%Y-%m-%d %H:%M') == '2025-10-01 10:04':
        logger.info('Stop for debug')


def is_price_crossed_levels(side='down', symbol='', next_levels=['PDL'], current_price=-1, entry_underlying_price=-1):
    if next_levels is None:
        return False

    levels_map = get_levels_map()
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

def is_price_close_to_next_levels(side='up',price= 0, current_level=1, next_levels=['PDH']):  # used in the config

    if next_levels is None:
        return False
    levels_map = get_levels_map()
    closeness_distance = eval(app_config['closeness_distance'])

    for key in next_levels:
        next_level = levels_map.get(key, None)
        if next_level is None:
            continue  # skip missing levels

        distance = abs(price - next_level)
        is_close = distance < closeness_distance

        # next_level is above the current level, price is below next level but very close
        if side == "up" and next_level > current_level and price > current_level and price < next_level and is_close:
            add_to_signlas(symbol, 'PRICE_CLODE_TO_LEVEL', price, df['date'].iloc[-1], f'price is very close to next level. price: {price}, to: {next_level} <br> {get_hhm_mm_of_last_record(df)}', color='red')
            return True
        if side == "down" and next_level < current_level and price < current_level and price > next_level and is_close:
            add_to_signlas(symbol, 'PRICE_CLODE_TO_LEVEL', price, df['date'].iloc[-1], f'price is very close to next level. price: {price}, to: {next_level} <br> {get_hhm_mm_of_last_record(df)}', color='red')
            return True

        # next_level is above the current level, price is above next level and current level but very close
        if side == "up" and next_level > current_level and price > current_level and price > next_level and is_close: # This is for once the price passes the next level as well.
            add_to_signlas(symbol, 'PRICE_CLODE_TO_LEVEL', price, df['date'].iloc[-1], f'price is very close and passed next level. price: {price}, to: {next_level} <br> {get_hhm_mm_of_last_record(df)}', color='red')
            return True

        if side == "down" and next_level < current_level and price < current_level and price < next_level and is_close:  # see PLTR Oct 09-
            add_to_signlas(symbol, 'PRICE_CLODE_TO_LEVEL', price, df['date'].iloc[-1], f'price is close and passed next level. price: {price}, to: {next_level} <br> {get_hhm_mm_of_last_record(df)}', color='red')
            return True

    return False


def is_price_close_to_next_levels_ver_2(side='up', price= 0, current_level=1, next_levels=['PDH']):  # used in the config

    if next_levels is None:
        return False
    levels_map = get_levels_map()
    closeness_distance = eval(app_config['closeness_distance'])
    if breakout_idx == 0:
        return False

    clipped_df = df[breakout_idx:]
    highest_high = clipped_df['high'].max()
    lowest_low = clipped_df['low'].min()
    logger.info(f"is_price_close_to_next_levels_ver_2, {symbol}, price: side: {side}, {price}, current_level: {current_level}, next_levels:{next_levels}, breakout_idx: {breakout_idx} ,date: {df['date'].iloc[-1]}")
    logger.info(f"is_price_close_to_next_levels_ver_2, clipped_df: \n{clipped_df.to_markdown()}")

    for key in next_levels:
        next_level = levels_map.get(key, None)
        if next_level is None:
            continue  # skip missing levels

        distance = abs(price - next_level)
        is_close = distance < closeness_distance

        if side == "up":
            # TODO THe first two can merged ..
            # next_level is above the current level, price is below next level but very close
            if next_level > current_level and price > current_level and price < next_level and is_close:
                add_to_signlas(symbol, 'PRICE_CLODE_TO_LEVEL', price, df['date'].iloc[-1], f'up-1 {price}, to: {next_level} <br> {get_hhm_mm_of_last_record(df)}', color='red')
                return True

            # next_level is above the current level, price is above next level
            if next_level > current_level and price > current_level and price > next_level: # This is for once the price passes the next level as well.
                add_to_signlas(symbol, 'PRICE_CLODE_TO_LEVEL', price, df['date'].iloc[-1], f'up-2. price: {price}, to: {next_level} <br> {get_hhm_mm_of_last_record(df)}', color='red')
                return True

            # next_level is above the current level AND price is above leve AND highest_high after breakout canddle is close to the next level ..
            if next_level > current_level and price > current_level and abs(highest_high - next_level) < closeness_distance:
                add_to_signlas(symbol, 'PRICE_CLODE_TO_LEVEL', price, df['date'].iloc[-1], f'up-3. price: {price}, to: {next_level} <br> {get_hhm_mm_of_last_record(df)}', color='red')
                return True

            # next_level > current level AND price > c level AND highest high >  next level
            if next_level > current_level and price > current_level and highest_high > next_level:
                add_to_signlas(symbol, 'PRICE_CLODE_TO_LEVEL', price, df['date'].iloc[-1], f'up-4. price: {price}, to: {next_level} <br> {get_hhm_mm_of_last_record(df)}', color='red')
                return True

        else:
            # next l < c level AND price < c level AND price > next l ...
            if next_level < current_level and price < current_level and price > next_level and is_close:
                add_to_signlas(symbol, 'PRICE_CLODE_TO_LEVEL', price, df['date'].iloc[-1], f'down-1. price: {price}, to: {next_level} <br> {get_hhm_mm_of_last_record(df)}', color='red')
                return True


            if next_level < current_level and price < current_level and price < next_level:  # see PLTR Oct 09-
                add_to_signlas(symbol, 'PRICE_CLODE_TO_LEVEL', price, df['date'].iloc[-1], f'down-2. price: {price}, to: {next_level} <br> {get_hhm_mm_of_last_record(df)}', color='red')
                return True

            # next_level < current level AND price is below level AND lowest low after breakout canddle is close to the next level ..
            if next_level < current_level and price < current_level and abs(lowest_low - next_level) < closeness_distance:
                add_to_signlas(symbol, 'PRICE_CLODE_TO_LEVEL', price, df['date'].iloc[-1], f'down-3. price: {price}, to: {next_level} <br> {get_hhm_mm_of_last_record(df)}', color='red')
                return True

            # next_level < current level AND price < c level AND lowest low  <  next level
            if next_level < current_level and price < current_level and lowest_low < next_level:
                add_to_signlas(symbol, 'PRICE_CLODE_TO_LEVEL', price, df['date'].iloc[-1], f'down-4. price: {price}, to: {next_level} <br> {get_hhm_mm_of_last_record(df)}', color='red')
                return True


    return False


def calculate_score(market_trend):
    """
    Calculate a total score based on evaluated conditions.
    - context: dict of variables (safe eval environment)
    - scoring_rules: list of dicts with 'cond', 'score', and 'memo'
    """
    final_score = 0
    memo_lines = []
    for s in app_config['scores']:
        cond = app_config['scores'][s].get("cond", "")
        score = app_config['scores'][s].get("score", 0)
        memo = app_config['scores'][s].get("memo", "")
        cond_result = False
        try:
            cond_result = eval(cond)
        except Exception as e:
            logger.error(f"@@ calculate_score, error {e}")
            cond_result = False
            memo_lines.append(f"ERROR evaluating '{cond}': {e}")

        # Only add score if condition is True
        score_got = score if cond_result else 0
        final_score += score_got
        memo_lines.append('----------')
        if s =='s1':
            memo += " "
            last5 = df['VR'].tail(7)
            s = " | ".join(f"{v:.2f}" for v in last5)
            memo += s
        memo_lines.append(f"{score_got}/{score}, {cond_result},{cond}  # {memo}")

    memo_lines.insert(0, f"{final_score} # score") # in the chart we expecting the score#, so don't change it .
    memo_lines.append(f"Final Score: {final_score}")
    memo_lines.append(f"{get_hhm_mm_of_last_record(df)}")

    final_memo = "<br>".join(memo_lines)

    return final_score, final_memo

def print_missing_rows_in_qqq_vs_stock(df, qqq_df):
    if not eval(app_config.get('busy_time', '1 == 2')):

        missing_rows_in_qqq_df = df.loc[~df['date'].isin(qqq_df['date'])]
        if len(missing_rows_in_qqq_df) > 0:
            logger.warning(f"missing_rows_in_qqq_df: \n{missing_rows_in_qqq_df[-3:].to_markdown()}")
    return

def all_levels_in(symbol, levels=['PDL', 'PDH', 'PMH', 'PML','5MH', '5ML']):
    # if a level is not there ,will return False
    levels_map = get_levels_map()
    for level in levels:
        if levels_map.get(level) == None:
            return False
    return True


def orchestrate_expirations_strikes():
    global options_meta_date_dic
    # get from IB. is messy ...
    find_expiration_and_strikes_for_all()
    dump_a_map_to_file(options_meta_date_dic, file_path=f'{intermediate_dir}/85-strikes-expirations-ib.csv')

    # Mere with Nazadq ...
    nazdaq_file = f'{intermediate_dir}/85-strikes-nazdaq.csv'
    strikes_from_nazdaq = file_utils.load_json_from_file(nazdaq_file)
    if strikes_from_nazdaq != {}:
        options_meta_date_dic.update(strikes_from_nazdaq)
        dump_a_map_to_file(options_meta_date_dic, file_path=f'{intermediate_dir}/85-strikes-expirations-ib+nazdaq.csv')

    adhoc_file = f'{intermediate_dir}/85-strikes-adhoc.csv'
    strikes_from_adhoc = file_utils.load_json_from_file(adhoc_file)
    if strikes_from_adhoc != {}:
        options_meta_date_dic.update(strikes_from_adhoc)
        dump_a_map_to_file(options_meta_date_dic, file_path=f'{intermediate_dir}/85-strikes-expirations-ib+nazdaq+adhoc.csv')

    logger.debug('hold it here ')
    return


def get_last_record_hh_mm():
    if len(df) == 0 or df is None:
        return -1

    last_record_hh_mm = int(df['date'].iloc[-1].strftime('%H%M'))
    return int(last_record_hh_mm)


def summerize_screening_log(screening_log_for_run_df):
    if len(screening_log_for_run_df) ==0:
        return

    df = screening_log_for_run_df
    df = df[df["symbol"] != "MNQ"]

    # if we want to have autmated aggragation have is_ in the begining ...
    df["is_positive"] = df["pnl"] > 0
    df["is_negative"] = df["pnl"] < 0
    df["is_long"] = df["side"] == "long"
    df["is_short"] = df["side"] == "short"
    df["is_long_positive"] = df["is_long"] & df["is_positive"]
    df["is_short_positive"] = df["is_short"] & df["is_positive"]
    df["is_rs_positive"] = df["rs_relative"] > 0
    df["is_win_rs_positive"] = df["is_rs_positive"] & df["is_positive"]
    df["is_lose_rs_positive"] = df["is_rs_positive"] & df["is_negative"]
    df["is_vr_enough"] = df["entry_volume_ratio"] > 1.0
    df["is_win_vr_enough"] = df["is_vr_enough"] & df["is_positive"]
    df["is_lose_vr_enough"] = df["is_vr_enough"] & df["is_negative"]


    # ---- Build aggregation dict ----
    agg_dict = {}
    # ---- Add fixed aggregations ----
    agg_dict["total_trades"] = ("pnl", "count")
    agg_dict["sum_pnl"] = ("pnl", "sum")

    # ---- Auto-find all columns starting with "is_" ----
    is_cols = [col for col in df.columns if col.startswith("is_")]

    # auto add all is_* columns → (colname_without_is_ + _count)
    for col in is_cols:
        new_name = f"{col}_count"  # strip is_
        agg_dict[new_name] = (col, "sum")  # no count here. sum counts True


    logger.info(f'hold it{agg_dict}')
    # ---- GROUPBY using classic syntax ----
    screening_summary_df = (
        df.groupby(["trade_date", "day_of_week", "memo"])
        .agg(**agg_dict)
        .reset_index()
    )


    screening_summary_df["long_win_rate"] = np.where(
        screening_summary_df["is_long_count"] > 0,
        (screening_summary_df["is_long_positive_count"] / screening_summary_df["is_long_count"]) * 100,
        0
    )
    screening_summary_df["long_win_rate"] = round(screening_summary_df["long_win_rate"], 2)

    screening_summary_df["short_win_rate"] = np.where(
        screening_summary_df["is_short_count"] > 0,
        (screening_summary_df["is_short_positive_count"] / screening_summary_df["is_short_count"]) * 100,
        0
    )
    screening_summary_df["short_win_rate"] = round(screening_summary_df["short_win_rate"] , 2)

    screening_summary_df["total_win_rate"] = np.where(
        screening_summary_df["total_trades"] > 0,
        (screening_summary_df["is_positive_count"] / screening_summary_df["total_trades"]) * 100,
        0
    )
    screening_summary_df["total_win_rate"] = round(screening_summary_df["total_win_rate"], 2)
    screening_summary_df = df_utils.move_last_x_to_position_y(screening_summary_df, 3, 4)
    return screening_summary_df


def aggregate_screening_log(df):
    df['run_number_start_end'] = f'{unique_run_number}--{back_test_date_start}--{back_test_date_end}'

    # auto-pick columns ending with _count OR equal to "total_trades"

    # then append all is_* count columns
    count_cols = [col for col in df.columns
                  if col.endswith('_count')]

    agg_map = {
        "total_trades": "sum",
        "sum_pnl": "sum",
    }

    agg_map.update({col: "sum" for col in count_cols})

    agg_df = (
        df.groupby(['run_number_start_end', 'memo'])
          .agg(agg_map)
          .reset_index()
    )
    # Compute win rates
    agg_df["long_win_rate"] = round ((
                                      agg_df["is_long_positive_count"] /
                                      agg_df["is_long_count"].replace(0, float("nan"))
                              ) * 100 , 2)

    agg_df["short_win_rate"] = round((
                                       agg_df["is_short_positive_count"] /
                                       agg_df["is_short_count"].replace(0, float("nan"))
                               ) * 100, 2)

    agg_df["total_win_rate"] = round((
                                       agg_df["is_positive_count"] /
                                       agg_df["total_trades"].replace(0, float("nan"))
                               ) * 100 ,2)

    agg_df = agg_df.fillna(0)
    agg_df = df_utils.move_last_x_to_position_y(agg_df, 3, 4)

    return agg_df


def add_open_position_to_candle_info(symbol):
    candle_info_price = df['low'].iloc[-1]
    open_trade_info = application_state.get('open_trades_dic', {}).get(symbol)
    if open_trade_info:
        add_to_candle_info_df(symbol, df['date'].iloc[-1], candle_info_price, polish_map_to_show_in_hover(open_trade_info))  # shoe open trade inc hart ...

if __name__ == "__main__":

    app_config = config_utils.load_app_config(portfolio_id)

    ib_config = load_ib_config()
    ib = create_ib_connection()


    application_state = {}
    options_meta_date_dic = {}
    unique_run_number = ''

    if app_config['load_application_state_from_file']:
        load_application_state_from_file()

    if app_config['close_all_open_option_positions']:
        close_all_open_option_positions()

    if app_config['cancel_open_orders_on_start']:
        cancel_open_orders()

    time_frame = '1 min'

    drawing_objects_df = pd.DataFrame()
    hover_df = pd.DataFrame(columns=['symbol', 'time_frame', 'object', 'color', 'date_1', 'price_1', 'date_2', 'price_2', 'memo', 'unique_id'])
    key_levels_df = pd.DataFrame(columns=['symbol', 'time_frame', 'key_level', 'price', 'memo', 'unique_id'])
    order_history_df = pd.DataFrame()
    futures_order_history_df = pd.DataFrame()
    stop_loss_history_df = pd.DataFrame()
    take_profit_history_df = pd.DataFrame()
    bid_ask_history_df = pd.DataFrame()
    capital_allocation_df = pd.DataFrame()
    open_close_refs_df = pd.DataFrame()
    close_pairs = []
    consequence_exception = 0
    dfs_map = {}
    screening_log_list = []
    screening_log_df = pd.DataFrame()
    last_candles_visit_map = {} # {'QQQ': '2025-11-12 23:31:00'}
    close_levels_marked_for_symol_map = {}
    checkmark_map = {} # using to check mark things ...
    qqq_df = pd.DataFrame()  # need to reset once we iterate throught all symbols ...
    qqq_5MH = -1
    qqq_5ML = -1
    qqq_PDH = -1
    qqq_PDL = -1

    logger.info("application started.")
    run_spend_time = 0
    run_number = 0
    while True:
      try:
        start_time = time.time()
        run_number += 1
        now = datetime.datetime.now()
        current_hh_ny = int(now.strftime("%H")) # checks trade time ...
        current_hh_mm_ny = int(now.strftime("%H%M")) # checks trade time ...
        date_yyyy_mm_dd_hh_mm = now.strftime("%Y-%m-%d__%H-%M")
        date_yyyy_mm_dd = now.strftime("%Y-%m-%d")
        date_run_number = f"{now.strftime('%Y%m%d-%H%M%S')}--{run_number}"
        day_of_week = now.strftime("%A")

        logger.info(f"==================== run_number: {run_number}, date_run_number: {date_run_number}")

        is_trade_time = eval(app_config['live']['trade_time'])
        is_busy_time = eval(app_config['live'].get('busy_time', '1 == 1'))
        is_market_time = eval(app_config['live'].get('market_time', '1 == 1'))

        if run_number % 1 == 0:
            app_config = config_utils.load_app_config(portfolio_id)

        if app_config['exit']:
            update_config_and_save(app_config, 'exit', False)
            save_all_csv_files()
            exit(1)

        if run_number == 1:
            orchestrate_expirations_strikes()

        if run_number == 1:
            historical_days = '' # from config
        elif day_of_week == 'Monday':
            historical_days = '3 D'  # 1 D doesnt go for previous day ...
        else:
            historical_days = '1 D'


        all_positions = get_all_open_positions()
        option_positions_to_monitor = find_option_positions_to_monitor(all_positions)
        future_positions_to_monitor = find_future_positions_to_monitor(all_positions)

        update_for_avg_cost(option_positions_to_monitor)

        options_portfolio_df = get_live_quote_for_option_positions(option_positions_to_monitor) # This is used in TP and SL, so need we have it each run
        future_portfolio_df = get_live_quote_for_future_positions(future_positions_to_monitor)

        if not is_busy_time and is_market_time and not checkmark_map.get(f'TEST_STRIKES-{current_hh_mm_ny}') and current_hh_mm_ny % 10 == 0: # only at 1110, 1120, 1130 ..
           test_get_bid_ask_for_symbols()
           checkmark_map[f'TEST_STRIKES-{current_hh_mm_ny}'] = True
           logger.info(f"bid_ask_history_df: \n: {bid_ask_history_df.to_markdown()}")

        if 5 * run_number % 60 == 0:
           check_application_state_vs_ib_positions()


        symbol_number = 0
        for symbol in app_config['symbols']:

            symbol_number += 1
            unique_run_number = f"{date_run_number}--{symbol_number}"

            logger.warning(f"------------------- {symbol}, {unique_run_number}")
            symbol_start_time = time.time()

            # These are for each symbol ...
            up_offset_counter = 0  # this is for hovers on the candles ... need to be renamed ...
            down_offset_counter = 0
            signals = []
            close_pairs = []
            candle_info_df = pd.DataFrame(columns=['symbol', 'date', 'price', 'memo'])
            retest_indices_by_level_set = {}
            break_out_indices_by_level_set = {}
            retest_idx = 0
            breakout_idx = 0

            df = get_market_data(symbol, '1 min', historical_days=historical_days)
            df = popualate_features(df)
            df = populate_volume_ratio(df)
            last_record_hh_mm = get_last_record_hh_mm()

            dfs_map[symbol] = df.copy()  # we need for open trades ...
            if symbol == 'QQQ':
                qqq_df = df.copy() # keep latest qqq

            qqq_df = preppare_qqq_df(qqq_df)
            print_missing_rows_in_qqq_vs_stock(df, qqq_df)

            # Process starts from here ...
            # Preparing ....
            relative_strength_df = compute_relative_strength(df, qqq_df, period=20)
            intraday_rs_df = compute_intraday_rs(df, qqq_df)
            dynamic_tolerance = atr_tolerance_helper.get_dynamic_tolerance(df, level=0, min_tick=0.01)

            # Levels
            if run_number == 1: # only first run for each symbol ...
                calculate_PDL_PDH(df)

            are_all_levels_in = all_levels_in(symbol)
            if not are_all_levels_in: # if not in, recalcualte ...
                # TODO need to be checked, we need to pass that candle... better to calculate every time ..
                find_add_PMH_PML_levels_to_key_levels_df()
                find_add_5MH_5ML_levels_to_key_levels_df()

            key_levels_list = get_key_levels_list() # This need to be done after 5MH

            if symbol == 'QQQ': # TODO we need to do once after 9:35
                qqq_5MH = get_levels_map().get('5MH', -1)
                qqq_5ML = get_levels_map().get('5ML', -1)
                qqq_PDH = get_levels_map().get('PDH', -1)
                qqq_PDL = get_levels_map().get('PDL', -1)

            # once per candle per symbol ...
            if last_candles_visit_map.get(symbol, None ) != df['date'].iloc[-1]:
                mark_tolerance_to_the_level(get_levels_map().get('5MH', 0), '5MH')
                mark_tolerance_to_the_level(get_levels_map().get('5ML', 0), '5ML')
                mark_atr_to_the_level('up', get_levels_map().get('5MH', 0), '5MH')
                mark_atr_to_the_level('down', get_levels_map().get('5ML', 0), '5ML')
                add_atr_to_candle_info(dynamic_tolerance)
                add_rs_relative_to_candle_info(symbol)
                add_open_position_to_candle_info(symbol)

            if are_all_levels_in and not close_levels_marked_for_symol_map.get(symbol): # we have all elvels, so mark them ...
                mark_close_levels(key_levels_list)
                close_levels_marked_for_symol_map[symbol] = True
                checkmark_map[f'{symbol}-ALL_LEVELS_IN'] = True

            buy_sell_case_results_list = check_buy_and_sell_cases()

            check_buy_sell_result_to_send_order(buy_sell_case_results_list)
            check_for_stop_loss_and_take_profit()

            add_buy_a_sell_entries_to_signals(buy_sell_case_results_list)

            add_candle_info_df_to_signals()  # !! Adding to signals should happen before HERE
            logger.debug(f"{symbol}, signals: {signals}")

            hover_df = convert_signals_to_hover_df(signals)

            if (is_trade_time and 5 * run_number % 60 * 5 == 0) or (not is_trade_time and 5 * run_number % 60 * 1 == 0): # for each symbol ...
                # These are for each symbol ...
                save_ohlc_for_chart(df)
                save_extra_features_df()

            if not is_busy_time and 931 < current_hh_mm_ny and not checkmark_map.get(f'{symbol}-MARK_GAP') :
                detect_a_mark_market_gap(symbol, df)  # need to happen one time after 9:30
                checkmark_map[f'{symbol}-MARK_GAP'] = 'Done'

            dump_application_state_to_file()

            if not is_busy_time:
                logger.info(f"key_levels_df\n{key_levels_df[key_levels_df['symbol']== symbol].to_markdown()}")

            print_application_state(application_state, msg='application_state:')

            symbol_end_time = time.time()
            symbol_run_spend_time = round(symbol_end_time - symbol_start_time, 2)
            logger.warning(f'------------------- {symbol}, {unique_run_number}, symbol_run_spend_time: {symbol_run_spend_time} seconds')

            last_candles_visit_map[symbol] = df['date'].iloc[-1] # keeps the last record we visited for each symbol...
            checkmark_map[f'{symbol}-LAST_VISIT'] = df['date'].iloc[-1] # keeps the last record we visited for each symbol...
        # END:  for symbol in app_config['symbols']:
        # in the WHILE TRUE...
        if (not is_busy_time) and (5 * run_number % 60 * 2 == 0):
            save_all_csv_files()

        # End WHILE TRUE
        end_time = time.time()

        sleep_enough()

        consequence_exception = 0
        check_health_status.write_health_status(portfolio_id)

      except Exception as e:
          consequence_exception = consequence_exception + 1
          logger.error(f"@@@@ error: {e}")
          logger.warning(traceback.format_exc())
          time.sleep(20)

          if consequence_exception == 3:
              email_utils.send_email('saeed.bx1@yahoo.com', f"error in {portfolio_id} - {app_config['user_name']}",
                                           body=f"Error in {app_config['user_name']} <br>{e}<br\><br\><br\>{traceback.format_exc()}")

          if isinstance(e, ConnectionError):
              # set a flag and set connection in loop .. exists if riase exceptin
              logger.error("@@@@ It's a ConnectionError, try to reconnect ")
              ib = create_ib_connection()
              logger.warning("Done.")
