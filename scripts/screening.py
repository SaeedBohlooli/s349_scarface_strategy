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

portfolio_dir = f'../../portfolios/results/{portfolio_id}'
reports_dir = f'../../portfolios/reports/{portfolio_id}'
log_dir = f'../../portfolios/logs/{portfolio_id}'
detailed_log_dir = f'../../portfolios/detailed-logs/{portfolio_id}'
charts_dir = f'../../portfolios/charts/{portfolio_id}'

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
    for symbol in app_config['symbols']:
        logger.info(f"symbol: {symbol}, time_frame: {time_frame} ")
        contract = create_contract(symbol)

        df = get_historical_data(contract,app_config['historical_days'], time_frame)
        time_frame_x = time_frame.replace(' ', '')
        df.to_csv(f"{portfolio_dir}/{symbol}-{time_frame_x}.csv")
        symbols_time_frame_df_map[f'{symbol}-{time_frame_x}'] = df
        logger.info(f"in get_market_data_befre_market_start: \n{df[-5:].to_markdown()}")
    return

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

def generate_for_chart():
    for x, df in symbols_time_frame_df_map.items():
        logger.info(f"x: {x}, len(df): {len(df)}")
        parts = x.split("-")
        symbol = parts[0]
        time_frame = parts[1]
        df = df[['date','open','close', 'high', 'low', 'volume']]
        file = f"{charts_dir}/{symbol}-{time_frame}.csv"
        df.to_csv(file, index=False, mode='w')

def calculate_support_resitance_for_t_min_1():
    global support_resistance_map
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

        support_resistance_map[f'{symbol}-{time_frame}-previous_day-RTH-high'] = day_high
        support_resistance_map[f'{symbol}-{time_frame}-previous_day-RTH-low'] = day_low
    return

def generate_support_resitance_for_t_min_1_report():
    file_path = os.path.join(charts_dir, 'support_resistance_1min_previous_day.json')

    logger.warning(f"support_resistance_map:\n{pprint.pformat(support_resistance_map)}")

    with open(file_path, 'w') as f:
        logger.info(f"saving at file_path: {file_path}")
        json.dump(support_resistance_map, f, indent=4)
        logger.info(f"saving done. ")

if __name__ == "__main__":
    app_config = load_app_config(portfolio_id)
    ib_config = load_ib_config()
    ib = create_ib_connection()
    symbols_time_frame_df_map = {}
    support_resistance_map = {}

    get_market_data_befre_market_start('1 day')
    get_market_data_befre_market_start('1 min')
    calculate_support_resitance_for_t_min_1()
    generate_support_resitance_for_t_min_1_report()
    while True:
        get_market_data_befre_market_start('1 min')
        generate_for_chart()
        pass
        break
