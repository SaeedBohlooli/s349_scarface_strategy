import logging
import traceback

logger = logging.getLogger(__name__)
from trading_utils import date_utils

def check_buy_sell_condition(app_config, application_state, case, symbol, market_data):

    can_buy = False
    can_sell = False
    res_str = ''
    long_level = -1
    short_level = -1

    try:
        df = market_data.dfs_map(symbol)
        if df is None:
            logger.warning(f"check_buy_sell_condition, no market data for symbol: {symbol}")
            return None
        precondition = app_config['cases'][case]['precondition']
        precondition_eval = eval(precondition)
        if not precondition_eval:
            logger.warning(f"check_buy_sell_condition, precondition not met for case: {case}, symbol: {symbol}, precondition: {precondition}")
            return None
        levels = application_state['symbols'][symbol] # used in config

        can_replace_level = app_config['cases'][case]['can_replace_level']
        long_level = eval(app_config['cases'][case]['long']['level'])
        short_level = eval(app_config['cases'][case]['short']['level'])

        long_level = replace_level_if_needed(app_config, df, symbol, 'up', can_replace_level, long_level)
        short_level = replace_level_if_needed(app_config, df, symbol, 'down', can_replace_level, short_level)

        min_required_move_from_level = app_config['symbols_meta'][symbol]['min_required_move_from_level']  # used in config
        price = df['close'].iloc[-1]  # used in config
        atr_14 = df['atr_14'].iloc[-2]  # used in config

        logger.debug(f"in check_buy_sell_condition, levels: {levels}")
        evaluated_conditions_map = {}
        for side in ['long', 'short']:
            for condition in app_config['cases'][case][side]['conditions']:
                evaluated = eval(condition)
                logger.info(f"in check_buy_sell_condition, {symbol}, case: {case}, side: {side}, evaluated: {evaluated},  condition: {condition}, ")
                evaluated_conditions_map.setdefault(side, {}).setdefault('valuated_conditions',[]).append(evaluated)


        if all(evaluated_conditions_map.get('long', {}).get('valuated_conditions', [])):
            can_buy = True
        if all(evaluated_conditions_map.get('short', {}).get('valuated_conditions', [])):
            can_sell = True

        logger.info(f"check_buy_sell_condition(), {case}, {symbol}, {can_buy}, {can_sell}")
        logger.info(f"check_buy_sell_condition(), {case}, can_buy: {can_buy}, {symbol}")
        logger.info(f"check_buy_sell_condition(), {case}, can_sell: {can_sell}, {symbol}")

        # long_breakup_idxs = break_out_indices_by_level_set.get(long_level, set())
        # long_retest_idxs = retest_indices_by_level_set.get(long_level, set())
        long_breakup_idxs = get_break_out_indices_by_level_set(application_state, symbol, long_level)
        long_retest_idxs = get_retest_indices_by_level_set(application_state, symbol, long_level)

        # short_breakup_idxs = break_out_indices_by_level_set.get(short_level, set())
        # short_retest_idxs = retest_indices_by_level_set.get(short_level, set())

        short_breakup_idxs = get_break_out_indices_by_level_set(application_state, symbol, short_level)
        short_retest_idxs = get_retest_indices_by_level_set(application_state, symbol, short_level)

        result_long =  ",".join(f"{i + 1}:{val}" for i, val in enumerate(evaluated_conditions_map.get('long', {}).get('valuated_conditions', [])))
        result_short = ",".join(f"{i + 1}:{val}" for i, val in enumerate(evaluated_conditions_map.get('short', {}).get('valuated_conditions', [])))

        breakout_idx = application_state.get('breakouts', {}).get(symbol, [])
        retest_idx = ''

        # This is shown in the chart ..
        res_str = (f"res_{case}:<br>"
                   f"{result_long} .. {long_breakup_idxs}.{long_retest_idxs} <br>"
                   f"{result_short} .. {short_breakup_idxs}.{short_retest_idxs} <br>"
                   f"breakout: {breakout_idx}, retest: {retest_idx} <br>"
                   f"{df['date'].iloc[-1].strftime('%H:%M')}")
        res_str = res_str.replace('True', 'T')
        res_str = res_str.replace('False', 'F')

        res_str_log = res_str.replace('<br>', '\n')
        logger.info(f"\nres_str: {res_str_log}")
    except Exception as e:
        logger.error(f"@ in check_buy_sell_condition: {symbol} {case} error {e}")
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


def check_buy_and_sell_cases(app_config, application_state, symbol, market_data):
    mode = application_state.get('mode', 'live')
    buy_sell_case_results = []
    for case in app_config['cases']:
        if case in app_config[mode]['cases_to_run']:
            res = check_buy_sell_condition(app_config, application_state, case, symbol, market_data)
            if res is not None: # if precondition not met, we get None
                buy_sell_case_results.append(res)

    return buy_sell_case_results



def replace_level_if_needed(app_config, df, symbol, side, can_replace_level, level):
    # If two levels are close, we replace with next one ...

    if not can_replace_level:
        return level
    closeness_distance = eval(app_config['closeness_distance'])
    next_level = get_next_level(side, level)

    if side == 'up':
        if next_level > level and abs(next_level - level) < closeness_distance:
            logger.info(f"replace_level_if_needed, level is replaced,{symbol}, {side}, level: {level}, next_level: {next_level}, {df['date'].iloc[-1]}")
            return next_level
    else:
        if next_level < level and abs(next_level - level) < closeness_distance:
            logger.info(f"replace_level_if_needed, level is replaced, {symbol}, {side}, level: {level}, next_level: {next_level}, {df['date'].iloc[-1]}")
            return next_level
    return level


def get_next_level(side, levels, level):
    if side == 'up':
        next_level = levels.get('PDH', -1)
    else:
        next_level = levels.get('PDL', -1)

    return next_level



def breakout_in_last_x_candles_ver_2(symbol, app_config, application_state, df, side='up', idx_list=[-2], level=0):

    logger.debug(f"in breakout_in_last_x_candles, symbol: {symbol}, idx_list: {idx_list}, level:{level}")

    if level == 0:
        return False
    gap = app_config['symbols_meta'][symbol]['breakout_confirmation_distance']
    breakout_happened = False

    for idx in idx_list:
        row = df.iloc[idx]
        previous = df.iloc[idx-1]
        # --- Breakout detection ---
        if date_utils.get_hhmm_int(row['date']) < 930: # we dont want breaks before 930
            continue

        # --- breakout condition ---
        if side == 'up':
            cond_1 = (row["low"] < level and row["close"] > level + gap)    # The price above level + gap
            cond_2 = (previous["open"] < level and row["close"] > level + gap)  # The prev open is below level and current above the level.
            cond_3 = (previous["open"] < level and row["open"] > level and row["close"] > level)  # The prev open is below level and current open and close are above the level.

        else:
            cond_1 = (row["high"] > level and row["close"] < level - gap)
            cond_2 = (previous["open"] > level and row["close"] < level - gap)
            cond_3 = (previous["open"] > level and row["open"] < level and row["close"] < level)

        breakout = (cond_1 or cond_2 or cond_3)
        if not breakout:
            continue


        # --- candle body confirmation ---
        body = abs(row["close"] - row["open"])
        candle_range = row["high"] - row["low"]
        candle_is_not_week = (candle_range > 0 and body / candle_range > 0.5) # do not remove candle_rage > 0 will raise devided by zero exception

        if (cond_1 and candle_is_not_week) or cond_2 or cond_3: # for cond_1 we need body_confirmation, for cond_2 and cond_3 we do not need it

            logger.info(f"in breakout_in_last_x_candles, idx: {idx}, level: {level}, retest happened!! ")

            application_state['breakouts'][symbol].setdefault('', []).append({
                'side': side,
                'level': level,
                'idx': idx,
                'time': row['date'],
            })
            breakout_happened = True

    return breakout_happened


def get_break_out_indices_by_level_set(application_state, symbol, level):
    break_out_indices = set()
    breakouts = application_state['breakouts'].get(symbol, [])
    for b in breakouts:
        if b['level'] == level:
            break_out_indices.add(b['idx'])
    return break_out_indices
    
def get_retest_indices_by_level_set(application_state, symbol, level):
    retest_indices = set()
    retests = application_state['retests'].get(symbol, [])
    for r in retests:
        if r['level'] == level:
            retest_indices.add(r['idx'])
    return retest_indices



def price_retest(symbol, app_config, application_state, df, side='up', idx_list=[-2], level=0, both_sides=False):

    if level == 0:
        return False

    # tolerance_amount = app_config['symbols_meta'][symbol]['retest_tolerance_amount']
    # tolerance_amount = dynamic_tolerance.get('tolerance', 0)
    tolerance_amount = application_state.get('dynamic_tolerance', {}).get(symbol, {}).get('tolerance', 0)

    tolerance_amount = tolerance_amount * app_config['symbols_meta'][symbol].get('retest_tolerance_multiplier', 1)
    logger.debug(f"price_retest(), {symbol}, tolerance_amount: {tolerance_amount}")
    retest = False

    for idx in idx_list:
        row = df.iloc[idx]

        if date_utils.get_hhmm_int(row['date']) < 930: # we dont want breaks before 930
            continue


        # --- Retest detection ---
        if side == 'up':
            if level > row["low"] and level - row["low"] <= tolerance_amount and row["close"] > level:
                application_state['retests'][symbol].setdefault('', []).append({
                    'side': side,
                    'level': level,
                    'idx': idx,
                    'time': row['date'],
                })
                logger.info(f"price_retest(), symbol: {symbol}, level: {level}, date:{df.iloc[idx]['date']} ")
                retest = True
                diff = abs(row['low']-level)

            if both_sides and abs(level - row["low"]) <= tolerance_amount and row["close"] > level:   # close > level.  low is close to the level in both sides.
                application_state['retests'][symbol].setdefault('', []).append({
                    'side': side,
                    'level': level,
                    'idx': idx,
                    'time': row['date'],
                })
                retest = True
                diff = abs(row['low']-level)
        else:
            if row["high"] > level and row["high"] - level <= tolerance_amount and row["close"] < level:
                application_state['retests'][symbol].setdefault('', []).append({
                    'side': side,
                    'level': level,
                    'idx': idx,
                    'time': row['date'],
                })
                retest = True
                diff = abs(row['high'] - level)
            if both_sides and abs(level - row["high"]) <= tolerance_amount and row["close"] < level:   # close < level.  high is close to the level in both sides.
                application_state['retests'][symbol].setdefault('', []).append({
                    'side': side,
                    'level': level,
                    'idx': idx,
                    'time': row['date'],
                })
                retest = True
                diff = abs(row['high']-level)

    return retest

def is_retest_after_breakout(application_state, symbol, side='up', level=1):

    breakout_idxs = get_break_out_indices_by_level_set(application_state, symbol, level)
    retest_idxs = get_retest_indices_by_level_set(application_state, symbol, level)

    if retest_idxs == set() or breakout_idxs == set():
        return  False
    if max(retest_idxs) > min(breakout_idxs):
        retest_idx = max(retest_idxs)
        application_state.setdefault('retests_idx', {})['symbol'] = retest_idx
        valid_breakouts = [b for b in breakout_idxs if b < retest_idx]   # all the breakout idxs that are before retest_idx
        if valid_breakouts:
            breakout_idx = max(valid_breakouts)  # closest (largest) breakout before retest
            application_state.setdefault('breakouts_idx', {})['symbol'] = breakout_idx
        return True
    else:
        return False
