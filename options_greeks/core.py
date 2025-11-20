import os
import time
import logging
from datetime import datetime

# --- relative imports inside the package ---
from .ib_helpers import connect_ib_client, fetch_es_positions
from .market_data import collect_market_data
from .processing import enrich_with_pnl, compute_exposures, finalize_dataframe
from .reporting import export_portfolio, send_alerts

# --- import ib_connection from parent directory ---
from ib_connection import request_snapshot_data, request_stream_until_greeks

# --- configuration constants ---
from config import EXPORT_DIR, ENABLE_EMAIL_ALERT, ENABLE_TELEGRAM_ALERT


# ==================================================
# Runtime settings
# ==================================================
FAST_MODE = False
MAX_RUNTIME_SECONDS = 600     # 10-minute safety cap
POST_SNAPSHOT_WAIT = 15       # wait after requesting all snapshots
MAX_RETRY_ATTEMPTS = 2        # number of snapshot retries
RETRY_WAIT = 10               # seconds between retries


# ==================================================
# Utility: time format
# ==================================================
def _ts(start):
    """Format elapsed runtime as mm:ss string."""
    secs = time.time() - start
    m, s = divmod(int(secs), 60)
    return f"{m:02d}:{s:02d}s"


# ==================================================
# Wait for Greeks and retry logic
# ==================================================
def wait_for_greeks(app):
    """Wait for IB to deliver all option Greeks, retry missing ones."""
    logging.info(f"🕐 Waiting {POST_SNAPSHOT_WAIT}s for Greeks to settle...")
    time.sleep(POST_SNAPSHOT_WAIT)

    for attempt in range(1, MAX_RETRY_ATTEMPTS + 1):
        missing = [
            rid for rid, data in app.market_data.items()
            if not all(k in data and data[k] is not None
                       for k in ("Delta", "Gamma", "Vega", "Theta"))
        ]

        if not missing:
            logging.info("✅ All Greeks received successfully.")
            return True

        logging.warning(f"⚠️ Attempt {attempt}: {len(missing)} contracts still missing Greeks. Retrying...")

        # Re-request missing snapshots
        for rid in missing:
            conid = app.reqid_to_conid.get(rid)
            contract = app.conid_to_contract.get(conid)
            if not contract:
                continue
            new_id = app.nextReqId
            app.nextReqId += 1
            request_snapshot_data(app, contract, new_id)

        logging.info(f"🕐 Waiting {RETRY_WAIT}s after retry {attempt}...")
        time.sleep(RETRY_WAIT)

    logging.error("❌ Some contracts still missing Greeks after all retries.")
    return False


# ==================================================
# Main workflow
# ==================================================
def fetch_and_export_es_options():
    """
    Full pipeline:
    1. Connect to IB
    2. Fetch positions
    3. Collect snapshot data
    4. Wait/retry Greeks
    5. Streaming fallback for missing Greeks
    6. Compute PnL, exposures, and export
    """
    t0 = time.time()
    deadline = t0 + MAX_RUNTIME_SECONDS
    print(f"🚀 Starting ES options snapshot | Max runtime: {MAX_RUNTIME_SECONDS}s")

    # ---- connect ----
    app = connect_ib_client()
    print(f"[{_ts(t0)}] ✅ Connected to IB Gateway/TWS")

    # ---- fetch positions ----
    df_pos = fetch_es_positions(app)
    if df_pos.empty:
        print(f"[{_ts(t0)}] ℹ️ No ES options positions detected.")
        app.disconnect()
        return None
    print(f"[{_ts(t0)}] 📦 Positions fetched: {len(df_pos)}")

    # ---- request market data ----
    df_md = collect_market_data(app, df_pos, fast=FAST_MODE, deadline=deadline)
    print(f"[{_ts(t0)}] 📡 Market data collection started...")

    # ---- wait & retry ----
    wait_for_greeks(app)

    # ---- streaming fallback ----
    still_missing = [
        rid for rid, data in app.market_data.items()
        if not all(k in data and data[k] is not None for k in ("Delta", "Gamma", "Vega", "Theta"))
    ]
    if still_missing:
        logging.warning(f"🛟 Streaming fallback for {len(still_missing)} contracts missing Greeks...")
        fixed = 0
        for old_rid in still_missing:
            conid = app.reqid_to_conid.get(old_rid)
            contract = app.conid_to_contract.get(conid)
            if not contract:
                continue
            new_id = app.nextReqId
            app.nextReqId += 1
            ok = request_stream_until_greeks(app, contract, new_id)
            fixed += int(ok)
        logging.info(f"🧩 Streaming fallback fixed {fixed}/{len(still_missing)} contracts.")

    # ---- enrich & compute exposures ----
    df_md = enrich_with_pnl(app, df_md, fast=FAST_MODE)
    print(f"[{_ts(t0)}] 💰 PnL computed.")

    df_md = compute_exposures(df_md)
    print(f"[{_ts(t0)}] 🧮 Exposures computed.")

    df_final = finalize_dataframe(df_md)
    print(f"[{_ts(t0)}] 🧹 Dataframe finalized: {len(df_final)} rows.")

    # ---- export & alerts ----
    os.makedirs(EXPORT_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    out_path = export_portfolio(df_final, EXPORT_DIR, timestamp)
    send_alerts(df_final, out_path, ENABLE_EMAIL_ALERT, ENABLE_TELEGRAM_ALERT)

    try:
        app.disconnect()
    except Exception:
        pass

    print(f"[{_ts(t0)}] ✅ Snapshot exported: {out_path}")
    return out_path


# ==================================================
# Entry point
# ==================================================
if __name__ == "__main__":
    fetch_and_export_es_options()
