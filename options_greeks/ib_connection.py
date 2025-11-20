from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
import threading
import time
import logging

# ==================================================
# Logging setup
# ==================================================
logging.basicConfig(
    format='%(asctime)s | %(levelname)s | %(message)s',
    level=logging.INFO
)

# ==================================================
# IB Client/Wrapper
# ==================================================
class IBExporter(EWrapper, EClient):

    def __init__(self):
        EClient.__init__(self, self)

        # Internal state
        self.positions_data = []
        self.market_data = {}
        self.data_source = {}
        self.nextReqId = 1

        # Position sync
        self.positions_done = False
        self.positions_event = threading.Event()

        # Error tracking
        self.last_error = None

        # Account & PnL
        self.account = None
        self.pnl_by_conid = {}
        self._pnl_reqid_to_conid = {}
        self._next_pnl_req_id = 900000

        # Contract mappings for readable logs
        self.reqid_to_conid = {}
        self.conid_to_contract = {}

    # ==================================================
    # Error Handling
    # ==================================================
    def error(self, reqId, errorCode, errorString, advancedOrderRejectJson=''):
        msg = f"IB Error [reqId={reqId}, code={errorCode}]: {errorString}"
        logging.error(msg)
        self.last_error = (reqId, errorCode, errorString)

    # ==================================================
    # Account Management
    # ==================================================
    def managedAccounts(self, accountsList: str):
        accounts = [a.strip() for a in accountsList.split(",") if a.strip()]
        if accounts:
            self.account = accounts[0]
            logging.info(f"✅ Using account: {self.account}")
        else:
            logging.warning("⚠️ managedAccounts returned no accounts.")

    # ==================================================
    # Position Data
    # ==================================================
    def position(self, account, contract, position, avgCost):
        self.positions_data.append({
            "Account": account,
            "Symbol": contract.symbol,
            "SecType": contract.secType,
            "Currency": contract.currency,
            "Position": position,
            "Avg Price": avgCost / float(contract.multiplier or 50),
            "Strike": contract.strike,
            "Right": contract.right,
            "Expiration": contract.lastTradeDateOrContractMonth,
            "Instrument": contract.localSymbol,
            "TradingClass": contract.tradingClass,
            "Multiplier": contract.multiplier,
            "ConId": getattr(contract, "conId", None)
        })

    def positionEnd(self):
        logging.info("✅ Positions received.")
        self.positions_done = True
        self.positions_event.set()

    def wait_for_positions(self, timeout: float = 10.0):
        result = self.positions_event.wait(timeout=timeout)
        if not result:
            logging.warning("⚠️ Timeout waiting for position data.")
        return result

    # ==================================================
    # Market Data & Greeks
    # ==================================================
    def tickPrice(self, reqId, tickType, price, attrib):
        if reqId not in self.market_data:
            self.market_data[reqId] = {}
        if tickType == 1:
            self.market_data[reqId]["Bid"] = price
        elif tickType == 2:
            self.market_data[reqId]["Ask"] = price
        elif tickType == 4:
            self.market_data[reqId]["Last"] = price

    def tickOptionComputation(self, reqId, tickType, tickAttrib,
                              impliedVol, delta, optPrice,
                              pvDividend, gamma, vega, theta, undPrice):
        if reqId not in self.market_data:
            self.market_data[reqId] = {}

        def val(v):
            if v in (-1, -2, float('inf'), float('-inf')):
                return None
            return v

        self.market_data[reqId].update({
            "Delta": val(delta),
            "Gamma": val(gamma),
            "Vega": val(vega),
            "Theta": val(theta),
            "ImpliedVol": val(impliedVol)
        })

        # Friendly logging with symbol context
        conid = self.reqid_to_conid.get(reqId)
        contract = self.conid_to_contract.get(conid)
        sym = contract.localSymbol if contract else f"reqId={reqId}"

        logging.info(
            f"📈 {sym}: Δ={delta}, Γ={gamma}, Vega={vega}, Θ={theta}, IV={impliedVol}"
        )

    def tickSnapshotEnd(self, reqId):
        conid = self.reqid_to_conid.get(reqId)
        contract = self.conid_to_contract.get(conid)
        sym = contract.localSymbol if contract else f"reqId={reqId}"
        logging.info(f"📸 Snapshot completed for {sym}")

    # ==================================================
    # PnL Tracking
    # ==================================================
    def pnlSingle(self, reqId, pos, dailyPnL, unrealizedPnL, realizedPnL, value):
        conId = self._pnl_reqid_to_conid.get(reqId)
        if conId is None:
            logging.debug(f"pnlSingle received for unknown reqId={reqId}")
            return
        self.pnl_by_conid[conId] = {
            "daily": dailyPnL,
            "unrealized": unrealizedPnL,
            "realized": realizedPnL,
            "value": value
        }

    def pnlSingleEnd(self, reqId):
        logging.debug(f"pnlSingleEnd for reqId={reqId}")

    def req_pnl_for_conid(self, conId: int):
        if not self.account:
            logging.warning("⚠️ No account set yet; cannot request PnL.")
            return None
        req_id = self._next_pnl_req_id
        self._next_pnl_req_id += 1
        self._pnl_reqid_to_conid[req_id] = int(conId)
        self.reqPnLSingle(req_id, self.account, "", int(conId))
        return req_id


# ==================================================
# Helpers
# ==================================================
def run_loop(app):
    app.run()


def build_es_option_contract(row):
    c = Contract()
    c.symbol = "ES"
    c.secType = "FOP"
    c.exchange = "CME"
    c.currency = "USD"
    c.lastTradeDateOrContractMonth = str(row.get("Expiration", ""))
    c.strike = float(row.get("Strike", 0.0))
    c.right = str(row.get("Right", "")).upper()
    c.tradingClass = row.get("TradingClass", "")
    c.localSymbol = row.get("Instrument", "")
    c.multiplier = str(row.get("Multiplier", "50"))
    return c


# ==================================================
# Market Data Request (Improved)
# ==================================================
MAX_REQUESTS_PER_SECOND = 40
MIN_DELAY_BETWEEN_REQUESTS = 0.30
POST_SNAPSHOT_WAIT = 12
MAX_RETRY_ATTEMPTS = 2

def request_snapshot_data(app, contract, reqId):
    """Request market data snapshot for one option with throttling and retry."""
    try:
        conId = getattr(contract, "conId", None)
        if conId:
            app.conid_to_contract[conId] = contract
            app.reqid_to_conid[reqId] = conId

        logging.info(f"📷 Requesting snapshot for {contract.localSymbol} (reqId={reqId})")
        # 100=Greeks, 101=model prices, 106=open interest
        app.reqMktData(reqId, contract, "100,101,106", True, False, [])
        app.data_source[reqId] = "Snapshot"

        # Throttle requests
        time.sleep(MIN_DELAY_BETWEEN_REQUESTS)

    except Exception as e:
        logging.error(f"⚠️ Snapshot request failed for {contract.localSymbol}: {e}")

STREAM_FALLBACK_WAIT = 8      # seconds to wait for streaming greeks
STREAM_POLL_INTERVAL = 0.25   # seconds between checks

def request_stream_until_greeks(app, contract, reqId,
                                generic_ticks="100,101,106",
                                max_wait=STREAM_FALLBACK_WAIT):
    """
    Open a short streaming subscription for a single contract and wait
    until Greeks arrive, then cancel the stream. Returns True if Greeks arrived.
    """
    try:
        conId = getattr(contract, "conId", None)
        if conId:
            app.conid_to_contract[conId] = contract
            app.reqid_to_conid[reqId] = conId

        logging.info(f"🔁 Streaming fallback for {contract.localSymbol} (reqId={reqId})")
        app.reqMktData(reqId, contract, generic_ticks, False, False, [])

        # wait for greeks to land
        elapsed = 0.0
        while elapsed < max_wait:
            data = app.market_data.get(reqId, {})
            if all(k in data and data[k] is not None for k in ("Delta", "Gamma", "Vega", "Theta")):
                logging.info(f"✅ Streaming greeks received for {contract.localSymbol}")
                break
            time.sleep(STREAM_POLL_INTERVAL)
            elapsed += STREAM_POLL_INTERVAL

        # cancel streaming regardless
        try:
            app.cancelMktData(reqId)
        except Exception:
            pass

        data = app.market_data.get(reqId, {})
        return all(k in data and data[k] is not None for k in ("Delta", "Gamma", "Vega", "Theta"))

    except Exception as e:
        logging.error(f"⚠️ Streaming fallback failed for {getattr(contract, 'localSymbol', '?')}: {e}")
        return False
