import logging
logger = logging.getLogger(__name__)

from ib_async import *
from trading_engine import pricing_helper
from trading_core.file_manager import FileManager
from trading_utils import date_utils
from trading_utils import ib_contract
from trading_utils import ib_pricing_async
from trading_utils import number_utils
from trading_utils import global_state


async def find_expiration_and_strikes_for_all_from_ib(ib, app_config, application_state, market_data):
    for symbol in app_config['symbols']:
        if app_config['symbols_meta'][symbol]['contract_type'] in ['Equity']:
            exchange = app_config['symbols_meta'][symbol].get('exchange', 'SMART')
            await find_expiration_and_strikes_from_ib(ib, application_state, symbol, exchange, market_data)

async def find_expiration_and_strikes_from_ib(ib, application_state, symbol, exchange, market_data):
    underlying = Stock(symbol, 'SMART', 'USD')
    logger.info(f"[find_expiration_and_strikes_from_ib] underlying: {underlying}, type: {type(underlying)}, module: {type(underlying).__module__}" )

    q = await ib_contract.get_cached_contract(ib, symbol)

    logger.info(f"[find_expiration_and_strikes_from_ib] underlying: {underlying}:  qualifyContracts: {q}")

    if not q :
        logger.warning(f"[find_expiration_and_strikes_from_ib] @@@@ find_expiration_and_strikes_from_ib, underlying contract not qualified. {symbol}: {underlying}")
        return
    #  Request all option chains for this symbol
    chains = await ib.reqSecDefOptParamsAsync(symbol, '', 'STK', q.conId)
    if chains is None:
        logger.warning(f"[find_expiration_and_strikes_from_ib] @@@ chains is Null for symbol: {symbol}")
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

    # options_meta_date_dic = application_state.setdefault('options_meta_date_dic', {})
    options_meta_date_dic = market_data.data_store.get('options_meta_date_dic', {})
    options_meta_date_dic[f'{symbol}-strikes'] = strikes
    options_meta_date_dic[f'{symbol}-expirations'] = sorted(chain.expirations)

    set_options_meta_date_dic(market_data, options_meta_date_dic)

    if symbol in ['NVDA', 'TSLL']:
        logger.debug('hold it here....')

    return


def set_options_meta_date_dic(market_data, options_meta_date_dic):
    market_data.data_store.setdefault('options_meta_date_dic', options_meta_date_dic)

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


async def orchestrate_expirations_strikes(ib, app_config, application_state, market_data):
    # intermediate_dir = 'intermediate'
    shared_dir = '../../portfolios/shared'
    # options_meta_date_dic = application_state.setdefault('options_meta_date_dic', {})

    # get from IB. is messy ...
    await find_expiration_and_strikes_for_all_from_ib(ib, app_config, application_state, market_data)
    options_meta_date_dic = market_data.data_store.get('options_meta_date_dic', {})
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

    extended_strikes = extend_all_strikes(options_meta_date_dic, 20)
    options_meta_date_dic.update(extended_strikes)

    FileManager.save_named_json(options_meta_date_dic, file_name='85-strikes-expirations-ib+nazdaq+adhoc+manual+extend.json', dir='intermediate')

    logger.debug('hold it here ')
    return


async def prepare_option_contract(ib, app_config, application_state, market_data, symbol, right='C', user_defined_expiry=0, user_defined_strike =0 ):

    min_contract_price = app_config['symbols_meta'][symbol].get('min_contract_price', 0)
    if min_contract_price == 0:
        min_contract_price =  app_config['positioning'].get('min_contract_price', 0)

    underlying_price = await ib_pricing_async.get_or_subscribe_symbol_price(ib, symbol)

    options_meta_date_dic = market_data.data_store.get('options_meta_date_dic', {})

    expiry_list = options_meta_date_dic.get(f'{symbol}-expirations', [])
    # example: "APPL-expirations": [
    #     "20251205",
    #     "20251209",
    #     "20251212"
    # ]
    expiry_offset = app_config['symbols_meta'][symbol].get('expiry_offset', 0)  # 0 means first one ... for QQQ/SPY we get the seond one ...
    expiry = expiry_list[expiry_offset] if expiry_list else None
    strike = 0
    if user_defined_strike == 0: # app selects ...

        strikes = options_meta_date_dic.get(f'{symbol}-strikes')
        if strikes is None:
            logger.warning(f"@@@@@ [prepare_contract], strikes is None. {symbol}, {right}, underlying_price: {underlying_price}")
            return  None
        # --- Categorize ---
        itm_calls = [s for s in strikes if s < underlying_price]
        otm_calls = [s for s in strikes if s > underlying_price]
        itm_puts = [s for s in strikes if s > underlying_price]
        otm_puts = [s for s in strikes if s < underlying_price]
        strike_found = False
        adj_index = 0 # we move in the list ...
        while not strike_found:
            if len(otm_calls) !=0 and len(otm_puts) != 0:
                if right == 'C':
                    strike = otm_calls[0 + adj_index]   # 0 , 1, 2 ....
                else:
                    strike = otm_puts[-1 -adj_index]  # -1, -2 , -3 ...
            else:
                logger.error (f"@@@@ [prepare_contract], we have issue, {symbol}, underlying_price: {underlying_price}, expiry: {expiry}, strikes: {strikes}")

                return None
            bid, ask, last = await pricing_helper.get_quote_for_option_bid_ask(ib, symbol=symbol, expiry=expiry, strike=strike, right=right)
            if not number_utils.is_valid_price(bid) or not number_utils.is_valid_price(ask):
                logger.warning(f"@@@@ [prepare_contract], bid or ask is None, {symbol}, underlying_price: {underlying_price}, expiry: {expiry}, strike: {strike}, right: {right}")
                return None
            mid_price = (bid + ask) / 2
            if mid_price >= min_contract_price:
                strike_found = True
            else:
                logger.info(f"[prepate_contract] @ mid_price is less then min_contract_price, strike: {strike}, mid_price: {mid_price}, min_contract_price: {min_contract_price} ")
                adj_index += 1
    else:
        strike = user_defined_strike


    contract = await ib_contract.get_option_contract_cached(ib, symbol=symbol, strike=strike, expiry=expiry, right=right)
    logger.info(f"[prepare_contract] contract: {contract}")

    return contract

    return None

async def subscribe_market_data_for_all_otm_option_contracts(ib, app_config, application_state, market_data):
    for symbol in app_config['symbols']:
        if app_config['symbols_meta'][symbol]['contract_type'] not in ['Equity']:
            continue
        for right in ['C', 'P']:
            result = await subscribe_market_data_for_otm_option_contracts(ib, app_config, application_state, market_data, symbol, right)
            if result == False:
                logger.warning(f"@@@@ [subscribe_market_data_for_all_otm_option_contracts], could not prepare contract for later use: {symbol}, {right}")

async def subscribe_market_data_for_otm_option_contracts(ib, app_config, application_state, market_data, symbol, right='C'):

    underlying_price = await ib_pricing_async.get_or_subscribe_symbol_price(ib, symbol)

    options_meta_date_dic = market_data.data_store.get('options_meta_date_dic', {})

    strikes = options_meta_date_dic.get(f'{symbol}-strikes')
    expiry_list = options_meta_date_dic.get(f'{symbol}-expirations',[])

    # example: "AMD-expirations": [
    #     "20251205",
    #     "20251209",
    #     "20251212"
    # ]
    expiry_offset = app_config['symbols_meta'][symbol].get('expiry_offset', 0) # 0 means first one ... for QQQ/SPY we get the seond one ...

    expiry = expiry_list[expiry_offset] if expiry_list else None
    if strikes is None:
        logger.warning(f"[subscribe_market_data_for_otm_option_contracts] @@@@@ , strikes is None. {symbol}, {right}, underlying_price: {underlying_price}")
        return  False

    # --- Categorize ---
    # itm_calls = [s for s in strikes if s < underlying_price]
    otm_calls = [s for s in strikes if s > underlying_price]
    # itm_puts = [s for s in strikes if s > underlying_price]
    otm_puts = [s for s in strikes if s < underlying_price]
    if len(otm_calls) ==0 or len(otm_puts) == 0:
        logger.warning("[subscribe_market_data_for_otm_option_contracts] @@@ not enough otm options, so skip for later use.")
        return False

    max_otm_strikes_to_try = app_config.get('options', {}).get("max_otm_strikes_to_try", 3)

    for i in range(1,max_otm_strikes_to_try + 1 ): # try first X otm strikes # try first X otm strikes

        if right == 'C':
            strike = otm_calls[i - 1]   # take the first X otm calls   0 , 1,
        else:
            strike = otm_puts[-i]   # take the last X otm puts   -1 , -2, -3

        contract = await ib_contract.get_option_contract_cached(ib, symbol=symbol, strike=strike, expiry=expiry, right=right)
        logger.info(f"[subscribe_market_data_for_otm_option_contracts], contract: {contract}")
        if contract is not None:
            await ib_pricing_async.subscribe_contracts_to_market_data(ib, [contract])
        else:
            logger.warning(f"[subscribe_market_data_for_otm_option_contracts] @@@ contract is None")


    return True

async def unsubscribe_market_data_for_itm_option_contracts(ib):

    contracts_to_unsubscribe_for_market_data = []
    for conid in global_state.conid_to_symbol_subscribed_for_quotes.keys():
        contract = global_state.conid_to_contract_cache.get(conid)
        if contract is None:
            continue

        if not isinstance(contract, Option) :
            # if not option move on ... we only care about options here
            continue
        # "Option(conId=879041559, symbol='QQQ', lastTradeDateOrContractMonth='20260514', strike=715.0, right='C', multiplier='100',
        # exchange='SMART', currency='USD', localSymbol='QQQ   260514C00715000', tradingClass='QQQ')",
        symbol = contract.tradingClass
        underlying_price = await ib_pricing_async.get_or_subscribe_symbol_price(ib, symbol)

        if contract.right == 'C' and contract.strike + 2 < underlying_price:
            # price < strike, so remove it ....
            contracts_to_unsubscribe_for_market_data.append(contract)
            logger.info(f"[unsubscribe_market_data_for_itm_option_contracts] {symbol}, {contract.right}, strike: {contract.strike}, underlying_price: {underlying_price}, contract: {contract}")
        elif contract.right == 'P' and contract.strike - 2 > underlying_price:
            # price > strike, so remove it ....
            contracts_to_unsubscribe_for_market_data.append(contract)
            logger.info(f"[unsubscribe_market_data_for_itm_option_contracts] {symbol}, {contract.right}, strike: {contract.strike}, underlying_price: {underlying_price}, contract: {contract}")

    if contracts_to_unsubscribe_for_market_data:
        await ib_pricing_async.unsubscribe_contracts_from_market_data(ib,contracts_to_unsubscribe_for_market_data)


    return True

async def unsubscribe_excessively_distant_option_contracts(ib):

    contracts_to_unsubscribe_for_market_data = []
    for conid in global_state.conid_to_symbol_subscribed_for_quotes.keys():
        contract = global_state.conid_to_contract_cache.get(conid)
        if contract is None:
            continue

        if not isinstance(contract, Option) :
            # if not option move on ... we only care about options here
            continue
        # "Option(conId=879041559, symbol='QQQ', lastTradeDateOrContractMonth='20260514', strike=715.0, right='C', multiplier='100',
        # exchange='SMART', currency='USD', localSymbol='QQQ   260514C00715000', tradingClass='QQQ')",
        symbol = contract.tradingClass
        underlying_price = await ib_pricing_async.get_or_subscribe_symbol_price(ib, symbol)

        if contract.right == 'C' and contract.strike > underlying_price + 10:
            # price < strike, so remove it ....
            contracts_to_unsubscribe_for_market_data.append(contract)
            logger.info(f"[unsubscribe_excessively_distant_option_contracts] {symbol}, {contract.right}, strike: {contract.strike}, underlying_price: {underlying_price}, contract: {contract}")
        elif contract.right == 'P' and contract.strike < underlying_price - 10:
            # price > strike, so remove it ....
            contracts_to_unsubscribe_for_market_data.append(contract)
            logger.info(f"[unsubscribe_excessively_distant_option_contracts] {symbol}, {contract.right}, strike: {contract.strike}, underlying_price: {underlying_price}, contract: {contract}")

    if contracts_to_unsubscribe_for_market_data:
        await ib_pricing_async.unsubscribe_contracts_from_market_data(ib,contracts_to_unsubscribe_for_market_data)


    return True


def extend_all_strikes(data: dict, n: int = 5) -> dict:
    for key, strikes in data.items():
        if not key.endswith("-strikes"):
            continue

        if not strikes or len(strikes) < 2:
            continue  # skip invalid entries safely

        strikes = sorted(strikes)

        # infer step size
        diffs = [
            round(strikes[i + 1] - strikes[i], 10)
            for i in range(len(strikes) - 1)
            if strikes[i + 1] > strikes[i]
        ]

        if not diffs:
            continue

        step = min(diffs)

        start = strikes[0]
        end = strikes[-1]

        lower = [round(start - step * i, 10) for i in range(n, 0, -1)]
        upper = [round(end + step * i, 10) for i in range(1, n + 1)]

        data[key] = lower + strikes + upper

    return data
