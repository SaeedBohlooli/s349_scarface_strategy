import logging
logger = logging.getLogger(__name__)

from ib_async import *
from trading_engine import pricing_helper
from trading_core.file_manager import FileManager
from trading_utils import date_utils
from trading_utils import ib_contract
from trading_utils import ib_pricing_async


async def find_expiration_and_strikes_for_all_from_ib(ib, app_config, application_state):
    for symbol in app_config['symbols']:
        if app_config['symbols_meta'][symbol]['contract_type'] in ['Equity']:
            exchange = app_config['symbols_meta'][symbol].get('exchange', 'SMART')
            await find_expiration_and_strikes_from_ib(ib, application_state, symbol, exchange)

async def find_expiration_and_strikes_from_ib(ib, application_state, symbol, exchange):
    underlying = Stock(symbol, 'SMART', 'USD')
    logger.info(f"underlying: {underlying}, type: {type(underlying)}, module: {type(underlying).__module__}" )

    q = await ib_contract.get_cached_contract(ib, symbol)

    logger.info(f"underlying: {underlying}:  qualifyContracts: {q}")

    if not q :
        logger.warning(f"@@@@ find_expiration_and_strikes_from_ib, underlying contract not qualified. {symbol}: {underlying}")
        return
    #  Request all option chains for this symbol
    chains = await ib.reqSecDefOptParamsAsync(symbol, '', 'STK', q.conId)
    if chains is None:
        logger.warning(f"@@@ chains is Null for symbol: {symbol}")
        return
    # Look at what's available
    # for chain in chains:
    #     logger.info(f"Exchange:{chain.exchange}")
    #     logger.info(f"Trading class:{chain.tradingClass}")
    #     logger.info(f"Expirations:{sorted(chain.expirations)}")
    #     logger.info(f"Strikes (sample):{sorted(chain.strikes)[:10]}")
    #     logger.info("----------")

    #Go through each c in chains and give me the first one whose exchange equals 'SMART'.”
    if symbol in ['QQQ', 'SPY']:
        chain = get_best_option_chain(chains) # we choose the one has more
    else:
        chain = next((c for c in chains if c.exchange == 'SMART'), None) # leave it ias is ... go with firsto ne, retruns None if didtn fif

    if chain is None:
        logger.warning(f"@@@@ no option chain found for symbol: {symbol} on exchange: {exchange}")
        return

    expiry = sorted(chain.expirations)[0]
    strikes = sorted(chain.strikes)
    strikes = [s for s in strikes if abs(s * 10 % 5) < 1e-6]  # keeps only .0 and .5 . IB has messy data ...

    options_meta_date_dic = application_state.setdefault('options_meta_date_dic', {})
    options_meta_date_dic[f'{symbol}-strikes'] = strikes
    options_meta_date_dic[f'{symbol}-expirations'] = sorted(chain.expirations)

    if symbol in ['NVDA', 'TSLL']:
        logger.debug('hold it here....')

    return


def get_best_option_chain(chains):
    """
    Selects the option chain with the most expirations,
    preferring SMART first, then CBOE variants.
    """
    # Filter only relevant exchanges
    # candidates = [c for c in chains if c.exchange.startswith('SMART') or c.exchange.startswith('CBOE')]
    candidates = [c for c in chains if c.exchange.startswith('SMART')]
    if not candidates:
        return None

    # Pick the one with the most expirations
    best = max(candidates, key=lambda c: len(c.expirations))
    logger.info(f" Using {best.exchange} ({best.tradingClass}) with {len(best.expirations)} expirations")
    return best


async def orchestrate_expirations_strikes(ib, app_config, application_state):
    # intermediate_dir = 'intermediate'
    shared_dir = '../../portfolios/shared'
    options_meta_date_dic = application_state.setdefault('options_meta_date_dic', {})

    # get from IB. is messy ...
    await find_expiration_and_strikes_for_all_from_ib(ib, app_config, application_state)
    # file_utils.save_a_map_to_file(options_meta_date_dic, file_path=f'{intermediate_dir}/85-strikes-expirations-ib.json')
    FileManager.save_named_json(options_meta_date_dic, file_name='85-strikes-expirations-ib.json', dir='intermediate')

    # Mere with Nazadq ...
    nazdaq_file = f'{shared_dir}/85-strikes-nazdaq.json'
    strikes_from_nazdaq = FileManager.load_named_json(full_path=nazdaq_file)

    if strikes_from_nazdaq != {}:
        options_meta_date_dic.update(strikes_from_nazdaq)
        FileManager.save_named_json(options_meta_date_dic, file_name='85-strikes-expirations-ib+nazdaq.json', dir='intermediate')

    adhoc_file = f'{shared_dir}/85-strikes-adhoc.json'
    strikes_from_adhoc = FileManager.load_named_json(full_path=adhoc_file)
    if strikes_from_adhoc != {}:
        options_meta_date_dic.update(strikes_from_adhoc)
        FileManager.save_named_json(options_meta_date_dic, file_name='85-strikes-expirations-ib+nazdaq+adhoc.json', dir='intermediate')

    expirations_manually_created = {}
    for s in app_config['symbols']:
        if s not in ['QQQ', 'SPY', 'MNQ']:
            expirations_manually_created[f"{s}-expirations"] = date_utils.next_fridays(10)
    options_meta_date_dic.update(expirations_manually_created)
    FileManager.save_named_json(options_meta_date_dic, file_name='85-strikes-expirations-ib+nazdaq+adhoc+manual.json', dir='intermediate')

    logger.debug('hold it here ')
    return


async def prepare_option_contract(ib, app_config, application_state, symbol, right='C'):

    # underlying_price = get_current_price(symbol)
    underlying_price = await ib_pricing_async.get_or_subscribe_symbol_price(ib, symbol)

    options_meta_date_dic = application_state.setdefault('options_meta_date_dic', {})
    strikes = options_meta_date_dic.get(f'{symbol}-strikes')

    # example: "expirations": [
    #     "20251205",
    #     "20251209",
    #     "20251212"
    # ]
    expiry_offset = app_config['symbols_meta'][symbol].get('expiry_offset', 0) # 0 means first one ... for QQQ/SPY we get the seond one ...

    expiry_list = options_meta_date_dic.get(f'{symbol}-expirations',[])
    expiry = expiry_list[expiry_offset] if expiry_list else None
    if strikes is None:
        logger.warning(f"@@@@@ prepare_contract, strikes is None. {symbol}, {right}, underlying_price: {underlying_price}")
        return  None
    # --- Categorize ---
    itm_calls = [s for s in strikes if s < underlying_price]
    otm_calls = [s for s in strikes if s > underlying_price]
    itm_puts = [s for s in strikes if s > underlying_price]
    otm_puts = [s for s in strikes if s < underlying_price]
    if len(otm_calls) !=0 and len(otm_puts) != 0:
        if right == 'C':
            strike = otm_calls[0]
        else:
            strike = otm_puts[-1]

        contract = await ib_contract.get_option_contract_cached(ib, symbol=symbol, strike=strike, expiry=expiry, right=right)
        # contract = create_option_contract(strike=strike, expiry=expiry, right=right,exchange="SMART", symbol=symbol, trading_class='')
        logger.info(f"in prepare_contract, contract: {contract}")

        return contract

    else:
        logger.error (f"@@@@ prepare_contract(), we have issue, {symbol}, underlying_price: {underlying_price}, expiry: {expiry}, strikes: {strikes}")

        return None

    return None

