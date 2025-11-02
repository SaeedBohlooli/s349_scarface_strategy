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


def capture_df_starting_hour_x_on_last_day(df, date_f='date', cutoff_time="13:00"):
    # print(f"in capture_df_starting_hour_x_on_last_day: \n{df[-1:].to_markdown()}")
    df = df.copy()
    df[date_f] = pd.to_datetime(df[date_f])

    # Find the last trading day in the DataFrame
    last_day = df[date_f].dt.normalize().max()

    # Create masks
    mask_time = df[date_f].dt.time >= pd.to_datetime(cutoff_time).time()
    mask_day = df[date_f].dt.normalize() == last_day

    # Keep everything aftere that cutoff on the last day, and all prior days
    cut_df = df[(mask_day & mask_time)]
    return cut_df
