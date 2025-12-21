import logging
logger = logging.getLogger(__name__)


def check_buy_sell_condition(app_config, application_state, case, symbol):

    can_buy = False
    can_sell = False
    res_str = ''
    long_level = -1
    short_level = -1

    try:
        precondition = app_config['cases'][case]['precondition']
        precondition_eval = eval(precondition)
        if not precondition_eval:
            logger.warning(f"check_buy_sell_condition, precondition not met for case: {case}, symbol: {symbol}, precondition: {precondition}")
            return None
        levels = application_state['symbols'][symbol] # used in config

        can_replace_level = app_config['cases'][case]['can_replace_level']
        long_level = eval(app_config['cases'][case]['long']['level'])
        short_level = eval(app_config['cases'][case]['short']['level'])

        long_level = replace_level_if_needed(app_config, application_state,symbol, 'up', can_replace_level, long_level)
        short_level = replace_level_if_needed(app_config, application_state,symbol, 'down', can_replace_level, short_level)

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

        long_breakup_idxs = break_out_indices_by_level_set.get(long_level, set())
        long_retest_idxs = retest_indices_by_level_set.get(long_level, set())

        short_breakup_idxs = break_out_indices_by_level_set.get(short_level, set())
        short_retest_idxs = retest_indices_by_level_set.get(short_level, set())

        result_long =  ",".join(f"{i + 1}:{val}" for i, val in enumerate(evaluated_conditions_map.get('long', {}).get('valuated_conditions', [])))
        result_short = ",".join(f"{i + 1}:{val}" for i, val in enumerate(evaluated_conditions_map.get('short', {}).get('valuated_conditions', [])))

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


def check_buy_and_sell_cases(app_config, application_state):
    mode = application_state.get('mode', 'live')
    buy_sell_case_results = []
    for case in app_config['cases']:
        if case in app_config[mode]['cases_to_run']:
            res = check_buy_sell_condition(case)
            if res is not None: # if precondition not met, we get None
                buy_sell_case_results.append(res)

    return buy_sell_case_results



def replace_level_if_needed(app_config, application_state, symbol, side, can_replace_level, level):
    # If two levels are close, we replace with next one ...

    if not can_replace_level:
        return level
    closeness_distance = eval(app_config['closeness_distance'])
    levels = application_state['symbols'][symbol]  # used in config
    next_level = get_next_level(side, level)

    if side == 'up':
        if next_level > level and abs(next_level - level) < closeness_distance:
            logger.info(f"replace_level_if_needed, level is replaced,{symbol}, {side}, level: {level}, next_level: {next_level}, {df['date'].iloc[-1]}")
            price = get_offseted_price('up', df['high'].iloc[-1])
            add_to_signlas(symbol, 'LEVEL_REPLACED', price, df['date'].iloc[-1], f'level is replaced. from: {level}, to: {next_level}')
            return next_level
    else:
        if next_level < level and abs(next_level - level) < closeness_distance:
            logger.info(f"replace_level_if_needed, level is replaced, {symbol}, {side}, level: {level}, next_level: {next_level}, {df['date'].iloc[-1]}")
            price = get_offseted_price('up', df['high'].iloc[-1])
            add_to_signlas(symbol, 'LEVEL_REPLACED', price,  df['date'].iloc[-1], f'level is replaced. from: {level}, to: {next_level}')
            return next_level
    return level


def get_next_level(side, levels, level):
    if side == 'up':
        next_level = levels.get('PDH', -1)
    else:
        next_level = levels.get('PDL', -1)

    return next_level
