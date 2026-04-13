from trading_utils import ib_contract, ib_pricing_async

async def subscribe_for_current_price(ib, app_config, application_state):

    for symbol in application_state['symbols']:
        current_price = await ib_pricing_async.get_or_subscribe_symbol_price(ib, symbol, app_config.get('symbols_meta', {}).get(symbol, {}).get('contract_month'))
        if current_price is None:
            current_price = -1.0
        application_state.setdefault('latest_prices', {})[symbol] = current_price

def get_latest_price(application_state, symbol):
    return application_state.get('latest_prices', {}).get(symbol, None)


async def get_quote_for_option_bid_ask(ib, symbol, expiry, strike, right ):

    bid, ask, last = await ib_pricing_async.get_or_subscribe_option_price(ib, symbol, expiry, strike, right )
    return bid, ask, last

