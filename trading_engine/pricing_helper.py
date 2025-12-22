from tensorboard.compat.proto.struct_pb2 import NoneValue

from trading_utils import ib_contract, ib_pricing_async


async def subscribe_for_current_price(ib, app_config, application_state):
    return
    for symbol in application_state['symbols']:
        current_price = await ib_pricing_async.get_or_subscribe_symbol_price(ib, symbol, app_config.get('symbols_meta', {}).get(symbol, {}).get('contract_month'))
        if current_price is None:
            current_price = -1.0
        application_state.setdefault('current_prices', {})[symbol] = current_price
