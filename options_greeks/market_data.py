import time
import pandas as pd
from ib_connection import build_es_option_contract, request_snapshot_data

GENERIC_TICKS = "100,101,104,105,106,233"


def _before_deadline(deadline):
    return (deadline is None) or (time.time() < deadline)


def collect_market_data(app, df_positions, fast=False, deadline=None):
    """Requests live/frozen data + snapshot backfills, waits for Greeks safely."""
    REQ_PAUSE = 0.25
    LIVE_WAIT = 5
    FROZEN_WAIT = 15
    SNAP_WAIT = 10
    CHECK_INTERVAL = 2
    MAX_WAIT_SECONDS = 120  # per Greek batch

    req_ids, results = {}, []

    # prefer live
    app.reqMarketDataType(1)
    for i, row in df_positions.iterrows():
        if not _before_deadline(deadline):
            break
        c = build_es_option_contract(row)
        rid = app.nextReqId
        app.nextReqId += 1
        try:
            app.reqMktData(rid, c, GENERIC_TICKS, False, False, [])
            req_ids[i] = [rid]
        except Exception as e:
            print(f"⚠️ reqMktData failed for row {i}: {e}")
        time.sleep(REQ_PAUSE)

    time.sleep(LIVE_WAIT)

    if not any(app.market_data.values()):
        app.reqMarketDataType(2)
        print("⚠️ No live ticks detected — switched to FROZEN data.")
    time.sleep(FROZEN_WAIT)

    # ---- Wait loop for Greeks ----
    t_start = time.time()
    while time.time() - t_start < MAX_WAIT_SECONDS and _before_deadline(deadline):
        completed = 0
        for i, row in df_positions.iterrows():
            tick = {}
            for rid in req_ids.get(i, []):
                tick.update(app.market_data.get(rid, {}))
            if all(k in tick for k in ("Delta", "Gamma", "Vega", "Theta")):
                completed += 1
        print(f"⏳ Greeks completion: {completed}/{len(df_positions)}", end="\r")
        if completed >= len(df_positions):
            break
        time.sleep(CHECK_INTERVAL)

    # ---- Snapshot backfill ----
    for i, row in df_positions.iterrows():
        if not _before_deadline(deadline):
            break
        have = {}
        for rid in req_ids.get(i, []):
            have.update(app.market_data.get(rid, {}))
        if not all(k in have for k in ("Delta", "Gamma", "Vega", "Theta")):
            snap_id = app.nextReqId
            app.nextReqId += 1
            try:
                request_snapshot_data(app, build_es_option_contract(row), snap_id)
                req_ids.setdefault(i, []).append(snap_id)
            except Exception as e:
                print(f"⚠️ Snapshot request failed for row {i}: {e}")
            time.sleep(REQ_PAUSE)
    time.sleep(SNAP_WAIT)

    # ---- Merge results ----
    for i, row in df_positions.iterrows():
        tick = {}
        for rid in req_ids.get(i, []):
            tick.update(app.market_data.get(rid, {}))
        results.append({**row, **tick})
    df = pd.DataFrame(results)

    for col in ("Bid", "Ask", "Last", "Delta", "Gamma", "Vega", "Theta"):
        if col not in df.columns:
            df[col] = pd.NA

    print(f"\n✅ Market data fetch complete ({len(df)} rows)")
    return df
