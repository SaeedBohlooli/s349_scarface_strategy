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

logger = miscutils.setup_logger(__name__, level=Constants.LOGGING_LEVEL)

portfolio_id = 'p250'
configs_folder = f'../scripts/configs'
config_file = f'{configs_folder}/app-config.yaml'

portfolio_dir = f'../portfolios/results/{portfolio_id}'
reports_dir = f'../portfolios/reports/{portfolio_id}'
log_dir = f'../portfolios/logs/{portfolio_id}'
detailed_log_dir = f'../portfolios/detailed-logs/{portfolio_id}'
charts_dir = f'../portfolios/charts/{portfolio_id}'

os.makedirs(portfolio_dir, exist_ok=True)
os.makedirs(reports_dir, exist_ok=True)
os.makedirs(log_dir, exist_ok=True)
os.makedirs(detailed_log_dir, exist_ok=True)
os.makedirs(charts_dir, exist_ok=True)
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
def get_market_data_befre_market_start(time_frame = '1 day'):
    global symbols_time_frame_df_map
    logger.info(f"symbol: {symbol}, time_frame: {time_frame} ")
    contract = create_contract(symbol)

    df = get_historical_data(contract, app_config['historical_days'], time_frame)
    time_frame_x = time_frame.replace(' ', '')
    df.to_csv(f"{portfolio_dir}/{symbol}-{time_frame_x}.csv")
    symbols_time_frame_df_map[f'{symbol}-{time_frame_x}'] = df
    logger.info(f"in get_market_data_befre_market_start: \n{df[-5:].to_markdown()}")
    return df

def create_contract(symbol):
    if symbol == 'MNQ':
        contract = Future('MNQ', '202509', 'CME')
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

def create_ohlc_for_chart(df):
    logger.info(f"in generate_for_chart, symbol: {symbol}, len(df): {len(df)}")
    df = df[['date','open', 'high', 'low', 'close', 'volume']]
    file = f"{charts_dir}/{symbol}-{time_frame.replace(' ', '')}.csv"
    df.to_csv(file, index=False, mode='w')

def calculate_support_resitance_for_t_min_1():
    global support_resistance_map
    global key_levels_df
    for x, df in symbols_time_frame_df_map.items():
        logger.info(f"x: {x}, len(df): {len(df)}")
        parts = x.split("-")
        symbol = parts[0]
        time_frame = parts[1]
        if time_frame != '1min':
            continue

        df = df[['date','open','close', 'high', 'low', 'volume']]
        # filter to that day between 9:30–16:00
        df = df.set_index('date')  # set as index
        df.index = pd.to_datetime(df.index)
        logger.info(f"get_previous_bday().date(): {get_previous_bday().date()}")
        mask = (df.index.date == get_previous_bday().date())
        df_rth = df.loc[mask].between_time("09:30", "16:00")

        # calculate high and low
        day_high = df_rth["high"].max()
        day_low = df_rth["low"].min()

        logger.info(f"Previous weekday RTH High: {day_high}")
        logger.info(f"Previous weekday RTH Low: {day_low}" )

        add_to_drawing_objects_df(symbol=symbol, time_frame=time_frame,  object='dash', color='Blue', price_1=day_high, memo=f'PDH {day_high}', unique_id=f'{symbol}-{time_frame}-PDH' )
        add_to_drawing_objects_df(symbol=symbol, time_frame=time_frame,  object='dash', color='Blue', price_1=day_low, memo=f'PDL {day_low}' , unique_id=f'{symbol}-{time_frame}-LDH' )
        add_to_key_levels_df(symbol=symbol, time_frame=time_frame, key_level='PDH', price=day_high, memo=f'PDH {day_high}')
        add_to_key_levels_df(symbol=symbol, time_frame=time_frame, key_level='PDL', price=day_low, memo=f'PDH {day_high}')
    return


def  add_to_key_levels_df(symbol, time_frame, key_level, price, memo='', unique_id=''):
    global key_levels_df
    if price> 0:
        if unique_id == '':
            unique_id = f'{symbol}--{time_frame}--{key_level}'
        data = {'symbol': symbol , 'time_frame': time_frame, 'key_level': key_level, 'price': price, 'memo' : memo, 'unique_id': unique_id}
        key_levels_df = pd.concat([key_levels_df, pd.DataFrame([data])])
        key_levels_df = key_levels_df.drop_duplicates(subset=['unique_id'], keep='last') # TODO chage to unique_id later ...
    return key_levels_df

def add_to_drawing_objects_df(symbol='TSLA', time_frame='1m', object='dash', color='', date_1='', price_1=0, date_2='', price_2=0, memo = '', unique_id = 1 ):
    global drawing_objects_df
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

def add_5_mins_low_high_to_drawing_objects_df(low_for_5_min, high_for_5_min):
    if low_for_5_min != -1:
        add_to_drawing_objects_df(symbol=symbol, time_frame=time_frame, object='dash', color='Red', price_1=low_for_5_min, memo=f'low for 5 mins {low_for_5_min}', unique_id=f'{symbol}-{time_frame}-LOW_5_MIN')
    if high_for_5_min != -1:
        add_to_drawing_objects_df(symbol=symbol, time_frame=time_frame, object='dash', color ='Red', price_1=high_for_5_min, memo=f'high for 5 mins {high_for_5_min}', unique_id=f'{symbol}-{time_frame}-HIGH_5_MIN')

    return

def add_pre_market_mins_low_high_to_drawing_objects_df(low_pre_market, high_pre_market):
    if low_pre_market != -1:
        add_to_drawing_objects_df(symbol=symbol, time_frame=time_frame, object='dash', color='Red', price_1=low_pre_market, memo=f'low for pre-market {low_pre_market}', unique_id=f'{symbol}-{time_frame}-PML')
    if high_pre_market != -1:
        add_to_drawing_objects_df(symbol=symbol, time_frame=time_frame, object='dash', color ='Red', price_1=high_pre_market, memo=f'high for pre-market {high_pre_market}', unique_id=f'{symbol}-{time_frame}-PMH')

    return


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
def detect_breakout_retest_ver1(df, key_levels, tolerance=0.0005):
    """
    Detect breakout or retest on the latest candle only.

    df: DataFrame with at least ['open','high','low','close']
    key_levels: list of floats (support/resistance levels)
    tolerance: allowable distance to treat as "touch" (default 0.1%)

    Returns: list of signals for the latest candle
             Each signal is a tuple: (event_type, level, candle_index)
             event_type ∈ {"breakout_up", "breakout_down", "retest_up", "retest_down"}
    """
    global signals
    if len(df) < 2:
        return signals  # need at least 2 candles to compare breakout

    latest = df.iloc[-1]
    prev = df.iloc[-2]
    idx = df.iloc[-1]['date']

    for level in key_levels:
        # --- Breakout detection ---
        if prev["close"] < level and latest["close"] > level:
            signals.append(("breakout_up", level, idx))
        elif prev["close"] > level and latest["close"] < level:
            signals.append(("breakout_down", level, idx))

        # --- Retest detection ---
        if abs(latest["low"] - level) <= level * tolerance and latest["close"] > level:
            signals.append(("retest_up", level, idx))
        elif abs(latest["high"] - level) <= level * tolerance and latest["close"] < level:
            signals.append(("retest_down", level, idx))

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


def create_hover_df(signals):
    global hover_df

    hovers_list = []
    for s in signals:
        logger.info(f"create_hover_df, s:{s}")
        event = s[0]
        price_1 = s[1]
        date_1 = s[2]
        clr = 'Green' if 'up' in event else 'Red'
        if 'breakout_up' in event:
            obj = 'FLASH_UP'
        elif 'breakout_down' in event:
            obj = 'FLASH_DOWN'
        elif 'retest_up' in event:
            obj = 'RETEST_UP'
        elif 'retest_down' in event:
            obj = 'RETEST_DOWN'
        else:
            obj = 'NA'
        data = {
            'symbol': symbol,
            'time_frame': time_frame,
            'object': obj,
            'color': clr,
            'price_1': price_1,
            'date_1': date_1,
            'memo': f'{event} {price_1}',
            'unique_id': f'{symbol}--{date_1}--{price_1}'
        }
        hovers_list.append(data)
    if len(hovers_list) > 0:
        hover_df = pd.concat([hover_df, pd.DataFrame(hovers_list)], ignore_index=True)
        hover_df = hover_df.drop_duplicates()
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
                key_level=key_level,
                price=price,
                memo=memo
            )
            add_to_drawing_objects_df(symbol=symbol, time_frame=time_frame, object='dot', color='Black',
                                      price_1=price, memo=f'{memo}',
                                      unique_id=f'{symbol}-{time_frame}-{key_level}')
if __name__ == "__main__":


    app_config = load_app_config(portfolio_id)
    ib_config = load_ib_config()
    ib = create_ib_connection()
    symbols_time_frame_df_map = {}
    # support_resistance_map = {}
    drawing_objects_df = pd.DataFrame()
    hover_df = pd.DataFrame( columns=['symbol', 'time_frame', 'object', 'color', 'date_1', 'price_1', 'date_2', 'price_2', 'memo','unique_id'])
    key_levels_df = pd.DataFrame( columns=['symbol', 'time_frame', 'key_level', 'price', 'memo','unique_id'])

    for symbol in app_config['symbols']:
        get_market_data_befre_market_start('1 day')
        get_market_data_befre_market_start('1 min')
        calculate_support_resitance_for_t_min_1()
        # write_support_resitance_for_t_min_1_report()
    j = 0
    while True:
        start_time = time.time()
        j += 1
        now = datetime.datetime.now()
        run_date_time = now.strftime("%Y-%m-%d__%H-%M")
        logger.info(f"==================== j: {j}  run_date_time: {run_date_time}")
        for symbol in app_config['symbols']:
            time_frame = '1 min'
            signals = []

            df = get_market_data_befre_market_start('1 min')
            create_ohlc_for_chart(df)

            low_for_5_min, high_for_5_min = find_session_high_and_low(df, start="09:30", end="09:35")
            add_5_mins_low_high_to_drawing_objects_df(low_for_5_min, high_for_5_min)
            add_to_key_levels_df(symbol, time_frame,'low_for_5_min', low_for_5_min, 'low_for_5_min' )
            add_to_key_levels_df(symbol, time_frame,'high_for_5_min', high_for_5_min, 'high_for_5_min' )

            low_for_pre_market, high_for_pre_market = find_session_high_and_low(df, start="04:00", end="09:30", wait_until_end_of_period=False)
            add_pre_market_mins_low_high_to_drawing_objects_df(low_for_pre_market, high_for_pre_market)
            add_to_key_levels_df(symbol, time_frame,'low_for_pre_market', low_for_pre_market, 'low_for_pre_market' )
            add_to_key_levels_df(symbol, time_frame,'high_for_pre_market', high_for_pre_market, 'high_for_pre_market' )
            add_test_key_levels()

            key_levels_list = get_key_levels_list()
            signals = detect_breakout_retest_ver1(df, key_levels_list)
            logger.info(f"key_levels_df:\n {key_levels_df.to_markdown()}")
            logger.info(f"key_levels_list: {key_levels_list}")
            logger.info(f"signals: {signals}")
            hover_df = create_hover_df(signals)

            save_df_to_csv_a_tabular(drawing_objects_df, '10-drawing_objects_df.csv', mode='w', dir=charts_dir)
            save_df_to_csv_a_tabular(hover_df, dir=charts_dir, file_name='12-hover_df.csv', mode='a')

            if j % 4 == 0:
                app_config = load_app_config(portfolio_id)

        end_time = time.time()

        sleep_enough()
        # pass
        # break
