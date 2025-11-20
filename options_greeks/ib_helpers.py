import time
import pandas as pd
import threading
from ib_connection import IBExporter, run_loop


def connect_ib_client(host="127.0.0.1", port=7496):
    """Establish and validate connection to IB."""
    app = IBExporter()
    app.connect(host, port, clientId=int(time.time()) % 10000)
    threading.Thread(target=run_loop, args=(app,), daemon=True).start()

    for _ in range(50):
        if app.isConnected():
            return app
        time.sleep(0.1)
    raise ConnectionError("❌ IB not connected.")


def fetch_es_positions(app):
    """Fetch ES options positions."""
    app.reqPositions()
    app.wait_for_positions(10.0)
    df = pd.DataFrame(app.positions_data)
    if df.empty:
        return df
    return df[(df["Symbol"] == "ES") & (df["SecType"] == "FOP")].copy()
