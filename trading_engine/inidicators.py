import logging
logger = logging.getLogger(__name__)
import pandas as pd
from finta import TA
import numpy as np

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


def populate_emas(df, periods=[9, 21]):
    for p in periods:
        df[f'ema_{p}'] = df['close'].ewm(span=p, adjust=False).mean()
    return df

def populate_vwap(df):
    """
    Compute intraday VWAP, resetting at 09:30 each day.
    Requires 'date', 'high', 'low', 'close', 'volume' columns.
    """
    df = df.copy()
    df['_date_parsed'] = pd.to_datetime(df['date'])
    df['_trade_date'] = df['_date_parsed'].dt.date

    # Identify session start: first bar at or after 09:30 each day
    session_mask = df['_date_parsed'].dt.time >= pd.Timestamp("09:30").time()

    # Typical price
    df['_tp'] = (df['high'] + df['low'] + df['close']) / 3.0
    df['_tp_vol'] = df['_tp'] * df['volume']

    # Cumulative sums reset at each new trading day's 09:30
    # We create a session group: increments when we cross 09:30
    is_session_start = session_mask & (~session_mask.shift(1, fill_value=False))
    df['_session_group'] = is_session_start.cumsum()

    # Only compute VWAP for RTH bars
    df['_cum_tp_vol'] = df.groupby('_session_group')['_tp_vol'].cumsum()
    df['_cum_vol'] = df.groupby('_session_group')['volume'].cumsum()

    df['vwap'] = np.where(df['_cum_vol'] > 0, df['_cum_tp_vol'] / df['_cum_vol'], np.nan)

    # Clean up temp columns
    df.drop(columns=[c for c in df.columns if c.startswith('_')], inplace=True)

    return df


def compute_relative_strength(stock_df: pd.DataFrame, qqq_df: pd.DataFrame, period: int = 20):
    # Ensure aligned timeframes
    merged = pd.merge(stock_df[['date', 'close']], qqq_df[['date', 'close']], on='date', suffixes=('_stock', '_qqq'))

    merged['rs_ratio'] = merged['close_stock'] / merged['close_qqq']
    merged['rs_ema'] = merged['rs_ratio'].ewm(span=period, adjust=False).mean()
    merged['rs_roc'] = merged['rs_ema'].pct_change(periods=period)

    merged = merged.fillna(0)
    return merged[['date', 'rs_ratio', 'rs_ema', 'rs_roc']]

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
            logger.warning("@ get_930_open(), df does not have open for 9:30.")
            tmp_df = df[df['date'].dt.date == latest_date]
            if len(tmp_df) >0:
                return tmp_df['open'].iloc[-1]
            else:
                logger.warning("@ get_930_open(), df does not have open for same day, so we we return last record")
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
