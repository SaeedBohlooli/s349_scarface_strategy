import json
import os
import logging
import pandas as pd
import configparser
from datetime import datetime
import yaml

def setup_logger(name, level=logging.INFO, fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s'):
    logger = logging.getLogger(name)
    # logger.setLevel(level)
    logger.setLevel(logging.INFO)

    if not logger.handlers:  # Prevent adding multiple handlers

        handler = logging.StreamHandler()
        formatter = logging.Formatter(fmt)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.propagate = False
    return logger

logger = setup_logger(__name__, level=logging.WARNING)

def load_config(path = 'config.yaml') -> dict:
    with open(path, 'r') as file:
        config = yaml.safe_load(file)
    return config

def convert_column_timezone(df, from_column='date', to_column='date_est', from_zone='UTC', to_zone='America/New_York'):
    from_column_tmp = from_column + '_tmp'
    df[from_column_tmp] = pd.to_datetime(df[from_column])
    df[from_column_tmp] = df[from_column_tmp].dt.tz_localize(from_zone)

    # Convert from UTC to Eastern Time
    df[to_column] = df[from_column_tmp].dt.tz_convert(to_zone)
    logger.debug(f"df[-3:].to_markdown():\n {df[-10:].to_markdown()}")
    df = df.drop(columns=[from_column_tmp])
    return df