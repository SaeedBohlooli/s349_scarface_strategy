import logging
logger = logging.getLogger(__name__)

from ib_async import *
from trading_engine import pricing_helper
from trading_core.file_manager import FileManager
from trading_utils import date_utils
from trading_utils import global_state
from trading_utils import ib_contract
from trading_utils import ib_pricing_async


async def find_expiration_and_strikes_for_all_from_ib(ib, app_config, application_state, market_data):
    for symbol in app_config['symbols']:
        if app_config['symbols_meta'][symbol]['contract_type'] in ['Equity']:
            exchange = app_config['symbols_meta'][symbol].get('exchange', 'SMART')
            await find_expiration_and_strikes_from_ib(ib, application_state, symbol, exchange, market_data)

async def find_expiration_and_strikes_from_ib(ib, application_state, symbol, exchange, market_data):
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

    # Weekly expirations: last NYSE day Mon–Fri each week (Friday or Thursday if Fri is closed).
    weekly_exps = date_utils.next_weekly_equity_expiration_dates(10)
    expirations_manually_created = {}
    for s in app_config['symbols']:
        if s not in ['QQQ', 'SPY', 'MNQ']:
            expirations_manually_created[f"{s}-expirations"] = list(weekly_exps)
    options_meta_date_dic.update(expirations_manually_created)
    FileManager.save_named_json(options_meta_date_dic, file_name='85-strikes-expirations-ib+nazdaq+adhoc+manual.json', dir='intermediate')

    extended_strikes = extend_all_strikes(options_meta_date_dic, 10)
    options_meta_date_dic.update(extended_strikes)

    FileManager.save_named_json(options_meta_date_dic, file_name='85-strikes-expirations-ib+nazdaq+adhoc+manual+extend.json', dir='intermediate')

    logger.debug('hold it here ')
    return

def _pick_preferred_expiry(expiry_list, expiry_offset=0):
    """
    Pick expiry by index from the curated list (weekly list or IB chain).
    Coerces str → single-element list; returns yyyymmdd string for IB/cache keys.
    """
    if expiry_list is None:
        return None
    if isinstance(expiry_list, str):
        expiry_list = [expiry_list]
    if not expiry_list:
        return None

    idx = max(0, min(expiry_offset, len(expiry_list) - 1))
    return str(expiry_list[idx])


def _log_option_contract_cache_for_symbol(symbol: str, label: str = "prepare_option_contract") -> None:
    keys = [
        k for k in global_state.option_contract_cache.keys()
        if k and len(k) >= 1 and k[0] == symbol
    ]
    keys.sort(key=lambda x: (x[1] if len(x) > 1 else "", x[2] if len(x) > 2 else 0, x[3] if len(x) > 3 else ""))
    max_show = 50
    if not keys:
        logger.info(f"[{label}] option_contract_cache: no entries for {symbol}")
        return
    if len(keys) <= max_show:
        logger.info(f"[{label}] option_contract_cache for {symbol} ({len(keys)} entries): {keys}")
    else:
        logger.info(
            f"[{label}] option_contract_cache for {symbol}: {len(keys)} entries, "
            f"first {max_show}={keys[:max_show]}"
        )


async def prepare_option_contract(ib, app_config, application_state, market_data, symbol, right='C'):

    # underlying_price = get_current_price(symbol)
    underlying_price = await ib_pricing_async.get_or_subscribe_symbol_price(ib, symbol)

    options_meta_date_dic = market_data.data_store.get('options_meta_date_dic', {})

    strikes = options_meta_date_dic.get(f'{symbol}-strikes')
    expiry_list = options_meta_date_dic.get(f'{symbol}-expirations',[])

    # example: "expirations": [
    #     "20251205",
    #     "20251209",
    #     "20251212"
    # ]
    expiry_offset = app_config['symbols_meta'][symbol].get('expiry_offset', 0) # 0 means first one ... for QQQ/SPY we get the seond one ...
    expiry = _pick_preferred_expiry(expiry_list, expiry_offset)
    ex_head = list(expiry_list[:5]) if isinstance(expiry_list, list) else expiry_list
    ex_count = len(expiry_list) if isinstance(expiry_list, list) else "n/a"
    logger.info(
        f"[prepare_option_contract] symbol={symbol} right={right} underlying_price={underlying_price} "
        f"expiry_list_head={ex_head} expiry_chosen={expiry} expiry_offset={expiry_offset} (count={ex_count})"
    )
    _log_option_contract_cache_for_symbol(symbol)

    if strikes is None:
        related_keys = sorted(k for k in options_meta_date_dic.keys() if symbol in k)
        logger.warning(
            f"@@@@@ prepare_contract, strikes is None. {symbol}, {right}, underlying_price: {underlying_price}; "
            f"options_meta_date_dic keys matching symbol: {related_keys}"
        )
        return  None
    if len(strikes) == 0:
        logger.warning(
            f"[prepare_option_contract] strikes is empty list for {symbol}; "
            f"expiry_list={expiry_list} expiry_chosen={expiry}"
        )
        return None
    # --- Categorize ---
    itm_calls = [s for s in strikes if s < underlying_price]
    otm_calls = [s for s in strikes if s > underlying_price]
    itm_puts = [s for s in strikes if s > underlying_price]
    otm_puts = [s for s in strikes if s < underlying_price]

    s_min, s_max = min(strikes), max(strikes)
    head = strikes[:12] if len(strikes) > 24 else strikes
    tail = strikes[-12:] if len(strikes) > 24 else []
    logger.info(
        f"[prepare_option_contract] strikes n={len(strikes)} range=[{s_min}, {s_max}] "
        f"head={head}{' ... tail=' + str(tail) if tail else ''} | "
        f"otm_calls_n={len(otm_calls)} otm_puts_n={len(otm_puts)} "
        f"otm_calls_first5={otm_calls[:5]} otm_puts_last5={otm_puts[-5:]}"
    )
    if len(otm_calls) !=0 and len(otm_puts) != 0:
        if right == 'C':
            strike = otm_calls[0]
        else:
            strike = otm_puts[-1]

        logger.info(
            f"[prepare_option_contract] qualifying Option symbol={symbol} strike={strike} expiry={expiry} right={right}"
        )
        try:
            contract = await ib_contract.get_option_contract_cached(
                ib, symbol=symbol, strike=strike, expiry=expiry, right=right
            )
        except Exception as e:
            logger.error(
                f"[prepare_option_contract] get_option_contract_cached failed "
                f"symbol={symbol} strike={strike} expiry={expiry} right={right}: {e}",
                exc_info=True,
            )
            return None
        logger.info(f"in prepare_contract, contract: {contract}")

        return contract

    else:
        logger.error (
            f"@@@@ prepare_contract(), we have issue, {symbol}, underlying_price: {underlying_price}, expiry: {expiry}, strikes: {strikes}; "
            f"n_otm_calls={len(otm_calls)} n_otm_puts={len(otm_puts)}"
        )

        return None

    return None

async def prepare_option_contracts_for_later_use(ib, app_config, application_state, market_data):
    for symbol in app_config['symbols']:
        if app_config['symbols_meta'][symbol]['contract_type'] not in ['Equity']:
            continue
        for right in ['C', 'P']:
            result = await prepare_option_contract_for_later_use_for_symbol(ib, app_config, application_state, market_data, symbol, right)
            if result == False:
                logger.warning(f"@@ could not prepare contract for later use: {symbol}, {right}")

async def prepare_option_contract_for_later_use_for_symbol(ib, app_config, application_state, market_data, symbol, right='C'):

    underlying_price = await ib_pricing_async.get_or_subscribe_symbol_price(ib, symbol)

    options_meta_date_dic = market_data.data_store.get('options_meta_date_dic', {})

    strikes = options_meta_date_dic.get(f'{symbol}-strikes')
    expiry_list = options_meta_date_dic.get(f'{symbol}-expirations',[])

    # example: "expirations": [
    #     "20251205",
    #     "20251209",
    #     "20251212"
    # ]
    expiry_offset = app_config['symbols_meta'][symbol].get('expiry_offset', 0) # 0 means first one ... for QQQ/SPY we get the seond one ...
    expiry = _pick_preferred_expiry(expiry_list, expiry_offset)
    ex_head = list(expiry_list[:5]) if isinstance(expiry_list, list) else expiry_list
    ex_count = len(expiry_list) if isinstance(expiry_list, list) else "n/a"
    logger.info(
        f"[prepare_option_contract_for_later_use] symbol={symbol} right={right} underlying_price={underlying_price} "
        f"expiry_list_head={ex_head} expiry_chosen={expiry} (count={ex_count})"
    )
    _log_option_contract_cache_for_symbol(symbol, label="prepare_option_contract_for_later_use")

    if strikes is None:
        related_keys = sorted(k for k in options_meta_date_dic.keys() if symbol in k)
        logger.warning(
            f"@@@@@ prepare_contract, strikes is None. {symbol}, {right}, underlying_price: {underlying_price}; "
            f"options_meta_date_dic keys matching symbol: {related_keys}"
        )
        return  False
    if len(strikes) == 0:
        logger.warning(
            f"[prepare_option_contract_for_later_use] strikes is empty list for {symbol}; "
            f"expiry_list={expiry_list} expiry_chosen={expiry}"
        )
        return False

    # --- Categorize ---
    # itm_calls = [s for s in strikes if s < underlying_price]
    otm_calls = [s for s in strikes if s > underlying_price]
    # itm_puts = [s for s in strikes if s > underlying_price]
    otm_puts = [s for s in strikes if s < underlying_price]
    if len(otm_calls) ==0 or len(otm_puts) == 0:
        logger.info(
            f"@@@ prepare_option_contract_for_later_use_for_symbol, not enough otm options, skip. "
            f"symbol={symbol} underlying={underlying_price} expiry={expiry} "
            f"n_strikes={len(strikes) if strikes else 0} n_otm_calls={len(otm_calls)} n_otm_puts={len(otm_puts)}"
        )
        return False

    for i in [1,2, 3]: # try first three otm strikes

        if right == 'C':
            strike = otm_calls[i - 1]   # take the first X otm calls   0 , 1,
        else:
            strike = otm_puts[-i]   # take the last X otm puts   -1 , -2, -3

        try:
            contract = await ib_contract.get_option_contract_cached(ib, symbol=symbol, strike=strike, expiry=expiry, right=right)
        except Exception as e:
            logger.error(
                f"[prepare_option_contract_for_later_use] get_option_contract_cached failed "
                f"symbol={symbol} strike={strike} expiry={expiry} right={right}: {e}",
                exc_info=True,
            )
            continue
        logger.info(f"in prepare_contract, contract: {contract}")
        if contract is not None:
            await ib_pricing_async.subscribe_contracts_to_market_data(ib, [contract])



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
