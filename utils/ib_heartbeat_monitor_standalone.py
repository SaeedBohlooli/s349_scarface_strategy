"""
Standalone IB Heartbeat Monitor
================================
Independently monitors Interactive Brokers connection and writes heartbeat file.

Usage:
    python ib_heartbeat_monitor_standalone.py --portfolio-id p107 --interval 30 --max-reconnect-attempts 10

Features:
    - Runs independently of main trading engine
    - Connects to IB using existing config
    - Periodically checks IB connection health
    - Writes heartbeat file for watchdog monitoring
    - Auto-reconnects on connection loss
    - Comprehensive logging
"""

import argparse
import asyncio
import sys
import logging
import logging.handlers
import os
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Imports from codebase
from trading_utils import config_utils
from trading_utils import ib_utils_async


# ==================== LOGGING SETUP ====================

def setup_logging(portfolio_id: str, log_dir: str = None) -> logging.Logger:
    """Setup logging with file and console output."""
    
    if log_dir is None:
        log_dir = f"../portfolios/{portfolio_id}/logs"
    
    os.makedirs(log_dir, exist_ok=True)
    
    log_file = os.path.join(log_dir, "ib_heartbeat_monitor.log")
    
    # Create rotating file handler
    handler = logging.handlers.RotatingFileHandler(
        filename=log_file,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5
    )
    
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)
    
    # Setup console handler with same formatter
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    # Setup logger
    logger = logging.getLogger("ib_heartbeat_monitor")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    logger.addHandler(console_handler)
    
    logger.info("=" * 80)
    logger.info("IB Heartbeat Monitor Started")
    logger.info("=" * 80)
    
    return logger


# ==================== HEARTBEAT LOGIC ====================

async def ib_heartbeat_monitor_loop(
    logger: logging.Logger,
    app_config: dict,
    portfolio_id: str,
    interval_seconds: int = 30,
    max_reconnect_attempts: int = 10
):
    """
    Main heartbeat monitor loop.
    
    1. Creates/maintains IB connection
    2. Periodically checks connection health
    3. Writes heartbeat file if connection alive
    4. Handles reconnections automatically
    """
    
    # Setup paths - resolve template variables
    heartbeat_dir = app_config.get('dirs', {}).get('heartbeat')
    logger.info(f"[SETUP] Raw heartbeat_dir from config: {heartbeat_dir}")
    
    if heartbeat_dir is None:
        heartbeat_dir = f"../../portfolios/{portfolio_id}/heartbeat"
        logger.info(f"[SETUP] heartbeat_dir was None, using default: {heartbeat_dir}")
    else:
        # Resolve template placeholders like {portfolio_id}
        try:
            heartbeat_dir = heartbeat_dir.format(portfolio_id=portfolio_id)
            logger.info(f"[SETUP] Formatted heartbeat_dir: {heartbeat_dir}")
        except Exception as e:
            logger.warning(f"[SETUP] Could not format heartbeat_dir: {e}, using as-is")
    
    logger.info(f"[SETUP] Final heartbeat directory: {heartbeat_dir}")
    os.makedirs(heartbeat_dir, exist_ok=True)
    
    ib_heartbeat_file = os.path.join(heartbeat_dir, "ib_heartbeat.log")
    app_heartbeat_file = os.path.join(heartbeat_dir, "app_heartbeat.log")
    
    logger.info(f"[SETUP] Heartbeat directory: {heartbeat_dir}")
    logger.info(f"[SETUP] IB heartbeat file: {ib_heartbeat_file}")
    logger.info(f"[SETUP] App heartbeat file: {app_heartbeat_file}")
    
    # IB connection config
    ip = app_config.get('ip', '127.0.0.1')
    port = app_config.get('port', 7497)
    # Use client_id 251 by default (to avoid conflicts with main engine which uses 250)
    client_id = app_config.get('heartbeat_client_id', app_config.get('client_id', 250) + 1)
    
    logger.info(f"[SETUP] IB Connection config: {ip}:{port}, client_id={client_id}")
    logger.info(f"[SETUP] Check interval: {interval_seconds} seconds")
    logger.info(f"[SETUP] Max reconnect attempts: {max_reconnect_attempts}")
    
    ib = None
    heartbeat_count = 0
    failure_count = 0
    
    logger.info("[START] Entering main loop...")
    
    while True:
        try:
            iteration = heartbeat_count + failure_count + 1
            logger.debug(f"\n[LOOP {iteration}] ======== Heartbeat iteration {iteration} ========")
            
            # 1) Ensure IB connection exists
            if ib is None:
                logger.warning(f"[CONNECT] IB connection is None, attempting to create...")
                ib = await ib_utils_async.create_ib_async(
                    ip=ip,
                    port=port,
                    client_id=client_id,
                    retry_delay=3,
                    max_attempts=max_reconnect_attempts
                )
                
                if ib is None:
                    logger.error(f"[CONNECT] FAILED to create IB connection after {max_reconnect_attempts} attempts")
                    failure_count += 1
                    await asyncio.sleep(interval_seconds)
                    continue
                else:
                    logger.info(f"[CONNECT] [OK] IB connection created successfully")
            
            # 2) Get current timestamp
            ts = datetime.now().isoformat()
            
            # 3) Write app heartbeat (always)
            try:
                Path(app_heartbeat_file).write_text(ts)
                logger.debug(f"[HEARTBEAT] App heartbeat written: {ts}")
            except Exception as e:
                logger.error(f"[HEARTBEAT] Failed to write app heartbeat: {e}")
            
            # 4) Check if IB is connected
            if not ib.isConnected():
                logger.warning(f"[CHECK] IB.isConnected() = False")
                logger.warning(f"[CHECK] Skipping IB heartbeat write. Will attempt reconnect.")
                ib = None  # Force reconnection next iteration
                failure_count += 1
                await asyncio.sleep(interval_seconds)
                continue
            
            logger.debug(f"[CHECK] IB.isConnected() = True")
            
            # 5) Lightweight API responsiveness check
            try:
                logger.debug(f"[CHECK] Requesting current time from IB (API responsiveness check)...")
                current_time = await asyncio.wait_for(
                    ib.reqCurrentTimeAsync(),
                    timeout=5
                )
                logger.debug(f"[CHECK] [OK] IB API responsive. Current server time: {current_time}")
            except asyncio.TimeoutError:
                logger.error(f"[CHECK] [FAIL] IB API timeout (5 seconds) - connection may be stalled")
                ib = None
                failure_count += 1
                await asyncio.sleep(interval_seconds)
                continue
            except Exception as e:
                logger.error(f"[CHECK] [FAIL] IB API check failed: {e}")
                ib = None
                failure_count += 1
                await asyncio.sleep(interval_seconds)
                continue
            
            # 6) Write IB heartbeat
            try:
                Path(ib_heartbeat_file).write_text(ts)
                heartbeat_count += 1
                logger.info(f"[HEARTBEAT] [OK] IB heartbeat written [{heartbeat_count}] at {ts}")
                logger.debug(f"[HEARTBEAT] File: {ib_heartbeat_file}")
            except Exception as e:
                logger.error(f"[HEARTBEAT] Failed to write IB heartbeat file: {e}")
                failure_count += 1
        
        except Exception as ex:
            logger.error(f"[ERROR] Unexpected error in heartbeat loop: {ex}")
            logger.error(f"[ERROR] Traceback: {type(ex).__name__}")
            import traceback
            logger.error(traceback.format_exc())
            ib = None
            failure_count += 1
        
        # Sleep before next iteration
        logger.debug(f"[SLEEP] Sleeping for {interval_seconds} seconds before next check...")
        await asyncio.sleep(interval_seconds)


# ==================== MAIN ====================

async def main_async(portfolio_id: str, interval_seconds: int, max_reconnect_attempts: int):
    """Async entry point."""
    
    logger = setup_logging(portfolio_id)
    
    logger.info(f"[INIT] Loading config for portfolio: {portfolio_id}")
    try:
        app_config = config_utils.load_app_config(portfolio_id)
        logger.info(f"[INIT] [OK] Config loaded successfully")
        logger.info(f"[INIT] Config keys: {list(app_config.keys())}")
    except Exception as e:
        logger.error(f"[INIT] [FAIL] Failed to load config: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise
    
    logger.info(f"[INIT] Starting heartbeat monitor loop...")
    
    await ib_heartbeat_monitor_loop(
        logger=logger,
        app_config=app_config,
        portfolio_id=portfolio_id,
        interval_seconds=interval_seconds,
        max_reconnect_attempts=max_reconnect_attempts
    )


def main():
    """Entry point."""
    
    parser = argparse.ArgumentParser(
        description="Standalone IB Heartbeat Monitor - Monitors IB connection 24/7"
    )
    parser.add_argument(
        "--portfolio-id",
        required=False,
        default="p107",
        help="Portfolio ID (default: p107)"
    )
    parser.add_argument(
        "--interval",
        type=int,
        required=False,
        default=30,
        help="Check interval in seconds (default: 30)"
    )
    parser.add_argument(
        "--max-reconnect-attempts",
        type=int,
        required=False,
        default=10,
        help="Max reconnection attempts (default: 10)"
    )
    
    args = parser.parse_args()
    
    print(f"Starting IB Heartbeat Monitor")
    print(f"  Portfolio ID: {args.portfolio_id}")
    print(f"  Check interval: {args.interval} seconds")
    print(f"  Max reconnect attempts: {args.max_reconnect_attempts}")
    print()
    
    try:
        asyncio.run(main_async(
            portfolio_id=args.portfolio_id,
            interval_seconds=args.interval,
            max_reconnect_attempts=args.max_reconnect_attempts
        ))
    except KeyboardInterrupt:
        print("\n[SHUTDOWN] Keyboard interrupt received. Shutting down gracefully...")
    except Exception as e:
        print(f"\n[FATAL] Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

