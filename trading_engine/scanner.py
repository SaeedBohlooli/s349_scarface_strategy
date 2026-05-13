import logging
import traceback

from trading_core.trading_ledger import TradingLedger

logger = logging.getLogger(__name__)
from trading_utils import ib_contract, ib_pricing_async
from trading_utils import date_utils
from trading_engine import chart_helper

def check_buy_sell_condition(ib, app_config, application_state, case, symbol, market_data):

    can_buy = False
    can_sell = False
    can_buy_cores = False
    can_sell_cores = False
    res_str = ''
    long_level = -1
    short_level = -1
    long_breakout_idx = 0
    long_retest_idx = 0
    short_breakout_idx = 0
    short_retest_idx = 0
    entry_breakout_idx = 0
    entry_retest_idx = 0
    try:
        df = market_data.dfs_map.get(symbol)
        if df is None:
            logger.warning(f"[check_buy_sell_condition], no market data for symbol: {symbol}")
            return None
        precondition = app_config['cases'][case]['precondition']
        precondition_eval = eval(precondition)
        if not precondition_eval:
            logger.warning(f"[check_buy_sell_condition], precondition not met for case: {case}, symbol: {symbol}, precondition: {precondition}")
            return None
        levels = application_state['levels'][symbol] # used in config

        can_replace_level = app_config['cases'][case]['can_replace_level']
        long_level = eval(app_config['cases'][case]['long']['level'])
        short_level = eval(app_config['cases'][case]['short']['level'])

        long_level = replace_level_if_needed(application_state, app_config, df, symbol, 'up', can_replace_level, long_level)
        short_level = replace_level_if_needed(application_state, app_config, df, symbol, 'down', can_replace_level, short_level)

        min_required_move_from_level = app_config['symbols_meta'][symbol]['min_required_move_from_level']  # used in config
        price = df['close'].iloc[-1]  # used in config
        atr_14 = df['atr_14'].iloc[-2]  # used in config
        skip_level_closeness_enabled = app_config.get("xui_symbol_controls", {}).get(symbol, {}).get("skip_level_closeness_enabled", False)  # used in config
        skip_pdhl_and_qqq_check_enabled = app_config.get("xui_symbol_controls", {}).get(symbol, {}).get("skip_pdhl_and_qqq_check_enabled", False)  # used in config

        logger.debug(f"[check_buy_sell_condition], levels: {levels}")
        evaluated_conditions_map = {}
        for side in ['long', 'short']:
            level_alias = app_config['cases'][case][side]['level_alias'] # used in config
            c_i = 0
            for condition in app_config['cases'][case][side]['cores']:
                c_i = c_i + 1
                logger.debug(f"[check_buy_sell_condition] {c_i}), {symbol}, case: {case}, side: {side}, condition: {condition} ")
                evaluated = eval(condition)
                logger.debug(f"[check_buy_sell_condition] {c_i}), {symbol}, case: {case}, side: {side}, evaluated: {evaluated},  condition: {condition} ")
                evaluated_conditions_map.setdefault(side, {}).setdefault('valuated_conditions',[]).append(evaluated)
                evaluated_conditions_map.setdefault(side, {}).setdefault('valuated_conditions_cores',[]).append(evaluated)
                
            
            for condition in app_config['cases'][case][side].get('extras', []):
                c_i = c_i + 1
                logger.debug(f"[check_buy_sell_condition] {c_i}), {symbol}, case: {case}, side: {side}, condition: {condition} ")
                evaluated = eval(condition)
                logger.debug(f"[check_buy_sell_condition] {c_i}), {symbol}, case: {case}, side: {side}, evaluated: {evaluated},  condition: {condition} ")
                evaluated_conditions_map.setdefault(side, {}).setdefault('valuated_conditions',[]).append(evaluated)
                evaluated_conditions_map.setdefault(side, {}).setdefault('valuated_conditions_extras',[]).append(evaluated)


        if all(evaluated_conditions_map.get('long', {}).get('valuated_conditions', [])):
            can_buy = True
        if all(evaluated_conditions_map.get('short', {}).get('valuated_conditions', [])):
            can_sell = True

        if all(evaluated_conditions_map.get('long', {}).get('valuated_conditions_cores', [])):
            can_buy_cores = True
        if all(evaluated_conditions_map.get('short', {}).get('valuated_conditions_cores', [])):
            can_sell_cores = True

        logger.info(f"[check_buy_sell_condition] {case}, {symbol}, {can_buy}, {can_sell}")
        logger.info(f"[check_buy_sell_condition] {case}, {symbol}, can_buy: {can_buy}, ")
        logger.info(f"[check_buy_sell_condition] {case}, {symbol}, can_sell: {can_sell}")

        long_breakout_idxs = get_break_out_indices_by_level_set(application_state, symbol, long_level)
        long_retest_idxs = get_retest_indices_by_level_set(application_state, symbol, long_level)


        short_breakout_idxs = get_break_out_indices_by_level_set(application_state, symbol, short_level)
        short_retest_idxs = get_retest_indices_by_level_set(application_state, symbol, short_level)

        result_long =  ",".join(f"{i + 1}:{val}" for i, val in enumerate(evaluated_conditions_map.get('long', {}).get('valuated_conditions', [])))
        result_short = ",".join(f"{i + 1}:{val}" for i, val in enumerate(evaluated_conditions_map.get('short', {}).get('valuated_conditions', [])))

        long_breakout_idx = get_breakout_idx(application_state, symbol, long_level)
        short_breakout_idx = get_breakout_idx(application_state, symbol, short_level)

        long_retest_idx = get_retest_idx(application_state, symbol, long_level)
        short_retest_idx = get_retest_idx(application_state, symbol, short_level)

        logger.info(f"[check_buy_sell_condition] breakout_idxs, {case}, {symbol}, can_buy: {long_breakout_idxs}, {long_retest_idxs}")
        logger.info(f"[check_buy_sell_condition] breakout_idxs, {case}, {symbol}, can_sell: {short_breakout_idxs}, {short_retest_idxs}")

        logger.info(f"[check_buy_sell_condition] idx, {case}, {symbol}, can_buy: {long_breakout_idx}, {long_retest_idx}")
        logger.info(f"[check_buy_sell_condition] idx, {case}, {symbol}, can_sell: {short_breakout_idx}, {short_retest_idx}")

        # This is shown in the chart ..
        res_str = (f"res_{case}:<br>"
                   f"{result_long} .. {long_breakout_idxs}.{long_retest_idxs} <br>"
                   f"{result_short} .. {short_breakout_idxs}.{short_retest_idxs} <br>"
                   f"long_breakout: {long_breakout_idx}, long_retest: {long_retest_idx} <br>"
                   f"short_breakout: {short_breakout_idx}, short_retest: {short_retest_idx} <br>"
                   f"{df['date'].iloc[-1].strftime('%H:%M')}")
        res_str = res_str.replace('True', 'T')
        res_str = res_str.replace('False', 'F')

        res_str_log = res_str.replace('<br>', '\n')
        logger.info(f"[buy_sell_case_results_details] res_str:\n{res_str_log}")

        application_state.setdefault('buy_sell_case_results_details', {}).setdefault(symbol, {})[case] = {
            'can_buy': can_buy,
            'can_sell': can_sell,
            'res_str': res_str,
        }
        if can_buy:
            entry_breakout_idx = long_breakout_idx
            entry_retest_idx = long_retest_idx
        elif can_sell:
            entry_breakout_idx = short_breakout_idx
            entry_retest_idx = short_retest_idx

    except Exception as e:
        logger.error(f"[check_buy_sell_condition] @@ {symbol} {case} error {e}")
        logger.error(traceback.format_exc())
        res_str = f'res_{case}'
    details_map = {
        'can_buy': can_buy,
        'can_sell': can_sell,
        'can_buy_cores': can_buy_cores,
        'can_sell_cores': can_sell_cores,
        'res_str': res_str,
        'long_level': long_level,
        'short_level': short_level,
        'long_breakout_idx': long_breakout_idx,
        'long_retest_idx': long_retest_idx,
        'short_breakout_idx': short_breakout_idx,
        'short_retest_idx': short_retest_idx,
        'entry_breakout_idx': entry_breakout_idx,
        'entry_retest_idx': entry_retest_idx

    }
    return case, can_buy, can_sell, details_map


def check_buy_and_sell_cases(ib, app_config, application_state, symbol, market_data):
    mode = application_state.get('mode', 'live')
    buy_sell_case_results = []
    for case in app_config['cases']:
        if case in app_config['live_cases']:
            res = check_buy_sell_condition(ib, app_config, application_state, case, symbol, market_data)
            if res is not None: # if precondition not met, we get None
                buy_sell_case_results.append(res)

    return buy_sell_case_results



def replace_level_if_needed(application_state, app_config, df, symbol, side, can_replace_level, level):
    # If two levels are close, we replace with next one ...

    if not can_replace_level:
        return level
    closeness_distance = eval(app_config['closeness_distance'])
    levels = application_state.get('levels', {}).get(symbol, {})
    next_level = get_next_level(side, level, levels)

    if side == 'up':
        if next_level > level and abs(next_level - level) < closeness_distance:
            logger.info(f"[replace_level_if_needed] level is replaced,{symbol}, {side}, level: {level}, next_level: {next_level}, {df['date'].iloc[-1]}")
            price = chart_helper.get_offseted_price(app_config, application_state,symbol,side='up', price=df['high'].iloc[-1])
            TradingLedger.add_to_list("signals", (symbol, 'LEVEL_REPLACED', price, df['date'].iloc[-1], f'level is replaced. from: {level}, to: {next_level}') )
            return next_level
    else:
        if next_level < level and abs(next_level - level) < closeness_distance:
            logger.info(f"[replace_level_if_needed] level is replaced, {symbol}, {side}, level: {level}, next_level: {next_level}, {df['date'].iloc[-1]}")
            price = chart_helper.get_offseted_price(app_config,application_state, symbol,'up', df['high'].iloc[-1])
            TradingLedger.add_to_list("signals", (symbol, 'LEVEL_REPLACED', price, df['date'].iloc[-1], f'level is replaced. from: {level}, to: {next_level}') )
            return next_level
    return level


def get_next_level(side, level, levels):

    if side == 'up':
        next_level = levels.get('PDH', -1)
    else:
        next_level = levels.get('PDL', -1)

    return next_level



def breakout_in_last_x_candles_ver_2(app_config, application_state, case, symbol, df, side='up', idx_list=[-2], level=0, level_alias=''):

    logger.debug(f"[in breakout_in_last_x_candles], symbol: {symbol}, idx_list: {idx_list}, level:{level}")

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
            cond_1 = (row["low"] <= level and row["close"] > level + gap)    # The price above level + gap
            cond_2 = (previous["open"] < level and row["close"] > level + gap)  # The prev open is below level and current above the level.
            cond_3 = (previous["open"] < level and row["open"] > level and row["close"] > level)  # The prev open is below level and current open and close are above the level.

        else:
            cond_1 = (row["high"] >= level and row["close"] < level - gap)
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

            logger.info(f"[in breakout_in_last_x_candles], idx: {idx}, level: {level}, retest happened!! ")

            application_state['breakouts'].setdefault(symbol, []).append({
                'side': side,
                'level': level,
                'level_alias': level_alias,
                'idx': idx,
                'time': str(row['date']),
            })
            breakout_happened = True

            offseted_price = chart_helper.get_offseted_price(app_config, application_state, symbol, side='up',price=df['high'].iloc[idx])
            case_color = get_case_color(app_config, case)
            TradingLedger.add_to_list("signals", (symbol, 'BREAKOUT', offseted_price, df['date'].iloc[idx], f"BREAKOUT {level_alias} ... {df['date'].iloc[idx]}... ", case_color) )

    return breakout_happened

def breakout_in_last_x_candles_ver_4(app_config, application_state, case, symbol, df, side='up', idx_list=[-2], level=0, level_alias=''):
    ###
    # The difference with ver_2 is that if -i is breakout candle, we do not need to check the body confirmation for -i-1 candle.
    # because -i-1 candle is before breakout and it can be weak as we do not care about it. but in ver_2 we check body
    # confirmation for -i candle which is breakout candle and it can be weak as well.
    # so in ver_3 we check body confirmation for -i candle only if cond_1 is true. if cond_2 or cond_3 is true, we do not check body confirmation for -i candle.

    logger.debug(f"[in breakout_in_last_x_candles], symbol: {symbol}, idx_list: {idx_list}, level:{level}")

    if level == 0:
        return False
    gap = app_config['symbols_meta'][symbol]['breakout_confirmation_distance']
    breakout_happened = False
    breakout_idxs = []

    for idx in idx_list:
        row = df.iloc[idx]
        previous = df.iloc[idx-1]
        next = df.iloc[idx+1]   # as we always we check -2, so this is safe. and -1 with be the forming candle
        # --- Breakout detection ---
        if date_utils.get_hhmm_int(row['date']) < 930: # we dont want breaks before 930
            continue

        # --- breakout condition ---
        if side == 'up':
            cond_1 = (row["open"] <= level and row["close"] > level + gap)    # The price above level + gap
            cond_2 = (previous["open"] < level and row["close"] > level + gap)  # The prev open is below level and current above the level.
            cond_3 = (previous["open"] < level and row["open"] > level and row["close"] > level)  # The prev open is below level and current open and close are above the level.
            cond_4 = (row["low"] <= level and row["close"] > level and next["open"] > level and next["close"] > level and next["close"]  > next["open"] )  # The current open is below level and next open and close both above the level

        else:
            cond_1 = (row["open"] >= level and row["close"] < level - gap)
            cond_2 = (previous["open"] > level and row["close"] < level - gap)
            cond_3 = (previous["open"] > level and row["open"] < level and row["close"] < level)
            cond_4 = (row["high"]  >= level and row["clode"] < level and next["open"] < level and next["close"] < level and next["close"] < next["open"])

        breakout = (cond_1 or cond_2 or cond_3 or cond_4)
        if not breakout:
            continue


        # --- candle body confirmation ---
        body = abs(row["close"] - row["open"])
        candle_range = row["high"] - row["low"]
        candle_is_not_week = (candle_range > 0 and body / candle_range > 0.5) # do not remove candle_rage > 0 will raise devided by zero exception

        if (cond_1 and candle_is_not_week) or cond_2 or cond_3 or cond_4: # for cond_1 we need body_confirmation, for others we do not need it

            logger.info(f"[breakout_in_last_x_candles_ver_4], idx: {idx}, level: {level}")

            application_state['breakouts'].setdefault(symbol, []).append({
                'side': side,
                'level': level,
                'level_alias': level_alias,
                'idx': idx,
                'time': str(row['date']),
            })
            breakout_idxs.append(idx)
            breakout_happened = True

            offseted_price = chart_helper.get_offseted_price(app_config, application_state, symbol, side='up',price=df['high'].iloc[idx])
            case_color = get_case_color(app_config, case)
            TradingLedger.add_to_list("signals", (symbol, 'BREAKOUT', offseted_price, df['date'].iloc[idx], f"BREAKOUT {level_alias} ... {df['date'].iloc[idx]}... ", case_color) )

    for breakout_idx in breakout_idxs:
        if not breakout_idx - 1 in breakout_idxs:
            # if the previous candle is not breakout candle, we check to markk it as breakout as well
                row = df.iloc[breakout_idx-1]
                if side == 'up':
                    body = abs(row["close"] - row["open"])
                    candle_range = row["high"] - row["low"]
                    candle_is_not_week = (candle_range > 0 and body / candle_range > 0.5) # do not remove candle_rage > 0 will raise devided by zero exception
                    if candle_is_not_week and row["open"] <= level and row["close"] > level:    # The price above level
                        application_state['breakouts'].setdefault(symbol, []).append({
                            'side': side,
                            'level': level,
                            'level_alias': level_alias,
                            'idx': breakout_idx-1,
                            'time': str(row['date']),
                        })
                        offseted_price = chart_helper.get_offseted_price(app_config, application_state, symbol, side='up',price=df['high'].iloc[breakout_idx-1])
                        case_color = get_case_color(app_config, case)
                        TradingLedger.add_to_list("signals", (symbol, 'BREAKOUT', offseted_price, row['date'], f"BREAKOUT {level_alias} ... {row['date']}... ", case_color) )
                else:
                    body = abs(row["close"] - row["open"])
                    candle_range = row["high"] - row["low"]
                    candle_is_not_week = (candle_range > 0 and body / candle_range > 0.5) # do not remove candle_rage > 0 will raise devided by zero exception
                    if candle_is_not_week and row["open"] >= level and row["close"] < level:    # The price below level
                        application_state['breakouts'].setdefault(symbol, []).append({
                            'side': side,
                            'level': level,
                            'level_alias': level_alias,
                            'idx': breakout_idx-1,
                            'time': str(row['date']),
                        })
                        offseted_price = chart_helper.get_offseted_price(app_config, application_state, symbol, side='up',price=df['high'].iloc[breakout_idx-1])
                        case_color = get_case_color(app_config, case)
                        TradingLedger.add_to_list("signals", (symbol, 'BREAKOUT', offseted_price, row['date'], f"BREAKOUT {level_alias} ... {row['date']}... ", case_color) )



    return breakout_happened


def breakout_in_last_x_candles_ver_3(app_config, application_state, case, symbol, df, side='up', idx_list=[-2], level=0, level_alias=''):
    ###
    # The difference with ver_2 is that if -i is breakout candle, we do not need to check the body confirmation for -i-1 candle.
    # because -i-1 candle is before breakout and it can be weak as we do not care about it. but in ver_2 we check body
    # confirmation for -i candle which is breakout candle and it can be weak as well.
    # so in ver_3 we check body confirmation for -i candle only if cond_1 is true. if cond_2 or cond_3 is true, we do not check body confirmation for -i candle.

    logger.debug(f"[breakout_in_last_x_candles], symbol: {symbol}, idx_list: {idx_list}, level:{level}")

    if level == 0:
        return False
    gap = app_config['symbols_meta'][symbol]['breakout_confirmation_distance']
    breakout_happened = False
    breakout_idxs = []

    for idx in idx_list:
        row = df.iloc[idx]
        previous = df.iloc[idx-1]
        # --- Breakout detection ---
        if date_utils.get_hhmm_int(row['date']) < 930: # we dont want breaks before 930
            continue

        # --- breakout condition ---
        if side == 'up':
            cond_1 = (row["low"] <= level and row["close"] > level + gap)    # The price above level + gap
            cond_2 = (previous["open"] < level and row["close"] > level + gap)  # The prev open is below level and current above the level.
            cond_3 = (previous["open"] < level and row["open"] > level and row["close"] > level)  # The prev open is below level and current open and close are above the level.

        else:
            cond_1 = (row["high"] >= level and row["close"] < level - gap)
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

            logger.info(f"[breakout_in_last_x_candles], idx: {idx}, level: {level}, retest happened!! ")

            application_state['breakouts'].setdefault(symbol, []).append({
                'side': side,
                'level': level,
                'level_alias': level_alias,
                'idx': idx,
                'time': str(row['date']),
            })
            breakout_idxs.append(idx)
            breakout_happened = True

            offseted_price = chart_helper.get_offseted_price(app_config, application_state, symbol, side='up',price=df['high'].iloc[idx])
            case_color = get_case_color(app_config, case)
            TradingLedger.add_to_list("signals", (symbol, 'BREAKOUT', offseted_price, df['date'].iloc[idx], f"BREAKOUT {level_alias} ... {df['date'].iloc[idx]}... ", case_color) )
    for breakout_idx in breakout_idxs:
        if not breakout_idx - 1 in breakout_idxs:
            # if the previous candle is not breakout candle, we check to markk it as breakout as well
                row = df.iloc[breakout_idx-1]
                if side == 'up':
                    body = abs(row["close"] - row["open"])
                    candle_range = row["high"] - row["low"]
                    candle_is_not_week = (candle_range > 0 and body / candle_range > 0.5) # do not remove candle_rage > 0 will raise devided by zero exception
                    if candle_is_not_week and row["open"] <= level and row["close"] > level:    # The price above level
                        application_state['breakouts'].setdefault(symbol, []).append({
                            'side': side,
                            'level': level,
                            'level_alias': level_alias,
                            'idx': breakout_idx-1,
                            'time': str(row['date']),
                        })
                        offseted_price = chart_helper.get_offseted_price(app_config, application_state, symbol, side='up',price=df['high'].iloc[breakout_idx-1])
                        case_color = get_case_color(app_config, case)
                        TradingLedger.add_to_list("signals", (symbol, 'BREAKOUT', offseted_price, row['date'], f"BREAKOUT {level_alias} ... {row['date']}... ", case_color) )
                else:
                    body = abs(row["close"] - row["open"])
                    candle_range = row["high"] - row["low"]
                    candle_is_not_week = (candle_range > 0 and body / candle_range > 0.5) # do not remove candle_rage > 0 will raise devided by zero exception
                    if candle_is_not_week and row["open"] >= level and row["close"] < level:    # The price below level
                        application_state['breakouts'].setdefault(symbol, []).append({
                            'side': side,
                            'level': level,
                            'level_alias': level_alias,
                            'idx': breakout_idx-1,
                            'time': str(row['date']),
                        })
                        offseted_price = chart_helper.get_offseted_price(app_config, application_state, symbol, side='up',price=df['high'].iloc[breakout_idx-1])
                        case_color = get_case_color(app_config, case)
                        TradingLedger.add_to_list("signals", (symbol, 'BREAKOUT', offseted_price, row['date'], f"BREAKOUT {level_alias} ... {row['date']}... ", case_color) )



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



def price_retest(app_config, application_state, case, symbol, df, side='up', idx_list=[-2], level=0, both_sides=False, level_alias=''):

    if level == 0:
        return False

    # tolerance_amount = app_config['symbols_meta'][symbol]['retest_tolerance_amount']
    # tolerance_amount = dynamic_tolerance.get('tolerance', 0)
    tolerance_amount = application_state.get('dynamic_tolerances', {}).get(symbol, {}).get('tolerance', 0)

    tolerance_amount = tolerance_amount * app_config['symbols_meta'][symbol].get('retest_tolerance_multiplier', 1)
    logger.debug(f"[price_retest] {symbol}, tolerance_amount: {tolerance_amount}")
    retest = False
    case_color = get_case_color(app_config,case)

    for idx in idx_list:
        row = df.iloc[idx]

        if date_utils.get_hhmm_int(row['date']) < 930: # we dont want breaks before 930
            continue


        # --- Retest detection ---
        if side == 'up':
            if level > row["low"] and level - row["low"] <= tolerance_amount and row["close"] > level:
                d = {
                    'side': side,
                    'level': level,
                    'level_alias': level_alias,
                    'idx': idx,
                    'time': str(row['date']),
                }
                application_state['retests'].setdefault(symbol, []).append(d)

                offseted_price = chart_helper.get_offseted_price(app_config, application_state, symbol, side='up', price=df['high'].iloc[idx])
                TradingLedger.add_to_list("signals", (symbol, 'RETEST', offseted_price, df['date'].iloc[idx], f"RETEST  {level_alias} ... {df['date'].iloc[idx]}", case_color) )

                logger.info(f"[price_retest] symbol: {symbol}, level: {level}, date:{df.iloc[idx]['date']} ")
                retest = True
                diff = abs(row['low']-level)

            elif both_sides and abs(level - row["low"]) <= tolerance_amount and row["close"] > level:   # close > level.  low is close to the level in both sides.
                d = {
                    'side': side,
                    'level': level,
                    'level_alias': level_alias,
                    'idx': idx,
                    'time': str(row['date']),
                }
                application_state['retests'].setdefault(symbol, []).append(d)

                offseted_price = chart_helper.get_offseted_price(app_config, application_state, symbol, side='up', price=df['high'].iloc[idx])
                TradingLedger.add_to_list("signals", (symbol, 'RETEST', offseted_price, df['date'].iloc[idx], f"RETEST  {level_alias} ... {df['date'].iloc[idx]}", case_color) )

                retest = True
                diff = abs(row['low']-level)
        else:
            if row["high"] > level and row["high"] - level <= tolerance_amount and row["close"] < level:
                d = {
                    'side': side,
                    'level': level,
                    'level_alias': level_alias,
                    'idx': idx,
                    'time': str(row['date']),
                }
                application_state['retests'].setdefault(symbol, []).append(d)

                offseted_price = chart_helper.get_offseted_price(app_config, application_state, symbol, side='up', price=df['high'].iloc[idx])
                TradingLedger.add_to_list("signals", (symbol, 'RETEST', offseted_price, df['date'].iloc[idx], f"RETEST  {level_alias} ... {df['date'].iloc[idx]}", case_color) )

                retest = True
                diff = abs(row['high'] - level)
            elif both_sides and abs(level - row["high"]) <= tolerance_amount and row["close"] < level:   # close < level.  high is close to the level in both sides.
                d = {
                    'side': side,
                    'level': level,
                    'level_alias': level_alias,
                    'idx': idx,
                    'time': str(row['date']),
                }
                application_state['retests'].setdefault(symbol, []).append(d)

                offseted_price = chart_helper.get_offseted_price(app_config, application_state, symbol, side='up', price=df['high'].iloc[idx])
                TradingLedger.add_to_list("signals", (symbol, 'RETEST', offseted_price, df['date'].iloc[idx], f"RETEST  {level_alias} ... {df['date'].iloc[idx]}" , case_color) )

                retest = True
                diff = abs(row['high']-level)

    return retest

def is_retest_after_breakout(application_state, symbol, side='up', level=1, level_alias=''):

    breakout_idxs = get_break_out_indices_by_level_set(application_state, symbol, level)
    retest_idxs = get_retest_indices_by_level_set(application_state, symbol, level)

    if retest_idxs == set() or breakout_idxs == set():
        return False
    if max(retest_idxs) > min(breakout_idxs):
        retest_idx = max(retest_idxs)
        application_state.setdefault('retest_idx', {}).setdefault(symbol, []).append({'retest_idx': retest_idx, 'level': level, 'level_alias': level_alias})
        valid_breakouts = [b for b in breakout_idxs if b < retest_idx]   # all the breakout idxs that are before retest_idx
        if valid_breakouts:
            breakout_idx = max(valid_breakouts)  # closest (largest) breakout before retest
            application_state.setdefault('breakout_idx', {}).setdefault(symbol, []).append({'breakout_idx' : breakout_idx, 'level': level, 'level_alias': level_alias })
        return True
    else:
        return False

    return False


def all_levels_in(application_state, symbol):
    levels = application_state['levels'].get(symbol, {})
    required_levels = ['PDH', 'PDL', 'PMH', 'PML', '5MH', '5ML']
    for rl in required_levels:
        if rl not in levels:
            return False
    return True





# def get_breakout_idx(application_state, symbol, level):
#     return application_state.get('breakouts_idx', {}).get('symbol', {}).get(symbol, None)
#
# def get_retest_idx(application_state, case, symbol):
#     return application_state.get('retests_idx', {}).get('case', {}).get(symbol, None)

def get_breakout_idx(application_state, symbol, level):
   #  application_state.setdefault('breakout_idx', {})[symbol] = {'breakout_idx' : breakout_idx, 'level': level, 'level_alias': level_alias }
    for entry in application_state.get('breakout_idx', {}).get(symbol, []):
        if entry['level'] == level:
            return entry['breakout_idx']
    return None

def get_retest_idx(application_state, symbol, level):
    for entry in application_state.get('retest_idx', {}).get(symbol, []):
        if entry['level'] == level:
            return entry['retest_idx']
    return None


def check_entry_vs_retest(application_state, case, symbol, df, side='up', level=1, retest_ohlc=''):

    retest_idx = get_retest_idx(application_state, symbol, level)
    breakout_idx = get_breakout_idx(application_state, symbol, level)

    if retest_idx is None or breakout_idx is None:
        return False

    if retest_idx == 0 or breakout_idx == 0:
        return False

    if side == 'up':
        ohlc_field = 'high' if retest_ohlc == '' else retest_ohlc
        if df['high'].iloc[-1] > df[ohlc_field].iloc[retest_idx]:  # clode > retest high
            return True
        else:
            return False
    else:
        ohlc_field = 'low' if retest_ohlc == '' else retest_ohlc
        if df['low'].iloc[-1] < df[ohlc_field].iloc[retest_idx]:
            return True
        else:
            return False
    return False



def no_failure_after_breakout(application_state, case, symbol, df, side='up', level=0, ohlc_field='open'):
    # we want make sure all closes after breakout are above the level.
    # for up, use 'open'
    # for down use 'close'

    breakout_idx = get_breakout_idx(application_state, symbol, level)

    if breakout_idx is None or breakout_idx == 0:
        return False

    i = -1 # the last candle
    j = breakout_idx # This is index for breakout...

    if j == i:
        return  False

    start, end = sorted([i, j])  # in case you mix order
    # say start -5 end -3.  this get -5, -4, -3,  it meanns both -5 and -3 is included too.
    if side == 'up':
        if (df.iloc[start:][ohlc_field] >= level).all(): # all highs are above level
            return True
    else:
        if (df.iloc[start:][ohlc_field] <= level).all(): # all opens are less then elvel
            return True

    return False


def check_price_vs_level(app_config, symbol, side='up', price=0, level=0):

    min_required_move_from_level = app_config['symbols_meta'][symbol]['min_required_move_from_level']

    if side == 'up':
        return price + min_required_move_from_level > level
    else:
        return price < level - min_required_move_from_level


def is_price_close_to_next_levels_ver_2(app_config, application_state, symbol, df, side='up', price= 0, current_level=1, next_levels=['PDH']):  # used in the config

    breakout_idx = get_breakout_idx(application_state, symbol, current_level)

    if breakout_idx == 0 or breakout_idx is None:
        return False
    if next_levels is None:
        return False

    levels_map = application_state['levels'].get(symbol, {})
    closeness_distance = eval(app_config['closeness_distance'])

    clipped_df = df[breakout_idx:]
    highest_high = clipped_df['high'].max()
    lowest_low = clipped_df['low'].min()
    logger.info(f"[is_price_close_to_next_levels_ver_2] {symbol}, price: side: {side}, {price}, current_level: {current_level}, next_levels:{next_levels}, breakout_idx: {breakout_idx} ,date: {df['date'].iloc[-1]}")

    for key in next_levels:
        next_level = levels_map.get(key, None)
        if next_level is None:
            continue  # skip missing levels

        distance = abs(price - next_level)
        is_close = distance < closeness_distance

        if side == "up":
            # TODO THe first two can merged ..
            # next_level is above the current level, price is below next level but very close
            if next_level > current_level and price > current_level and price < next_level and is_close:
                # add_to_signlas(symbol, 'PRICE_CLODE_TO_LEVEL', price, df['date'].iloc[-1], f'up-1 {price}, to: {next_level} <br> {date_utils.get_hhm_mm_of_last_record(df)}', color='red')
                TradingLedger.add_to_list("signals", (symbol, 'PRICE_CLODE_TO_LEVEL', price, df['date'].iloc[-1], f'up-1 {price}, to: {next_level} <br> {date_utils.get_hhm_mm_of_last_record(df)}' , 'red') )
                return True

            # next_level is above the current level, price is above next level
            if next_level > current_level and price > current_level and price > next_level: # This is for once the price passes the next level as well.
                # add_to_signlas(symbol, 'PRICE_CLODE_TO_LEVEL', price, df['date'].iloc[-1], f'up-2. price: {price}, to: {next_level} <br> {date_utils.get_hhm_mm_of_last_record(df)}', color='red')
                TradingLedger.add_to_list("signals", (symbol, 'PRICE_CLODE_TO_LEVEL', price, df['date'].iloc[-1], f'up-2. price: {price}, to: {next_level} <br> {date_utils.get_hhm_mm_of_last_record(df)}', 'red') )
                return True

            # next_level is above the current level AND price is above leve AND highest_high after breakout canddle is close to the next level ..
            if next_level > current_level and price > current_level and abs(highest_high - next_level) < closeness_distance:
                # add_to_signlas(symbol, 'PRICE_CLODE_TO_LEVEL', price, df['date'].iloc[-1], f'up-3. price: {price}, to: {next_level} <br> {date_utils.get_hhm_mm_of_last_record(df)}', color='red')
                TradingLedger.add_to_list("signals", (symbol, 'PRICE_CLODE_TO_LEVEL', price, df['date'].iloc[-1], f'up-3. price: {price}, to: {next_level} <br> {date_utils.get_hhm_mm_of_last_record(df)}', 'red') )
                return True

            # next_level > current level AND price > c level AND highest high >  next level
            if next_level > current_level and price > current_level and highest_high > next_level:
                # add_to_signlas(symbol, 'PRICE_CLODE_TO_LEVEL', price, df['date'].iloc[-1], f'up-4. price: {price}, to: {next_level} <br> {date_utils.get_hhm_mm_of_last_record(df)}', color='red')
                TradingLedger.add_to_list("signals", (symbol, 'PRICE_CLODE_TO_LEVEL', price, df['date'].iloc[-1], f'up-4. price: {price}, to: {next_level} <br> {date_utils.get_hhm_mm_of_last_record(df)}', 'red') )
                return True

        else:
            # next l < c level AND price < c level AND price > next l ...
            if next_level < current_level and price < current_level and price > next_level and is_close:
                # add_to_signlas(symbol, 'PRICE_CLODE_TO_LEVEL', price, df['date'].iloc[-1], f'down-1. price: {price}, to: {next_level} <br> {date_utils.get_hhm_mm_of_last_record(df)}', color='red')
                TradingLedger.add_to_list("signals", (symbol, 'PRICE_CLODE_TO_LEVEL', price, df['date'].iloc[-1], f'down-1. price: {price}, to: {next_level} <br> {date_utils.get_hhm_mm_of_last_record(df)}', 'red') )
                return True


            if next_level < current_level and price < current_level and price < next_level:  # see PLTR Oct 09-
                # add_to_signlas(symbol, 'PRICE_CLODE_TO_LEVEL', price, df['date'].iloc[-1], f'down-2. price: {price}, to: {next_level} <br> {date_utils.get_hhm_mm_of_last_record(df)}', color='red')
                TradingLedger.add_to_list("signals", (symbol, 'PRICE_CLODE_TO_LEVEL', price, df['date'].iloc[-1], f'down-2. price: {price}, to: {next_level} <br> {date_utils.get_hhm_mm_of_last_record(df)}', 'red') )
                return True

            # next_level < current level AND price is below level AND lowest low after breakout canddle is close to the next level ..
            if next_level < current_level and price < current_level and abs(lowest_low - next_level) < closeness_distance:
                # add_to_signlas(symbol, 'PRICE_CLODE_TO_LEVEL', price, df['date'].iloc[-1], f'down-3. price: {price}, to: {next_level} <br> {date_utils.get_hhm_mm_of_last_record(df)}', color='red')
                TradingLedger.add_to_list("signals", (symbol, 'PRICE_CLODE_TO_LEVEL', price, df['date'].iloc[-1], f'down-3. price: {price}, to: {next_level} <br> {date_utils.get_hhm_mm_of_last_record(df)}', 'red') )
                return True

            # next_level < current level AND price < c level AND lowest low  <  next level
            if next_level < current_level and price < current_level and lowest_low < next_level:
                # add_to_signlas(symbol, 'PRICE_CLODE_TO_LEVEL', price, df['date'].iloc[-1], f'down-4. price: {price}, to: {next_level} <br> {date_utils.get_hhm_mm_of_last_record(df)}', color='red')
                TradingLedger.add_to_list("signals", (symbol, 'PRICE_CLODE_TO_LEVEL', price, df['date'].iloc[-1], f'down-4. price: {price}, to: {next_level} <br> {date_utils.get_hhm_mm_of_last_record(df)}', 'red') )
                return True


    return False


def get_last_record_hh_mm(df):
    return date_utils.get_last_record_hhmm(df)


def get_mode(application_state):
    return application_state.get('mode', 'live')

def get_current_price(ib, application_state, symbol):
    return application_state.get('latest_prices', {}).get(symbol, None)


def get_case_color(app_config, case):
    return app_config.get('cases', {}).get(case, {}).get('color', 'black')