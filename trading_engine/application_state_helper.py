
from trading_utils import ib_pricing_async, date_utils
from trading_engine import risk_helper
from trading_engine import position_helper



def initialize_application_state_replay(
    app_config, application_state, replay_symbols: list | None = None
) -> None:
    """
    Build minimal application_state for bar replay without IB subscriptions.
    replay_symbols defaults to app_config['symbols']; may include QQQ pulled in only for RS.
    """
    sym_list = list(replay_symbols) if replay_symbols else list(app_config.get("symbols", []))
    application_state.setdefault('capital_allocation', [])
    application_state['symbols'] = {s: {} for s in sym_list}
    application_state['options_meta_date_dic'] = {}
    application_state['levels'] = {}
    application_state['breakouts'] = {}
    application_state['retests'] = {}
    application_state['breakout_idx'] = {}
    application_state['retest_idx'] = {}
    application_state.setdefault('engine', {})['exit_requested'] = False
    application_state['is_busy_time'] = False
    application_state['trading_date'] = date_utils.get_yyyymmdd()
    application_state['TradingLedger.get_all_dataframe_stats'] = []
    application_state['TradingLedger.get_all_list_stats'] = []
    application_state['forced_exits'] = []
    application_state['case_manual_orders'] = []
    application_state.setdefault('latest_prices', {})
    application_state.setdefault('open_trades_dic', {})
    application_state.setdefault('mode', 'live')
    application_state['chart_replay_save_full'] = True
    for symbol in sym_list:
        application_state.setdefault('latest_prices', {}).setdefault(symbol, -1.0)


async def initialize_application_state(ib, app_config, application_state):

    """

    :param application_state:
    :return:
    """
    application_state['capital_allocation'] = []
    application_state['symbols'] = {}
    application_state['options_meta_date_dic'] = {}
    application_state['levels'] = {}
    application_state.setdefault('engine', {})['exit_requested'] = False
    application_state['is_busy_time'] = False
    application_state['trading_date'] = date_utils.get_yyyymmdd()
    application_state['TradingLedger.get_all_dataframe_stats'] = []
    application_state['TradingLedger.get_all_list_stats'] = []
    application_state['forced_exits'] = []
    application_state['case_manual_orders'] = []

    for symbol in app_config['symbols']:
        application_state['symbols'][symbol] = {}
        current_price = await ib_pricing_async.get_or_subscribe_symbol_price(
            ib,symbol,contract_month=app_config.get('symbols_meta', {}).get(symbol,{}).get('contract_month'), wait_for_price=True, timeout_sec=300)

        if current_price is None:
            current_price = -1.0

        application_state.setdefault('latest_prices', {})[symbol] = current_price


    # application_state['latest_prices'] = {}
    # application_state['current_price'] = {}


def initialize_application_state_for_run(app_config, application_state):

    # Bar replay needs cumulative breakout/retest lists across simulated minutes; clearing here
    # every tick makes scanner logic blind to prior candles (no BREAKOUT/RETEST hover markers).
    if not application_state.get("chart_replay_save_full"):
        application_state["breakouts"] = {}
        application_state["retests"] = {}
        application_state["breakout_idx"] = {}
        application_state["retest_idx"] = {}
    else:
        application_state.setdefault("breakouts", {})
        application_state.setdefault("retests", {})
        application_state.setdefault("breakout_idx", {})
        application_state.setdefault("retest_idx", {})

    current_hh_mm_ny = date_utils.get_current_hhmm_ny() #used in the config evals for trade_time
    is_trade_time = eval(app_config['live']['trade_time'])
    is_busy_time = eval(app_config['live'].get('busy_time', '1 == 1'))
    is_market_time = eval(app_config['live'].get('market_time', '1 == 1'))

    application_state['is_trade_time'] = is_trade_time
    application_state['is_busy_time'] = is_busy_time
    application_state['is_market_time'] = is_market_time

    if is_busy_time or position_helper.calculate_number_of_open_positions(application_state) != 0:
        application_state['is_save_time'] =  False
    else:
        application_state['is_save_time'] =  True



def initialize_application_state_for_symbol_run(app_config, application_state):
    application_state['up_offset_counter'] = 0
    application_state['down_offset_counter'] = 0  # TODO need to be handles better