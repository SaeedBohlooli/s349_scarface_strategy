import sys
import time

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

from flask import Flask, render_template, request
import plotly.graph_objs as go
import plotly
import json
import plotly.io as pio

app = Flask(__name__)

portfolio_id = 'p250'
configs_folder = f'../scripts/configs'
config_file = f'{configs_folder}/app-config.yaml'
portfolio_dir = f'../portfolios/results/{portfolio_id}'
reports_dir = f'../portfolios/reports/{portfolio_id}'
log_dir = f'../portfolios/logs/{portfolio_id}'
detailed_log_dir = f'../portfolios/detailed-logs/{portfolio_id}'
run_counter = 0


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
    # base_dir = f'../portfolios'
    # portfolio_dir = os.path.join(base_dir, 'charts', portfolio_id)
    # return portfolio_dir
    return charts_dir
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
        x=df['date'],
        open=df['open'],
        high=df['high'],
        low=df['low'],
        close=df['close'],
        name='Candles'
    ), row=1, col=1)

    # add volume ...
    fig.add_trace(go.Scatter(
        x=df['date'],
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
def draw_w_plotly_w_subplot_1(symbol, chart_title='title'):
    global df
    global relative_strenght_df
    global intraday_rs_df
    logger.info(f"in draw_w_plotly_w_subplot:\n {df[-20:].to_markdown()}")

    df['date'] = pd.to_datetime(df['date'])
    end_time = df['date'].max() + pd.Timedelta(minutes=10)

    relative_strenght_df['date'] = pd.to_datetime(relative_strenght_df['date'])
    intraday_rs_df['date'] = pd.to_datetime(intraday_rs_df['date'])


    hours_in_focus = int(app_config['chart']['hours_in_focus'])
    start_time = end_time - pd.Timedelta(hours=hours_in_focus)



    # Set 'date' as the index
    # df.set_index('date', inplace=True)

    # Create a subplot: (2 rows, shared x-axis)
    fig = make_subplots(rows=6, cols=1, shared_xaxes=True,
                        vertical_spacing=0.04,
                        row_heights=[0.75, 0.05, 0.05, 0.05, 0.05, 0.05],
                        subplot_titles=(f'{symbol}', f'ATR-{symbol}', f'Volume-{symbol}', f'RS-ratio-and-ema-{symbol}', f'RS-roc-{symbol}', f'RS-Rel-{symbol}'))

    # Candlestick chart
    fig.add_trace(go.Candlestick(
        x=df['date'],
        open=df['open'],
        high=df['high'],
        low=df['low'],
        close=df['close'],
        name='Candles'
    ), row=1, col=1)

    fig.update_xaxes(showticklabels=True, row=1, col=1)


    # ATR line chart
    fig.add_trace(go.Scatter(
        x=df['date'],
        y=df['atr_14'],
        line=dict(color='orange', width=2),
        name='ATR'
    ), row=2, col=1)

    fig.add_trace(go.Scatter(
        x=df['date'],
        y=df['volume'],
        line=dict(color='orange', width=2),
        name='Volume'
    ), row=3, col=1)

    fig.add_trace(go.Scatter(
        x=relative_strenght_df['date'],
        y=relative_strenght_df['rs_ratio'],
        line=dict(color='blue', width=2),
        name='rs_ratio'
    ), row=4, col=1)


    fig.add_trace(go.Scatter(
        x=relative_strenght_df['date'],
        y=relative_strenght_df['rs_ema'],
        line=dict(color='red', width=1, dash='dot'),
        name='rs_ema'
    ), row=4, col=1)

    fig.add_trace(go.Scatter(
        x=relative_strenght_df['date'],
        y=relative_strenght_df['rs_roc'],
        line=dict(color='blue', width=2),
        name='rs_roc'
    ), row=5, col=1)

    fig.add_trace(go.Scatter(
        x=intraday_rs_df['date'],
        y=intraday_rs_df['rs_rel'],
        line=dict(color='blue', width=2),
        name='rs_rel'
    ), row=6, col=1)


    fig.update_layout(
        title=f'{chart_title}',
        width=1800,
        height=1400,
        xaxis=dict(
            range=[start_time, end_time],  # limit slider to last 4 hours
            rangeslider=dict(
                visible=False,
            ),

        ),
        xaxis2=dict(
            range=[start_time, end_time],  # 👈 sets visible window
            rangeslider=dict(visible=False)  # ATR row
        ),
        xaxis3=dict(
            range=[start_time, end_time],  # 👈 sets visible window
            rangeslider=dict(visible=False)  # Volume row
        ),
        xaxis4=dict(
            range=[start_time, end_time],  # 👈 sets visible window
            rangeslider=dict(visible=False)  # Volume row
        ),
        xaxis5=dict(
            range=[start_time, end_time],  # 👈 sets visible window
            rangeslider=dict(visible=False)
        ),
        xaxis6=dict(
            range=[start_time, end_time],  # 👈 sets visible window
            rangeslider=dict(visible=True,
                    thickness=0.07  # makes it smaller so it doesn’t overlap ATR
                    )
        )
    )


    fig.update_yaxes(title_text="Price", row=1, col=1, title_standoff=20, automargin=True)
    fig.update_yaxes(title_text="Volume", row=2, col=1, title_standoff=20, automargin=True)
    fig.update_yaxes(title_text="ATR", row=3, col=1, title_standoff=20, automargin=True)
    fig.update_yaxes(title_text="RS", row=4, col=1, title_standoff=20, automargin=True)
    fig.update_yaxes(title_text="RS", row=5, col=1, title_standoff=20, automargin=True)
    fig.update_yaxes(title_text="RS Rel", row=6, col=1, title_standoff=20, automargin=True)

    # Optional: rotate x-axis labels

    return fig

def draw_w_plotly_w_subplot(df, chart_title='title'):

    logger.info(f"in draw_w_plotly_w_subplot:\n {df[-20:].to_markdown()}")

    df['date'] = pd.to_datetime(df['date'])
    end_time = df['date'].max() + pd.Timedelta(minutes=20)  # leave some space in the right ....
    hours_in_focus = int(app_config['chart']['hours_in_focus'])
    start_time = end_time - pd.Timedelta(hours=hours_in_focus)

    # Set 'date' as the index
    df.set_index('date', inplace=True)

    # Create a subplot: (2 rows, shared x-axis)
    fig = make_subplots(rows=1, cols=1, shared_xaxes=True,
                        vertical_spacing=0.05,
                        #row_heights=[0.8, 0.2],
                        subplot_titles=(f'OHLC Chart {chart_title}', f'Volume {chart_title}'))

    # Candlestick chart
    fig.add_trace(go.Candlestick(
        x=df['date'],
        open=df['open'],
        high=df['high'],
        low=df['low'],
        close=df['close'],
        name='Candles'
    ), row=1, col=1)


    #
    # fig.add_trace(go.Bar(
    #     x=df['date'],
    #     y=df["volume"],
    #     name="Volume",
    #     marker_color="orange"
    # ), row=2, col=1)
    #


    # # add volume ...
    # fig.add_trace(go.Scatter(
    #     x=df['date'],
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
        width=1800,
        height=1300,
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

def draw_objects(fig, df, drawing_objects_df, symbol, time_frame):

    for i in range(len(drawing_objects_df)):

        if drawing_objects_df['symbol'].iloc[i] == symbol and drawing_objects_df['time_frame'].iloc[i] == time_frame:
            color = drawing_objects_df['color'].iloc[i]
            price = drawing_objects_df['price_1'].iloc[i]
            line_style = drawing_objects_df['object'].iloc[i]
            memo = drawing_objects_df['memo'].iloc[i]

             # style: "solid", "dot", "dash", "longdash", "dashdot", "longdashdot"

            # fig.add_hline(y=price, line_color=color, line_dash = object , annotation_text = memo)
            # Create a horizontal line using Scatter
            x_vals = df['date']
            y_vals = [price] * len(x_vals)

            # Create a text list: only first point has text
            text_vals = [''] * (len(x_vals) - 1) + [memo]

            fig.add_trace(go.Scatter(
                x=x_vals,
                y=y_vals,
                mode='lines+text',
                line=dict(color=color, dash=line_style),
                text=text_vals,
                textposition='top right',  # always on the left
                showlegend=True,
                name=memo
            ))

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


def load_relative_strength_df_from_file(portfolio_id='p700', symbol='TSLA', time_frame='1min'):
    file = f'{charts_dir}/{symbol}-{time_frame}-relative_strength.csv'
    logger.info(f"load_relative_strength_df_from_file, reading file: {file}")

    df = pd.read_csv(file)
    df['date'] = pd.to_datetime(df['date'])

    df = df[-app_config['chart']['1m_candles']:]

    logger.info(f"in load_relative_strength_df_from_file, df: \n{df[-5:].to_markdown()}")
    return df

def load_intraday_rs_df_from_file(portfolio_id='p700', symbol='TSLA', time_frame='1min'):
    file = f'{charts_dir}/{symbol}-{time_frame}-intraday_rs_df.csv'
    logger.info(f"load_intraday_rs_df_from_file, reading file: {file}")

    df = pd.read_csv(file)
    df['date'] = pd.to_datetime(df['date'])

    df = df[-app_config['chart']['1m_candles']:]

    logger.info(f"in load_intraday_rs_df_from_file, df: \n{df[-5:].to_markdown()}")
    return df

def load_df_from_ohlc_file(portfolio_id='p700', symbol='TSLA', time_frame='1min'):
    file = f'{charts_dir}/{symbol}-{time_frame}.csv'
    logger.info(f"load_ohlc_file_to_df, reading file: {file}")

    df = pd.read_csv(file)
    df['date'] = pd.to_datetime(df['date'])

    # if app_config['chart']['cutoff_in_hours'] !=0 :  # cut off hours ...
    #     # find the cutoff timestamp
    #     cut_off_hours = app_config['chart']['cutoff_in_hours']
    #     cutoff = df['date'].max() - pd.Timedelta(hours=cut_off_hours)
    #     logger.info(f"cutoff: {cutoff}")
    #     # keep only rows older than cutoff
    #     df = df[df['date'] < cutoff]

    df = df[-app_config['chart']['1m_candles']:]

    logger.info(f"in load_ohlc_file_to_df, df: \n{df[-5:].to_markdown()}")
    return df

def load_file_to_drawing_objects_df():
    file = f'{get_charts_dir(portfolio_id)}/10-drawing_objects_df.csv'
    logger.info(f"reading file: {file}")
    df = pd.read_csv(file)
    logger.info(f"drawing_objects_df:\n{df[1:].to_markdown()}")
    return df

def load_file_to_hover_df():
    file = f'{get_charts_dir(portfolio_id)}/12-hover_df.csv'
    if os.path.exists(file):
        logger.info(f"reading file: {file}")
        df = pd.read_csv(file)
        logger.info(f"load_file_to_hover_df:\n{df[1:].to_markdown()}")
        return df
    else:
        return pd.DataFrame()


def chart_orch(df, portfolio_id='p700', symbol='TSLA', time_frame='1min'):
    logger.info(df[-12:].to_markdown())

    first_order_date = df.iloc[0]['date']
    last_order_date = df.iloc[-1]['date']
    logger.info(f"first_order_date: {first_order_date}, last_order_date: {last_order_date} , len(df): {len(df)} chart_1m_candles: {app_config['chart']['1m_candles']}")

    # draw plots
    # fig = draw_w_plotly_w_subplot(df, chart_title=f'{symbol}-{time_frame}')
    fig = draw_w_plotly_w_subplot_1(chart_title=f'{symbol}-{time_frame}')
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

def add_hover_to_chart(fig1, hover_df):
    if len(hover_df) > 0:
        signal_x = hover_df['date'].tolist()
        signal_y = hover_df['price'].tolist()
        signals = hover_df['signals'].tolist()
        colors = hover_df['color'].tolist()
        hovertexts = hover_df['text'].tolist()
        fig1.add_trace(go.Scatter(
            x=signal_x,
            y=signal_y,
            mode='text',
            text=signals,
            hovertext=hovertexts,
            hoverinfo='text',
            textposition='top center',
            textfont=dict(size=20, color=colors),
            showlegend=False
        ))

    return fig1


def create_chart_hovered_df(hover_df, symbol):
    if len(hover_df) == 0:
        return pd.DataFrame()
    df = hover_df.copy()

    df = df[df['symbol'] == symbol]
    df['date'] = df['date_1']
    df['price'] = df['price_1']
    df['text'] = df['memo']
#  ⇗ ↛ ⇧
    # http://xahlee.info/comp/unicode_geometric_shapes.html
# ◒
    mapping = {
        # Up / Positive
        'FLASH_UP': '▲',
        'UP': '▲',
        'STRONG_UP': '⏫',
        'BREAKOUT_UP': '🔥',

        # Down / Negative
        'FLASH_DOWN': '▼',
        'DOWN': '▼',
        'STRONG_DOWN': '⏬',
        'BREAKOUT_DOWN': '💥',

        # Neutral / Flat
        'NEUTRAL': '●',
        'FLAT': '▬',
        'SIDEWAYS': '○',

        # Hold / Pause
        'HOLD': '■',
        'WAIT': '⏸',

        # Exit / Stop
        'EXIT': '✖',
        'STOP': '⛔',
        'CANCEL': '❌',

        # Highlight / Special
        'ALERT': '★',
        'NEWS': '⚡',
        'VOLUME_SPIKE': '◆',

        # Highlight / Special
        'RETEST_UP': '★',
        'RETEST_DOWN': '★',

        'bullish_reversal' : '◆',
        'bearish_reversal' : '◆',

        'Candle Type': '○',

        # BUY and sell Entry
        'BUY_ENTRY-case_1': '■',
        'SELL_ENTRY-case_1': '■',
        # BUY and sell Entry
        'BUY_ENTRY-case_2': '■',
        'SELL_ENTRY-case_2': '■',

        'Screening_case_1': '○',
        'Screening_case_2': '○',
        'Screening_case_3': '○',

        'CANDLE_INFO': '○',

    }

    # Apply mapping to a new column
    df['signals'] = df['object'].map(mapping).fillna('●')  # default to circle if unknown

    df = df[['date', 'price', 'signals', 'color', 'text']]

    return df

app_config = load_app_config(portfolio_id)  # to be accisible form every where ...
backtest_date = '20250810'
charts_dir = ''
chart_rows = 2
df = pd.DataFrame()
relative_strenght_df = pd.DataFrame()
intraday_rs_df = pd.DataFrame()
@app.route('/')
def index():
    global charts_dir
    global df
    global relative_strenght_df
    global intraday_rs_df
    portfolio_id = 'p250'
    app_config = load_app_config(portfolio_id)
    backtest_date = ''
    if app_config['chart']['source'] == 'live':
        charts_dir = f'../portfolios/charts/{portfolio_id}'
    else:
        backtest_base_dir = '../portfolios/backtest-charts'
        available_dates = sorted([
            d for d in os.listdir(backtest_base_dir)
            if os.path.isdir(os.path.join(backtest_base_dir, d))
        ], reverse=True)  # sort newest first
        backtest_date = request.args.get('backtest_date')
        logger.info(f"available_dates {available_dates}")
        if backtest_date is None:
            backtest_date = available_dates[0]
        logger.info(f"backtest_date: {backtest_date}")
        charts_dir = f'../portfolios/backtest-charts/{backtest_date}/{portfolio_id}'
        time.sleep(5)

    drawing_objects_df = load_file_to_drawing_objects_df()
    hover_df = load_file_to_hover_df()
    plots = []
    logger.info(f"================== call from client run_counter: {run_counter}")

    for symbol in app_config['symbols']:
        logger.info(f"================== {symbol}")
        time_frame = '1min'

        df = load_df_from_ohlc_file(portfolio_id='p250', time_frame=time_frame, symbol=symbol)
        relative_strenght_df = load_relative_strength_df_from_file(portfolio_id='p250',time_frame=time_frame, symbol=symbol)
        intraday_rs_df = load_intraday_rs_df_from_file(portfolio_id='p250',time_frame=time_frame, symbol=symbol)
        fig1 = draw_w_plotly_w_subplot_1(symbol, chart_title=f'{symbol}-{time_frame}')
        fig1 = draw_objects(fig1,df, drawing_objects_df, symbol=symbol, time_frame=time_frame )
        fig1 = add_start_finish_day(fig1, df)
        fig1 = mark_market_time_only_last_one(fig1, df)
        chart_hovered_df = create_chart_hovered_df(hover_df, symbol)
        fig1 = add_hover_to_chart(fig1, chart_hovered_df)
        plot_html = pio.to_html(fig1, full_html=False)

        plots.append(plot_html)

    logger.info(f"Done! {run_counter}")
    if backtest_date != '':
        return render_template(
            "index.html",
            plots=plots,
            backtest_date=backtest_date,
            available_dates=available_dates  # ✅ must pass this
        )
    else:
        return render_template(
            "index.html",
            plots=plots,
            backtest_date='',
            available_dates=[])  # ✅ must pass this


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
