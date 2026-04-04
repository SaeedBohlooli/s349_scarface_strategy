import logging
logger = logging.getLogger(__name__)
from trading_utils import date_utils
from trading_engine import position_helper

def calculate_number_of_option_contracts(app_config, application_state, symbol, strike, ask, user_defined_quantity):

    memo = ''
    available_capital = calcualte_availale_capital(app_config, application_state)

    capital_per_trade_percentage = app_config['live']['capital_per_trade_percentage']

    # 4000 * 0.2 = 800.00  if the ask = 1,  quantity:  8  =  800/( 100  contract * 1 ask)
    #  num_of_contracts: 4
    logger.info(f"calculate_number_of_contracts(), {symbol}, available_capital: {available_capital}, capital_per_trade_percentage: {capital_per_trade_percentage}")

    max_exposure_per_trade = int(app_config['live'].get('max_exposure_per_trade', 800))
    min_position_size = int(app_config['live'].get('min_position_size', 6))
    min_contract_entry_price = app_config['live'].get('min_contract_entry_price', 0.5)

    # capital_per_trade = min(available_capital * capital_per_trade_percentage, max_exposure_per_trade)  # TODO put in a function
    capital_per_trade = max_exposure_per_trade


    if user_defined_quantity == 0: # we calcualte it ...
        num_of_contracts = round(capital_per_trade / (ask * 100))

        if ask < min_contract_entry_price:
            logger.warning(f"@@@@ ask price {ask} is below the minimum contract entry price {min_contract_entry_price} ...")
            num_of_contracts = 0

        if num_of_contracts < min_position_size:
            logger.warning(f"@@@@ we don't have enough capital ...{num_of_contracts} contracts is below the minimum position size {min_position_size} ...")
            num_of_contracts = 0
    else:
        num_of_contracts = user_defined_quantity
        memo += 'case_manual'

    logger.info(f"capital_per_trade: {capital_per_trade}, ask: {ask} strike: {strike}")
    logger.info(f"symbol: {symbol}, num_of_contracts: {num_of_contracts}")
    if num_of_contracts == 0:
        logger.warning(f"@@@@ we don't have enough capital ...")
    capital_used = num_of_contracts * 100 * ask
    capital_remaining_after_order = available_capital - capital_used
    open_trades_count_at_entry = position_helper.calculate_number_of_open_positions(application_state)
    # update ...
    application_state.get('risk')['available_capital'] = capital_remaining_after_order

    data = {
            'timestamp': str(date_utils.time_now()),
            'trade_date' : application_state.get('trading_date'),
            'symbol': symbol,
            'unique_run_number': application_state.get('unique_run_number'),
            'starting_capital': available_capital,
            'capital_used': capital_used,
            'capital_remaining_after_order': capital_remaining_after_order,
            'allowed_capital_per_trade': capital_per_trade,
            'strike': strike,
            'ask': ask,
            'num_of_contracts': num_of_contracts,
            'daily_loss_so_far': 0,
            'daily_win_so_far': 0,
            'open_trades_count_at_entry': open_trades_count_at_entry,
            'memo': memo
            }
    return num_of_contracts, data

def calculate_number_of_future_contracts(app_config, application_state, symbol):

    available_capital = calcualte_availale_capital()

    capital_per_trade_percentage = app_config['live']['capital_per_trade_percentage']

    logger.info(f"calculate_number_of_future_contracts(), {symbol}, available_capital: {available_capital}, capital_per_trade_percentage: {capital_per_trade_percentage} ")

    capital_per_trade = max(available_capital * capital_per_trade_percentage, 800)  # TODO put in a function
    num_of_contracts = 1

    logger.info(f"capital_per_trade: {capital_per_trade}")
    logger.info(f"symbol: {symbol}, num_of_contracts: {num_of_contracts}")
    if num_of_contracts == 0:
        logger.warning(f"@@@@ we don't have enough capital ...")
    capital_used = num_of_contracts * 2500
    capital_remaining_after_order = available_capital - capital_used
    open_trades_count_at_entry = position_helper.calculate_number_of_open_positions()
    # update ...
    application_state.get('risk')['available_capital'] = capital_remaining_after_order

    data = {
            'timestamp': str(date_utils.time_now()),
            'trade_date': application_state.get('trading_date'),
            'symbol': symbol,
            'unique_run_number': application_state.get('unique_run_number'),
            'starting_capital': available_capital,
            'capital_used': capital_used,
            'capital_remaining_after_order': capital_remaining_after_order,
            'allowed_capital_per_trade': capital_per_trade,
            'strike': 0,
            'ask': 0,
            'num_of_contracts': num_of_contracts,
            'daily_loss_so_far': 0,
            'daily_win_so_far': 0,
            'open_trades_count_at_entry': open_trades_count_at_entry,
            'memo': '',
            }
    return num_of_contracts, data


def calcualte_availale_capital(app_config, application_state):

    available_capital = application_state.get('risk', {}).get('available_capital', None)
    if available_capital is None:
       available_capital = app_config['live']['capital']
       application_state.setdefault('risk', {}).setdefault('available_capital', available_capital )
    return available_capital

