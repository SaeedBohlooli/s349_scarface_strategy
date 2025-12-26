
from trading_utils import ib_pricing_async, date_utils


async def initialize_application_state(ib, app_config, application_state):

    """

    :param application_state:
    :return:
    """
    application_state['symbols'] = {}
    for symbol in app_config['symbols']:
        application_state['symbols'][symbol] = {}
        current_price = await ib_pricing_async.get_or_subscribe_symbol_price(
            ib,symbol,contract_month=app_config.get('symbols_meta', {}).get(symbol,{}).get('contract_month'), wait_for_price=True, timeout_sec=300)

        if current_price is None:
            current_price = -1.0

        application_state.setdefault('latest_prices', {})[symbol] = current_price

    application_state['is_busy_time'] = False
    application_state['trading_date'] = date_utils.get_yyyymmdd()

    # application_state['latest_prices'] = {}
    # application_state['current_price'] = {}


def initialize_application_state_for_run(app_config, application_state):

    """

    :param application_state:
    :return:
    """
    application_state['breakouts'] = {}
    application_state['retests'] = {}
    application_state['breakout_idx'] = {}
    application_state['retest_idx'] = {}
    application_state['levels'] = {}
    # for symbol in app_config['symbols']:
    #     application_state['symbols'][symbol] = {}
    #
    # application_state['is_busy_time'] = False
