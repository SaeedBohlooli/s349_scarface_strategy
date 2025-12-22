from bokeh.models.widgets import indicators

from trading_utils import *
import logging
logger = logging.getLogger(__name__)
import sys
sys.path.insert(0, f'../')

from trading_core.ws_server import WSServer
from trading_core.file_manager import FileManager
from trading_core.streamers.state_streamer import StateStreamer
from trading_core.streamers.config_streamer import ConfigStreamer
from trading_core.ib_connector import IBConnector
from trading_core.market_data_store import MarketDataStore
from trading_core import market_session_guard
from trading_core import application_state_router


from trading_utils import user_request_router

from trading_engine import marketdata_helper
from trading_engine import inidicators
from trading_engine import strategy
from trading_engine import application_state_helper
from trading_engine import scanner

from utils import atr_tolerance_helper

class TradingEngine:

    def __init__(self, boot):
        self.boot = boot
        self.logger = boot.logger
        self.app_config = boot.app_config
        self.application_state = boot.application_state
        self.ws = WSServer(host="0.0.0.0", port=self.app_config.get('ws_port', 6666))
        self.runtime = boot.runtime
        self.market_data = MarketDataStore()




    async def engine_loop(self, ib):
        run_number = 0
        initial_setup = False
        application_state_helper.initialize_application_state(self.app_config, self.application_state)
        while True:
            try:
                start_time = time.time()
                run_number += 1
                current_hh_mm_ny = self.runtime.now_hhmm()
                unique_run_number_X =  self.runtime.generate_unique_run_number(run_number)
                day_of_week = self.runtime.now_day_of_week()
                symbol_number = 0
                logger.info(f"==================== run_number: {run_number}, unique_run_number_X: {unique_run_number_X}")

                self.application_state['is_busy_time'] = False # TODO: improve this later

                if ib is None:
                    logger.warning("ib is None... so give a try to reconnect ...")
                    await asyncio.sleep(3)
                    continue
                self.app_config = self.runtime.reload_config()

                is_trade_time = eval(self.app_config['live']['trade_time'])
                is_busy_time = eval(self.app_config['live'].get('busy_time', '1 == 1'))
                is_market_time = eval(self.app_config['live'].get('market_time', '1 == 1'))

                for symbol in self.app_config.get('symbols'):
                    symbol_number += 1
                    unique_run_number = f'{unique_run_number_X}--{symbol_number}'
                    logger.warning(f"------------------- {symbol}, {unique_run_number}, {current_hh_mm_ny} ")
                    symbol_start_time = time.time()
                    df = await marketdata_helper.get_historical_data(ib, symbol, self.app_config, self.application_state, time_frame='1m', historical_days='3 D')
                    self.market_data.dfs_map[symbol] = df
                    df = inidicators.popualate_features(df)
                    df = inidicators.populate_volume_ratio(df)
                    self.market_data.dfs_with_indicators[symbol] = df
                    if not is_busy_time:
                        logger.info(f"{symbol}, df: \n{df[-4:].to_markdown()}")
                    last_record_hh_mm = date_utils.get_last_record_hhmm(df)  # TODO is not used anywhere ...
                    qqq_df = self.market_data.dfs_map.get('QQQ')
                    relative_strength_df = inidicators.compute_relative_strength(df, qqq_df, period=20)
                    intraday_rs_df = inidicators.compute_intraday_rs(df, qqq_df)
                    dynamic_tolerance = atr_tolerance_helper.get_dynamic_tolerance(df[:-1].copy(), level=0, min_tick=0.01)  # Drop -1 as it fluctates ans SL triggers ...

                    # Levels
                    if not self.application_state['symbols'][symbol].get('PDH'):  # PDH is not calculated yet
                        strategy.calculate_PDL_PDH(df,symbol, day_of_week=day_of_week, application_state=self.application_state)

                    are_all_levels_in = strategy.all_levels_in(self.application_state, symbol)
                    if not are_all_levels_in:  # if not in, recalcualte ...
                        # TODO need to be checked, we need to pass that candle... better to calculate every time ..
                        strategy.find_add_PMH_PML(self.application_state, df, symbol)
                        strategy.find_add_5MH_5ML(self.application_state, df, symbol)

                    current_price = await ib_pricing_async.get_or_subscribe_symbol_price(ib, symbol, contract_month=self.app_config.get('symbols_meta', {}).get(symbol, {}).get('contract_month'))
                    self.application_state['symbols'].setdefault(symbol, {})['current_price'] = current_price

                    scanner.check_buy_and_sell_cases(self.app_config, self.application_state, symbol, self.market_data)
                    symbol_end_time = time.time()
                    symbol_run_spend_time = round(symbol_end_time - symbol_start_time, 2)
                    logger.warning(f'------------------- {symbol}, {unique_run_number}, symbol_run_spend_time: {symbol_run_spend_time} seconds')

                application_state_router.populate_global_state(application_state=self.application_state)


                end_time = time.time()
                run_time_spent = round(end_time - start_time, 2)
                logger.warning(f'==================== unique_run_number: {unique_run_number}, run_spent_time: {run_time_spent} seconds, no sleep ...')

                await asyncio.sleep(self.app_config['interval_seconds']['engine_loop'])
            except Exception as e:
                logger.warning(f"@@@ Unexpected error in engine_loop: {e}")
                logger.error(f"@@@ error: {traceback.format_exc()}" )
                await asyncio.sleep(self.app_config['interval_seconds']['engine_loop'])


    async def run(self):
        logger.info("Starting Trading Engine")
        ib = await IBConnector.connect_from_config(self.app_config)

        ws_server = await self.ws.start()

        state_streamer = StateStreamer(self.app_config, self.application_state, self.ws, interval=5)
        config_streamer = ConfigStreamer(self.app_config, self.application_state, self.ws, interval=12)

        self.logger.info("WebSocket server is starting...")

        await asyncio.gather(
            ws_server,
            state_streamer.run(),
            # config_streamer.run(),
            self.engine_loop(ib),

            # user_request_x.user_request_loop(self.app_config, self.application_state),
            # self.boot.data_saver_manager.run(ib),
            # market_session_guard.market_session_guard_loop(ib, self.application_state)
        )