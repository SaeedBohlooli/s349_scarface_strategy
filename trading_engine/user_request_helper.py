import asyncio
import logging
import traceback
from trading_core import engine_cycle
from trading_utils import date_utils

logger = logging.getLogger(__name__)

def process_user_requests(app_config, application_state):
    for user_request in application_state.get('user_requests', []):
        request_type = user_request.get('request_type', '')
        if 'ENGINE_PROCESSED' in user_request.get('status', ''):
            continue
        if request_type.upper() == 'OPEN_ORDER_FROM_XUI_CASE_MANUAL':
            user_request['status'] += '|ENGINE_PROCESSED'
            application_state.setdefault('case_manual_orders', []).append(user_request)


async def process_app_user_request_loop(ib, app_config, application_state, interval_sec=5):
    while True:
        try:
            if engine_cycle.should_exit(application_state=application_state):
                logger.info("[process_app_user_request_loop] Exiting as requested.")
                break
            process_user_requests(app_config, application_state)
            logger.info("process_app_user_request_loop...")
            await asyncio.sleep(interval_sec)
        except Exception as e:
            logger.warning(f"@@@ process_app_user_request_loop Unexpected error: {e}")
            logger.error(f"@@@ process_app_user_request_loop error: {traceback.format_exc()}" )
            await asyncio.sleep(interval_sec)