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


def draw_w_plotly_w_subplot_oirg_no_slidebar(df, chart_title='title'):

    logger.info(f"in draw_w_plotly_w_subplot:\n {df[-20:].to_markdown()}")

    df['date'] = pd.to_datetime(df['date'])
    end_time = df['date'].max() + pd.Timedelta(minutes=10)

    start_time = df['date'].min()
    start_time_slider = end_time - pd.Timedelta(days=1) # this is for slider to show last 4 hrs

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
    # fig.update_layout(
    #     title=f'{chart_title}',
    #     width=1700,
    #     height=1200)
    #

    fig.update_layout(
        title=f'{chart_title}',
        width=1700,
        height=1200,
        xaxis=dict(
            range=[start_time_slider, end_time],  # 👈 sets visible window
            rangeslider=dict(
                visible=True,
                thickness=0.05
            )
        ),
        xaxis2=dict(rangeslider=dict(visible=False))  # hide 2nd subplot slider
    )
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
                range=[start_time_slider, end_time],  # limit slider to last 4 hours
                thickness=0.05  # Smaller value = thinner slider (default is ~0.1)
            )
        )
    )
    # chart is based on UTC, so we cut the chart ...
    fig.update_xaxes(range=[start_time, end_time], row=1, col=1)
    fig.update_xaxes(range=[start_time, end_time], row=2, col=1)
    fig.update_xaxes(showticklabels=True, row=1, col=1)  # showing X lables in the chart ...

    return fig
def draw_w_plotly_w_subplot(df, chart_title='title'):

    logger.info(f"in draw_w_plotly_w_subplot:\n {df[-20:].to_markdown()}")

    df['date'] = pd.to_datetime(df['date'])
    end_time = df['date'].max() + pd.Timedelta(minutes=10)

    start_time = end_time - pd.Timedelta(hours=8)

    # Set 'date' as the index
    df.set_index('date', inplace=True)

    # Create a subplot: (2 rows, shared x-axis)
    fig = make_subplots(rows=1, cols=1, shared_xaxes=True,
                        vertical_spacing=0.05,
                        #row_heights=[0.8, 0.2],
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


    #
    # fig.add_trace(go.Bar(
    #     x=df.index,
    #     y=df["volume"],
    #     name="Volume",
    #     marker_color="orange"
    # ), row=2, col=1)
    #


    # # add volume ...
    # fig.add_trace(go.Scatter(
    #     x=df.index,
    #     y=df['volume'],
    #     line=dict(color='orange', width=2),
    #     name='Volume'
    # ), row=2, col=1)


    #
    # fig.update_layout(
    #     title=f'{chart_title}',
    #     width=1700,
    #     height=1200)
    #

    fig.update_layout(
        title=f'{chart_title}',
        width=1700,
        height=1200,
        xaxis=dict(
            range=[start_time, end_time],  # 👈 focus last 4 hours
            rangeslider=dict(visible=True, thickness=0.05),
            type="date",
            rangebreaks=[
                dict(bounds=["sat", "mon"]),  # skip weekends
                dict(bounds=[0, 3.5], pattern="hour"),  # skip 00:00–09:30
                dict(bounds=[20, 24], pattern="hour"),  # skip 16:00–24:00
            ]
        ),

    )
    # sometimes slidebar overlaps ... this is the fix.
    # fig.update_layout(
    #     xaxis=dict(rangeslider=dict(visible=True)),
    #     xaxis2=dict(rangeslider=dict(visible=False)),  # Prevent overlapping in ATR subplot
    # )

    # # fix for slide bar range ..
    # fig.update_layout(
    #     xaxis=dict(
    #         rangeslider=dict(
    #             visible=True,
    #             range=[start_time_slider, end_time],  # limit slider to last 4 hours
    #             thickness=0.05  # Smaller value = thinner slider (default is ~0.1)
    #         )
    #     )
    # )
    # chart is based on UTC, so we cut the chart ...
    # fig.update_xaxes(range=[start_time, end_time], row=1, col=1)
    # fig.update_xaxes(range=[start_time, end_time], row=2, col=1)
    # fig.update_xaxes(showticklabels=True, row=1, col=1)  # showing X lables in the chart ...

    return fig

def draw_w_plotly_w_subplot_test(df, chart_title='title'):
    import pandas as pd
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    fig = go.Figure()
    end_time = df["date"].max()
    start_time = end_time - pd.Timedelta(hours=4)
    fig.add_trace(go.Scatter(
        x=df["date"],
        y=df["close"],
        mode="lines",
        name="Price"
    ))

    # ------------------------
    # Layout: last 4 hours focused + rangeslider
    # ------------------------
    fig.update_layout(
        xaxis=dict(
            range=[start_time, end_time],  # ⬅ initial view
            rangeslider=dict(visible=True),  # scroll bar
            type="date"
        ),
        yaxis=dict(title="Price"),
        title="Example: Last 4 Hours Focused"
    )

    return fig

def draw_objects(fig, df, symbol, time_frame):
    for i in range(len(df)):
        if df['symbol'].iloc[i] == symbol and df['time_frame'].iloc[i] == time_frame:
            color = df['color'].iloc[i]
            price = df['price_1'].iloc[i]
            object = df['object'].iloc[i]
            memo = df['memo'].iloc[i]
            fig.add_hline(y=price, line_color=color, line_dash = object , annotation_text = memo)

    return fig

def add_start_finish_day(fig, df):
    logger.info(f"in add_start_finish_day")
    # Extract unique trading dates (calendar days)
    unique_days = df['date'].dt.normalize().unique()

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

def load_ohlc_file_to_df(portfolio_id='p700', symbol='TSLA', time_frame='1min'):
    file = f'{get_charts_dir(portfolio_id)}/{symbol}-{time_frame}.csv'
    logger.info(f"load_ohlc_file_to_df, reading file: {file}")

    df = pd.read_csv(file)
    df['date'] = pd.to_datetime(df['date'])

    if app_config['chart']['cutoff_in_hours'] !=0 :  # cut off hours ...
        # find the cutoff timestamp
        cut_off_hours = app_config['chart']['cutoff_in_hours']
        cutoff = df['date'].max() - pd.Timedelta(hours=cut_off_hours)
        logger.info(f"cutoff: {cutoff}")
        # keep only rows older than cutoff
        df = df[df['date'] < cutoff]

    df = df[-app_config['chart']['1m_candles']:]

    logger.info(f"in load_ohlc_file_to_df, df: \n{df[-5:].to_markdown()}")
    return df

def load_file_to_drawing_objects_df():
    file = f'{get_charts_dir(portfolio_id)}/10-drawing_objects_df.csv'
    logger.info(f"reading file: {file}")
    df = pd.read_csv(file)
    logger.info(f"drawing_objects_df:\n{df[1:].to_markdown()}")
    return df
def chart_orch(df1, portfolio_id='p700', symbol='TSLA', time_frame='1min'):
    df = df1.copy()
    logger.info(df[-12:].to_markdown())

    first_order_date = df.iloc[0]['date']
    last_order_date = df.iloc[-1]['date']
    logger.info(f"first_order_date: {first_order_date}, last_order_date: {last_order_date} , len(df): {len(df)} chart_1m_candles: {app_config['chart']['1m_candles']}")

    # draw plots
    # fig = draw_w_plotly_w_subplot(df, chart_title=f'{symbol}-{time_frame}')
    fig = draw_w_plotly_w_subplot(df, chart_title=f'{symbol}-{time_frame}')
    logger.info(f"\n{df[-10:].to_markdown()}")

    return fig

def mark_market_time_only_last_one(fig,df):
    logger.info(f"in mark_market_time_only_last_one")

    last_day = df['date'].dt.normalize().max()
    market_start = last_day + pd.Timedelta(hours=9, minutes=30)
    market_end = last_day + pd.Timedelta(hours=16, minutes=0)
    fig.add_vrect(
        x0=market_start, x1=market_end,
        fillcolor="lightgreen",
        opacity=0.2,
        layer="below",
        line_width=0,
    )

    return fig

def mark_before_after_hours(fig, df):  # IS VERY SLOOW ... so we marke only last
    logger.info(f"in mark_before_after_hours")

    market_start = df["date"].dt.normalize() + pd.Timedelta(hours=9, minutes=30)
    market_end = df["date"].dt.normalize() + pd.Timedelta(hours=16, minutes=0)


    # Add shaded rectangles for pre-market / after-market
    for start, end in zip(market_start, market_end):
        fig.add_vrect(
            x0=start, x1=end,
            fillcolor="lightgreen",
            opacity=0.2,
            layer="below",
            line_width=0,
        )
    logger.info(f"in add_start_finish_day, Done!")

    return fig

@app.route('/')
def index():

    portfolio_id = 'p250'
    app_config = load_app_config(portfolio_id)
    #support_resistance_map = load_support_resistance_map_from_file()
    drawing_objects_df = load_file_to_drawing_objects_df()
    plots = []
    for symbol in app_config['symbols']:
        logger.info(f"================== {symbol}")
        time_frame = '1min'
        df = load_ohlc_file_to_df(portfolio_id='p250', time_frame=time_frame, symbol=symbol)
        fig1 = chart_orch(df, portfolio_id='p250', time_frame=time_frame, symbol=symbol)
        fig1 = draw_objects(fig1,drawing_objects_df, symbol=symbol, time_frame=time_frame )
        fig1 = add_start_finish_day(fig1, df)
        # fig1 = mark_before_after_hours(fig1, df)   WAS VERY SLOW
        fig1 = mark_market_time_only_last_one(fig1, df)
        plot_html = pio.to_html(fig1, full_html=False)

        plots.append(plot_html)

    logger.info(f"Done!")
    return render_template("index.html", plots=plots)


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
