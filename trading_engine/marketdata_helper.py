
import logging
logger = logging.getLogger(__name__)
from trading_utils import ib_marketdata_async

async def get_historical_data(ib, symbol, app_config, application_state, time_frame ='1 day', historical_days=''):
    if historical_days == '':
        mode = application_state.get('mode', 'live')
        historical_days = app_config[mode]['historical_days']

    logger.info(f"get_market_data(), symbol: {symbol}, time_frame: {time_frame}, historical_days: {historical_days}")
    df = await ib_marketdata_async.get_stock_historical_data(
        ib,
        symbol,
        time_frame=time_frame,
        duration=historical_days,
        contract_month= app_config['symbols_meta'][symbol].get('contract_month'),
        use_RTH=False
    )

    if not application_state['is_busy_time']:
        logger.info(f"in get_market_data, start: \n{df[:2].to_markdown()}")
        logger.info(f"in get_market_data, end: \n{df[-2:].to_markdown()}")
    return df
