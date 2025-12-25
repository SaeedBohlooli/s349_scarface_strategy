import logging
logger = logging.getLogger(__name__)
import pandas as pd
from trading_utils import number_utils

def calculate_PDL_PDH(df, symbol, day_of_week, application_state):

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

    logger.info(f"Previous Day RTH High: {day_high}")
    logger.info(f"Previous Day RTH Low: {day_low}" )

    application_state['levels'].setdefault(symbol, {})['PDH'] = day_high
    application_state['levels'].setdefault(symbol, {})['PDL'] = day_low
    return


def all_levels_in(application_state, symbol, levels=['PDL', 'PDH', 'PMH', 'PML','5MH', '5ML']):
    # if a level is not there ,will return False

    for level in levels:
        if application_state.get('levels').get(symbol).get(level) is None:
            return False
    return True

def find_add_PMH_PML(application_state, df, symbol):

    wait_until_end_of_period = True

    pml, pmh = find_session_high_and_low(df, start="04:00", end="09:29", wait_until_end_of_period= wait_until_end_of_period)
    if number_utils.is_valid_price(pmh) and number_utils.is_valid_price(pml) and pmh != -1 and pml != -1:
        application_state['levels'].setdefault(symbol, {})['PMH'] = pmh
        application_state['levels'].setdefault(symbol, {})['PML'] = pml


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


def find_add_5MH_5ML(application_state, df, symbol):

    wait_until_end_of_period = True

    x5mh, x5ml = find_session_high_and_low(df, start="09:30", end="09:34", wait_until_end_of_period= wait_until_end_of_period)
    if number_utils.is_valid_price(x5mh) and number_utils.is_valid_price(x5ml) and x5mh != -1 and x5ml != -1:
        application_state['levels'].setdefault(symbol, {})['5MH'] = x5mh
        application_state['levels'].setdefault(symbol, {})['5ML'] = x5ml

    return
