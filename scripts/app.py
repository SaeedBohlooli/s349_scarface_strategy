import sys

sys.path.insert(0, f'../')
import plotly.io as pio
import plotly.graph_objects as go

import logging
import os.path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import configparser
from plotly.subplots import make_subplots

import datetime
from utils import Constants
from utils import miscutils

# logger = logging.getLogger(__name__)
logger = miscutils.setup_logger(__name__, logging.INFO)
logger.info('g')

from flask import Flask, render_template
import plotly.graph_objs as go
import plotly
import json
import plotly.io as pio

app = Flask(__name__)

portfolio_id = 'p250'
configs_folder = f'../scripts/configs'
config_file = f'{configs_folder}/app-config.yaml'
portfolio_dir = f'../../portfolios/results/{portfolio_id}'
reports_dir = f'../../portfolios/reports/{portfolio_id}'
log_dir = f'../../portfolios/logs/{portfolio_id}'
detailed_log_dir = f'../../portfolios/detailed-logs/{portfolio_id}'
charts_dir = f'../../portfolios/charts/{portfolio_id}'

def load_app_config(portfolio_id):
    global app_config
    logger.warning(f"loading app_config ....")
    app_config = miscutils.load_config(f'{configs_folder}/config-{portfolio_id}.yaml')
    logger.info(f"loaded.")
    return app_config

def get_portfoilo_dir(portfolio_id):
    base_dir = f'../../portfolios'
    portfolio_dir = os.path.join(base_dir, 'results', portfolio_id)
    return portfolio_dir

def get_charts_dir(portfolio_id):
    base_dir = f'../../portfolios'
    portfolio_dir = os.path.join(base_dir, 'charts', portfolio_id)
    return portfolio_dir

def convert_time_zone(df, from_tz, to_tz):
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df['date'] = df['date'].dt.tz_localize(from_tz)
    df['date'] = df['date'].dt.tz_convert(to_tz)
    df['date'] = df['date'].dt.tz_localize(None)
    return df

def load_support_resistance_map_from_file():
    file_path = os.path.join(charts_dir, 'support_resistance_1min_previous_day.json')
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            logger.info(f"loading from file_path: {file_path} ")
            support_resistance_map = json.load(f)
        logger.info(f"loaded, support_resistance_map: {support_resistance_map}")
    else:
        logger.warning(f"file isn o there ,{file_path}")
    return  support_resistance_map


def draw_w_plotly_w_subplot(df, chart_title='title'):

    logger.info(f"in draw_w_plotly_w_subplot:\n {df[-20:].to_markdown()}")

    df['date'] = pd.to_datetime(df['date'])
    end_time = df['date'].max()
    start_time = df['date'].min()

    # Set 'date' as the index
    df.set_index('date', inplace=True)

    # Create a subplot: (2 rows, shared x-axis)
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        vertical_spacing=0.05,
                        row_heights=[0.8, 0.2],
                        subplot_titles=(f'OHLC Chart {chart_title}', f'Volume {chart_title}'))

    # Candlestick chart
    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df['open'],
        high=df['high'],
        low=df['low'],
        close=df['close'],
        name='Candles'
    ), row=1, col=1)

    # add volume ...
    fig.add_trace(go.Scatter(
        x=df.index,
        y=df['volume'],
        line=dict(color='orange', width=2),
        name='Volume'
    ), row=2, col=1)


    #
    fig.update_layout(
        title=f'{chart_title}',
        width=1700,
        height=1200)

    # sometimes slidebar overlaps ... this is the fix.
    fig.update_layout(
        xaxis=dict(rangeslider=dict(visible=True)),
        xaxis2=dict(rangeslider=dict(visible=False)),  # Prevent overlapping in ATR subplot
    )

    # fix for slide bar range ..
    fig.update_layout(
        xaxis=dict(
            rangeslider=dict(
                visible=True,
                range=[start_time, end_time],  # limit slider to last 4 hours
                thickness=0.05  # Smaller value = thinner slider (default is ~0.1)
            )
        )
    )
    # chart is based on UTC, so we cut the chart ...
    fig.update_xaxes(range=[start_time, end_time], row=1, col=1)
    fig.update_xaxes(range=[start_time, end_time], row=2, col=1)

    return fig


def add_support_resistance(fig, symbol, support_resistance_map):
    support = support_resistance_map.get(f'{symbol}-1min-previous_day-RTH-high', -1)
    resistance = support_resistance_map.get(f'{symbol}-1min-previous_day-RTH-low',-1)
    fig.add_hline(y=support, line_color="green", line_dash = "dash" , annotation_text = f"PDH @ {support}")
    fig.add_hline(y=resistance, line_color="blue", line_dash = "dash", annotation_text = f"PDL @ {resistance}")

    return fig

def add_start_finish_day(fig, df):
    # Extract unique trading dates (calendar days)
    unique_days = df.index.normalize().unique()

    for day in unique_days:
        # Build timestamps for that day
        open_time = pd.Timestamp(day) + pd.Timedelta(hours=9, minutes=30)
        close_time = pd.Timestamp(day) + pd.Timedelta(hours=16)

        # Add vertical line at 9:30
        fig.add_vline(
            x=open_time.to_pydatetime(),
            line_color="green",
            line_dash="dot",
        )

        # Add vertical line at 16:00
        fig.add_vline(
            x=close_time.to_pydatetime(),
            line_color="red",
            line_dash="dot",
        )

    return fig

def load_df(portfolio_id='p700', symbol='TSLA', time_frame='1min'):
    file = f'{get_charts_dir(portfolio_id)}/{symbol}-{time_frame}.csv'
    logger.info(f"reading file: {file}")

    df = pd.read_csv(file)
    df = df[-app_config['chart_1m_candles']:]
    return df

def chart_orch(df, portfolio_id='p700', symbol='TSLA', time_frame='1min'):

    logger.info(df[-12:].to_markdown())

    first_order_date = df.iloc[0]['date']
    last_order_date = df.iloc[-1]['date']
    logger.info(f"first_order_date: {first_order_date}, last_order_date: {last_order_date} , len(df): {len(df)} chart_1m_candles: {app_config['chart_1m_candles']}")

    # draw plots
    fig = draw_w_plotly_w_subplot(df, chart_title=f'{symbol}-{time_frame}')
    logger.info(f"\n{df[-10:].to_markdown()}")

    return fig

@app.route('/')
def index():

    portfolio_id = 'p250'
    app_config = load_app_config(portfolio_id)
    support_resistance_map = load_support_resistance_map_from_file()

    plots = []
    for symbol in app_config['symbols']:
        df = load_df(portfolio_id='p250', time_frame='1min', symbol=symbol)
        fig1 = chart_orch(df, portfolio_id='p250', time_frame='1min', symbol=symbol)
        fig1 = add_support_resistance(fig1,symbol, support_resistance_map)
        fig1 = add_start_finish_day(fig1, df)

        plot_html = pio.to_html(fig1, full_html=False)

        plots.append(plot_html)

    return render_template("index.html", plots=plots)


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
