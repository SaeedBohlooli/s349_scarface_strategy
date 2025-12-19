from playhouse.sqlite_udf import duration

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
from trading_core import user_request_x

from trading_utils import user_request_router
from trading_utils import position_helper

from trading_engine import marketdata_helper

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
        while True:
            try:
                start_time = time.time()
                run_number += 1
                current_hh_mm_ny = self.runtime.now_hhmm()
                unique_run_number_X =  self.runtime.generate_unique_run_number(run_number)
                symbol_number = 0
                self.application_state['is_busy_time'] = False # TODO: improve this later
                for symbol in self.app_config.get('symbols'):
                    symbol_number += 1
                    unique_run_number = f'{unique_run_number_X}--{symbol_number}'
                    logger.warning(f"------------------- {symbol}, {unique_run_number}, {current_hh_mm_ny} ")
                    symbol_start_time = time.time()
                    await marketdata_helper.get_market_data(ib, symbol, self.app_config, self.application_state,time_frame='1m',historical_days='3 D' )

                logger.warning(f"==================== unique_run_number: {unique_run_number}, current_hh_mm_ny: {current_hh_mm_ny}")
                if ib is None:
                    logger.warning("ib is None... so give a try to reconnect ...")
                    await asyncio.sleep(3)
                    continue
                self.app_config = self.runtime.reload_config()

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

        state_streamer = StateStreamer(self.application_state, self.ws, interval=5)
        config_streamer = ConfigStreamer(self.app_config, self.ws, interval=12)

        self.logger.info("WebSocket server is starting...")

        await asyncio.gather(
            ws_server,
            # state_streamer.run(),
            # config_streamer.run(),
            self.engine_loop(ib),

            # user_request_x.user_request_loop(self.app_config, self.application_state),
            # self.boot.data_saver_manager.run(ib),
            # market_session_guard.market_session_guard_loop(ib, self.application_state)
        )