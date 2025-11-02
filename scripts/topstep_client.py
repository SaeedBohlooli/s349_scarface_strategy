# file: topstep_client.py
import os
import csv
import json
import uuid
import time
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Union, Tuple
import requests
import yaml
import logging
import math
from dataclasses import dataclass

from utils.email_util_ver_02 import send_email

# --------------------------------------------------------------------------------------
# Paths & Config (UNCHANGED)
# --------------------------------------------------------------------------------------
EMAIL = "vikaskaler.bnr@gmail.com"
SCRIPT_DIR = os.path.dirname(__file__)
CONFIG_PATH = os.path.join(SCRIPT_DIR, "configs", "topstep-config.yaml")
# Where we keep dated CSVs by default (…/portfolios/topstep/YYYY-MM-DD/*.csv)
PORTFOLIO_PATH = os.path.join(os.path.dirname(__file__), "..", "portfolios/topstep")

# --------------------------------------------------------------------------------------
# Logging (existing style preserved)
# --------------------------------------------------------------------------------------
logging_level = 'INFO'
logging.basicConfig(level=logging_level, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------------------
# Exceptions (UNCHANGED)
# --------------------------------------------------------------------------------------
class TopstepConfigError(RuntimeError):
    ...
class TopstepApiError(RuntimeError):
    ...
class TopstepPayloadError(RuntimeError):
    ...

# --------------------------------------------------------------------------------------
# CSV Helpers (UNCHANGED)
# --------------------------------------------------------------------------------------
def dated_csv_path(base_dir: Union[str, Path], filename: str) -> Path:
    """Build a dated CSV path like base_dir/YYYY-MM-DD/filename and ensure directory exists."""
    date_str = datetime.now().strftime("%Y-%m-%d")
    path = Path(base_dir) / date_str / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    return path

def append_to_csv(
    csv_path: Union[str, Path],
    data: Union[Dict[str, Any], List[Dict[str, Any]]],
    add_timestamp: bool = True,
) -> Path:
    """
    Generic CSV logger — creates or appends to a CSV dynamically.
    """
    path = Path(csv_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    rows = [data] if isinstance(data, dict) else data
    if not rows:
        return path

    if add_timestamp:
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        for row in rows:
            row.setdefault("ts_utc", now)

    existing_fields: List[str] = []
    if path.exists():
        try:
            with path.open("r", newline="", encoding="utf-8") as f:
                reader = csv.reader(f)
                existing_fields = next(reader, [])
        except Exception:
            pass

    new_fields = set(existing_fields)
    for r in rows:
        new_fields.update(r.keys())
    fieldnames = list(new_fields)

    write_header = not path.exists() or set(fieldnames) != set(existing_fields)
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        for r in rows:
            safe_row = {k: r.get(k, "") for k in fieldnames}
            writer.writerow(safe_row)

    return path

# --------------------------------------------------------------------------------------
# Config & Utilities (UNCHANGED except tiny default additions at end)
# --------------------------------------------------------------------------------------
def load_config(path: str = CONFIG_PATH) -> Dict[str, Any]:
    """Load YAML config and normalize required fields."""
    with open(path, "r") as f:
        cfg = yaml.safe_load(f) or {}

    required = ["token", "user_id", "account_ids", "number_of_cons", "symbol_id"]
    miss = [k for k in required if k not in cfg or cfg[k] in (None, "", [])]
    if miss:
        raise TopstepConfigError(f"Missing required in {path}: {', '.join(miss)}")

    if not isinstance(cfg["account_ids"], list):
        raise TopstepConfigError("account_ids must be a list of ints.")

    try:
        cfg["number_of_cons"] = int(cfg["number_of_cons"])
    except Exception as e:
        raise TopstepConfigError("number_of_cons must be an integer.") from e

    # defaults for optional notifications (non-breaking; used by polling tick)
    n = cfg.setdefault("notifications", {})
    n.setdefault("email_to", EMAIL)
    n.setdefault("poll_interval", 20)

    return cfg

def _symbol_params(cfg: Dict[str, Any], symbol_id: str) -> Tuple[float, float]:
    """
    Read per-symbol SL/TP (points) from config.
      "F.US.MNQ":
        stop_loss: 30
        take_profit: 50
    """
    sym_cfg = cfg.get(symbol_id) or {}
    sl_pts = float(sym_cfg.get("stop_loss", 0))
    tp_pts = float(sym_cfg.get("take_profit", 0))
    if sl_pts <= 0 or tp_pts <= 0:
        raise TopstepConfigError(
            f"Missing/invalid stop_loss or take_profit for {symbol_id} in config."
        )
    return sl_pts, tp_pts

def _calc_sl_tp_from_avg(avg_price: float, side: str, sl_pts: float, tp_pts: float) -> Tuple[float, float]:
    s = side.strip().lower()
    if s in ("long", "buy", "bid"):
        return round(avg_price - sl_pts, 6), round(avg_price + tp_pts, 6)
    elif s in ("short", "sell", "ask"):
        return round(avg_price + sl_pts, 6), round(avg_price - tp_pts, 6)
    else:
        raise TopstepPayloadError("side must be 'long'|'short' (aliases: buy/bid, sell/ask).")

def _find_position_for_account(
    positions: List[Dict[str, Any]],
    *,
    account_id: int,
    symbol_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    if symbol_id:
        candidates = [
            p for p in positions
            if p.get("accountId") == account_id and p.get("symbolId") == symbol_id
        ]
    else:
        candidates = [p for p in positions if p.get("accountId") == account_id]
    if not candidates:
        return None
    try:
        candidates.sort(key=lambda p: p.get("entryTime", ""), reverse=True)
    except Exception:
        pass
    return candidates[0]

# --------------------------------------------------------------------------------------
# HTTP Helpers / Endpoints (UNCHANGED)
# --------------------------------------------------------------------------------------
ORDER_TYPES: Dict[str, int] = {
    "limit": 1,
    "market": 2,
    "stop": 4,
    "trailingstop": 5,
    "joinbid": 6,
    "join_ bid": 6,
    "join-bid": 6,
    "joinask": 7,
    "join_ ask": 7,
    "join-ask": 7,
}

def _normalize_order_type(order_type: Union[int, str]) -> int:
    if isinstance(order_type, int):
        if order_type in (1, 2, 4, 5, 6, 7):
            return order_type
        raise TopstepPayloadError(f"Unsupported order_type code: {order_type}")
    s = str(order_type).strip().lower().replace("__", "_").replace("-", "").replace(" ", "").replace("_", "")
    if s in ORDER_TYPES:
        return ORDER_TYPES[s]
    raise TopstepPayloadError(
        f"Unsupported order_type: {order_type} "
        f"(use one of: limit, market, stop, trailingStop, joinBid, joinAsk or codes 1/2/4/5/6/7)"
    )

def _validate_prices(t: int, limit_price: Optional[float], stop_price: Optional[float]) -> None:
    if t == 1 and limit_price is None:
        raise TopstepPayloadError("Limit order requires limit_price.")
    if t == 4 and stop_price is None:
        raise TopstepPayloadError("Stop order requires stop_price.")
    if t == 5 and stop_price is None:
        raise TopstepPayloadError("TrailingStop typically requires stop_price.")
    if t in (2, 6, 7) and (limit_price is not None or stop_price is not None):
        raise TopstepPayloadError("Market/JoinBid/JoinAsk should not include limit_price/stop_price.")

def _payload(
    *,
    side: str,
    account_id: int,
    symbol_id: str,
    qty: int,
    order_type: Union[int, str],
    time_type: int = 0,
    limit_price: Optional[float] = None,
    stop_price: Optional[float] = None,
) -> Dict[str, Any]:
    t = _normalize_order_type(order_type)
    s = side.strip().lower()

    if t == 6 and s not in ("long", "buy", "bid"):
        raise TopstepPayloadError("JoinBid (type=6) expects side='long'/'buy'.")
    if t == 7 and s not in ("short", "sell", "ask"):
        raise TopstepPayloadError("JoinAsk (type=7) expects side='short'/'sell'.")

    position_size = qty if s in ("long", "buy", "bid") else -qty
    _validate_prices(t, limit_price, stop_price)

    body: Dict[str, Any] = {
        "accountId": int(account_id),
        "symbolId": symbol_id,
        "type": t,
        "positionSize": position_size,
        "timeType": time_type,
        "customTag": str(uuid.uuid4()),
    }
    if t == 1 and limit_price is not None:
        body["limitPrice"] = float(limit_price)
    if t in (4, 5) and stop_price is not None:
        body["stopPrice"] = float(stop_price)
    return body

def _resolve_order_type_for_side(
    cfg: Dict[str, Any],
    symbol_id: str,
    side: str,
    explicit: Optional[Union[int, str]] = None,
) -> int:
    if explicit is not None:
        return _normalize_order_type(explicit)
    sym_cfg = cfg.get(symbol_id) or {}
    ot = sym_cfg.get("order_type")
    if ot:
        return _normalize_order_type(ot)
    s = side.strip().lower()
    return 6 if s in ("long", "buy", "bid") else 7  # joinBid / joinAsk

def get_positions(
    *,
    user_id: Optional[int] = None,
    contract_name: Optional[str] = None,
    cfg_path: str = CONFIG_PATH,
    base_url: str = "https://userapi.topstepx.com/Position/all/user",
    timeout: float = 10.0,
    add_app_headers: bool = False,
    dry_run: bool = False,
) -> List[Dict[str, Any]]:
    """
    Fetch open positions for a given user (TopstepX).
    If contract_name is provided, filter by symbolId/symbolName/contractId.
    """
    cfg = load_config(cfg_path)
    token = cfg["token"]
    uid = user_id or cfg.get("user_id")
    if not uid:
        raise TopstepConfigError("user_id not provided and not found in config file.")

    url = f"{base_url}/{uid}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    if add_app_headers:
        headers["x-app-type"] = cfg.get("x_app_type", "px-desktop")
        headers["x-app-version"] = cfg.get("x_app_version", "1.22.19")

    if dry_run:
        logger.info(f"[DRY RUN] GET {url}\nHeaders: {headers}\n")
        return []

    resp = requests.get(url, headers=headers, timeout=timeout)
    if not resp.ok:
        raise TopstepApiError(
            f"get_positions(user_id={uid}) failed (HTTP {resp.status_code}) -> {resp.text[:500]}"
        )

    try:
        data = resp.json()
    except Exception as e:
        raise TopstepApiError(f"Failed to parse JSON from positions API: {e}")

    positions = data
    if contract_name:
        cname = contract_name.strip().lower()
        positions = [
            p for p in data
            if cname in (str(p.get("symbolId", "")).lower(),
                         str(p.get("symbolName", "")).lower(),
                         str(p.get("contractId", "")).lower())
               or cname in str(p.get("symbolId", "")).lower()
               or cname in str(p.get("contractId", "")).lower()
        ]

    # IMPORTANT: removed per-position email here (per your request).
    return positions

def edit_stop_loss_account(
    *,
    tradingAccountId: int,
    positionId: int,
    stopLoss: float,
    takeProfit: float,
    timeType: int = 0,
    cfg_path: str = CONFIG_PATH,
    base_url: str = "https://userapi.topstepx.com/Order/editStopLossAccount",
    timeout: float = 10.0,
    add_app_headers: bool = False,
    dry_run: bool = False,
) -> Dict[str, Any]:
    cfg = load_config(cfg_path)
    token = cfg["token"]

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    if add_app_headers:
        headers["x-app-type"] = cfg.get("x_app_type", "px-desktop")
        headers["x-app-version"] = cfg.get("x_app_version", "1.22.19")

    payload = {
        "tradingAccountId": int(tradingAccountId),
        "positionId": int(positionId),
        "stopLoss": float(stopLoss),
        "takeProfit": float(takeProfit),
        "timeType": int(timeType),
    }

    if dry_run:
        logger.info(f"[DRY RUN] POST {base_url}\nHeaders: {headers}\nBody: {json.dumps(payload)}\n")
        return {"dryRun": True, "url": base_url, "payload": payload}

    resp = requests.post(base_url, headers=headers, json=payload, timeout=timeout)

    try:
        body = resp.json()
    except Exception:
        body = {"raw_text": (resp.text or "").strip()}

    if not resp.ok:
        raise TopstepApiError(
            f"edit_stop_loss_account failed (HTTP {resp.status_code}) -> {str(body)[:500]}"
        )

    return body

def flat_account(
    account_id: int,
    *,
    cfg_path: str = CONFIG_PATH,
    base_url: str = "https://userapi.topstepx.com/Position/close",
    timeout: float = 10.0,
    add_app_headers: bool = False,
    dry_run: bool = False,
) -> Dict[str, Any]:
    cfg = load_config(cfg_path)
    token = cfg["token"]

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    if add_app_headers:
        headers["x-app-type"] = cfg.get("x_app_type", "px-desktop")
        headers["x-app-version"] = cfg.get("x_app_version", "1.22.19")

    url = f"{base_url}/{account_id}"

    if dry_run:
        logger.info(f"[DRY RUN] DELETE {url}\nHeaders: {headers}\n")
        return {"accountId": account_id, "dryRun": True, "url": url}

    resp = requests.delete(url, headers=headers, timeout=timeout)
    result = {
        "accountId": account_id,
        "status_code": resp.status_code,
        "ok": resp.ok,
        "text": (resp.text or "").strip(),
    }
    if resp.text.strip():
        try:
            result["json"] = resp.json()
        except Exception:
            pass

    if not resp.ok:
        raise TopstepApiError(
            f"flat_account({account_id}) failed (HTTP {resp.status_code}) -> {resp.text[:500]}"
        )

    if resp.status_code == 200 and not resp.text.strip():
        result["message"] = "Flatten request accepted (200 OK, empty body)."

    return result

def flat_all(
    *,
    cfg_path: str = CONFIG_PATH,
    base_url: str = "https://userapi.topstepx.com/Position/close",
    timeout: float = 10.0,
    add_app_headers: bool = False,
    dry_run: bool = False,
) -> List[Dict[str, Any]]:
    cfg = load_config(cfg_path)
    account_ids = cfg.get("account_ids", [])
    if not account_ids:
        raise TopstepConfigError(f"No account_ids found in {cfg_path}")

    logger.info(f"\nFlattening all {len(account_ids)} accounts...")

    results: List[Dict[str, Any]] = []
    for i, acc_id in enumerate(account_ids, 1):
        logger.info(f" → [{i}/{len(account_ids)}] Flattening account {acc_id}...")
        try:
            res = flat_account(
                account_id=acc_id,
                cfg_path=cfg_path,
                base_url=base_url,
                timeout=timeout,
                add_app_headers=add_app_headers,
                dry_run=dry_run,
            )
            results.append(res)
            if res.get("ok"):
                logger.info(f"    ✅ Account {acc_id} flattened (HTTP {res['status_code']})")
            else:
                logger.info(f"    ⚠️  Account {acc_id} returned status {res['status_code']}")
        except Exception as e:
            logger.info(f"    ❌ Failed to flatten {acc_id}: {e}")
            results.append({"accountId": acc_id, "error": str(e)})

    logger.info("\nAll flatten requests processed.\n")
    return results

# --------------------------------------------------------------------------------------
# SEND ORDER (UNCHANGED signature/behavior)
# --------------------------------------------------------------------------------------
def has_open_position(
    account_id: int,
    *,
    symbol_id: Optional[str] = None,
    cfg_path: str = CONFIG_PATH,
    add_app_headers: bool = False,
) -> bool:
    cfg = load_config(cfg_path)
    user_id = cfg["user_id"]
    positions = get_positions(user_id=user_id, cfg_path=cfg_path, add_app_headers=add_app_headers)
    pos = _find_position_for_account(positions, account_id=account_id, symbol_id=symbol_id)
    return pos is not None

def send_order(
    *,
    side: str,
    order_type: Union[int, str],
    cfg_path: str = CONFIG_PATH,
    account_id: Optional[int] = None,
    base_url: str = "https://userapi.topstepx.com/Order",
    timeout: float = 10.0,
    add_app_headers: bool = False,
    time_type: int = 0,
    limit_price: Optional[float] = None,
    stop_price: Optional[float] = None,
    dry_run: bool = False,
    fail_fast: bool = False,
    skip_if_open: bool = True,
    check_symbol_only: bool = True,
) -> List[Dict[str, Any]]:
    cfg = load_config(cfg_path)
    token = cfg["token"]
    symbol_id = cfg["symbol_id"]
    qty = cfg["number_of_cons"]
    accounts: Sequence[int] = [account_id] if account_id else cfg["account_ids"]

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    if add_app_headers:
        headers["x-app-type"] = cfg.get("x_app_type", "px-desktop")
        headers["x-app-version"] = cfg.get("x_app_version", "1.22.19")

    session = requests.Session()
    results: List[Dict[str, Any]] = []

    total = len(accounts)
    logger.info(f"\nSending order to {total} account(s): side={side}, type={order_type}, symbol={symbol_id}, qty={qty}")

    for idx, acc in enumerate(accounts, 1):
        logger.info(f" → [{idx}/{total}] account {acc} ...")

        if skip_if_open:
            already_open = has_open_position(
                acc,
                symbol_id=symbol_id if check_symbol_only else None,
                cfg_path=cfg_path,
                add_app_headers=add_app_headers,
            )
            if already_open:
                logger.info(" ⏭️  skipped (open position exists)")
                skip_info = {
                    "accountId": acc,
                    "skipped": True,
                    "reason": "open_position_exists",
                    "symbol_scoped": check_symbol_only,
                    "symbolId": symbol_id,
                }
                results.append(skip_info)
                append_to_csv(dated_csv_path(PORTFOLIO_PATH, "order_skips.csv"), skip_info)
                continue

        try:
            body = _payload(
                side=side,
                account_id=acc,
                symbol_id=symbol_id,
                qty=qty,
                order_type=order_type,
                time_type=time_type,
                limit_price=limit_price,
                stop_price=stop_price,
            )

            if dry_run:
                logger.info(" DRY RUN")
                logger.info(f"    POST {base_url}")
                logger.info(f"    Headers: {headers}")
                logger.info(f"    Body: {json.dumps(body)}")
                results.append({"accountId": acc, "dryRun": True, "payload": body})
                continue

            resp = session.post(base_url, headers=headers, json=body, timeout=timeout)
            item = {
                "accountId": acc,
                "status_code": resp.status_code,
                "ok": resp.ok,
                "text": (resp.text or "").strip(),
            }
            try:
                if item["text"]:
                    item["json"] = resp.json()
            except Exception:
                pass

            results.append(item)
            if resp.ok:
                logger.info(f" ✅ (HTTP {resp.status_code})")
            else:
                logger.info(f" ⚠️  (HTTP {resp.status_code})")
                if fail_fast:
                    raise TopstepApiError(
                        f"send_order(side={side}, type={order_type}) failed for account {acc} "
                        f"(HTTP {resp.status_code}) -> {item['text'][:500]}"
                    )
        except Exception as e:
            logger.info(" ❌")
            err = {"accountId": acc, "error": str(e)}
            results.append(err)
            if fail_fast:
                raise

    logger.info("\nAll order requests processed.\n")
    return results

# --------------------------------------------------------------------------------------
# EMAIL FORMATTER (UNCHANGED)
# --------------------------------------------------------------------------------------
def format_position_email(p: Dict[str, Any], tz_name: str = "America/Toronto") -> Dict[str, str]:
    """
    Returns a dict: {event, subject, text, html}
    Case A (just opened): stopLoss and takeProfit are None
    Case B (final position): both present
    """
    symbol_id   = p.get("symbolId") or p.get("symbolName") or ""
    symbol_name = p.get("symbolName") or symbol_id
    account_id  = p.get("accountId")
    size        = p.get("positionSize", 0)
    avg_price   = p.get("averagePrice")
    sl          = p.get("stopLoss")
    tp          = p.get("takeProfit")
    pnl         = p.get("profitAndLoss")
    to_make     = p.get("toMake")
    risk        = p.get("risk")
    contract_id = p.get("contractId")
    entry_time  = p.get("entryTime")

    direction = "LONG" if (size or 0) > 0 else ("SHORT" if (size or 0) < 0 else "FLAT")

    try:
        dt_utc = datetime.fromisoformat((entry_time or "").replace("Z", "+00:00")) if entry_time else None
    except Exception:
        dt_utc = None
    pretty_time = entry_time
    try:
        if dt_utc:
            pretty_time = dt_utc.strftime("%Y-%m-%d %H:%M:%S UTC")
    except Exception:
        pass

    just_opened = (sl is None and tp is None)

    if just_opened:
        event   = "position_opened_no_sltp"
        subject = f"[Topstep] {symbol_name} {direction} x{abs(size)} opened (acct {account_id})"
        lead    = f"{symbol_name} {direction} position opened — SL/TP pending"
    else:
        event   = "position_final_with_sltp"
        subject = f"[Topstep] {symbol_name} {direction} x{abs(size)} finalized (SL/TP set)"
        lead    = f"{symbol_name} {direction} position finalized — SL/TP set"

    def f(x: Optional[float]) -> str:
        if x is None:
            return "—"
        if isinstance(x, (int, float)) and (math.isfinite(x)):
            s = f"{x:.6f}".rstrip("0").rstrip(".")
            return s
        return str(x)

    text_lines = [
        lead, "",
        f"Account:      {account_id}",
        f"Contract:     {contract_id or '—'}",
        f"Symbol:       {symbol_name} ({symbol_id})",
        f"Side:         {direction}",
        f"Size:         {size}",
        f"Avg Price:    {f(avg_price)}",
        f"Stop Loss:    {f(sl)}",
        f"Take Profit:  {f(tp)}",
        f"P&L:         {f(pnl)}",
        f"To Make:      {f(to_make)}",
        f"Risk:         {f(risk)}",
        f"Entry Time:   {pretty_time}",
    ]
    text = "\n".join(text_lines)

    html_rows = "".join([
        f"<tr><td><b>Account</b></td><td>{account_id}</td></tr>",
        f"<tr><td><b>Contract</b></td><td>{contract_id or '—'}</td></tr>",
        f"<tr><td><b>Symbol</b></td><td>{symbol_name} ({symbol_id})</td></tr>",
        f"<tr><td><b>Side</b></td><td>{direction}</td></tr>",
        f"<tr><td><b>Size</b></td><td>{size}</td></tr>",
        f"<tr><td><b>Avg Price</b></td><td>{f(avg_price)}</td></tr>",
        f"<tr><td><b>Stop Loss</b></td><td>{f(sl)}</td></tr>",
        f"<tr><td><b>Take Profit</b></td><td>{f(tp)}</td></tr>",
        f"<tr><td><b>P&amp;L</b></td><td>{f(pnl)}</td></tr>",
        f"<tr><td><b>To Make</b></td><td>{f(to_make)}</td></tr>",
        f"<tr><td><b>Risk</b></td><td>{f(risk)}</td></tr>",
        f"<tr><td><b>Entry Time</b></td><td>{pretty_time}</td></tr>",
    ])
    html = f"""
    <div>
      <p>{lead}</p>
      <table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;">
        {html_rows}
      </table>
    </div>
    """
    return {"event": event, "subject": subject, "text": text, "html": html}

# --------------------------------------------------------------------------------------
# NEW: In-memory state + tick helpers (ONLY for your asks)
# --------------------------------------------------------------------------------------
@dataclass
class _PosState:
    account_id: int
    position_id: int
    symbol_id: str
    had_sltp: bool

# positionId -> _PosState
_POS_MAP: Dict[int, _PosState] = {}
# accountId -> count of open positions (to know when account becomes flat)
_ACCT_OPEN_COUNTS: Dict[int, int] = {}

def _has_both_sltp(p: Dict[str, Any]) -> bool:
    return p.get("stopLoss") is not None and p.get("takeProfit") is not None

def _rebuild_account_counts(positions: List[Dict[str, Any]]) -> None:
    _ACCT_OPEN_COUNTS.clear()
    for p in positions:
        acc = int(p.get("accountId"))
        _ACCT_OPEN_COUNTS[acc] = _ACCT_OPEN_COUNTS.get(acc, 0) + 1

def _send_email(subject: str, html: str, cfg: Dict[str, Any]) -> None:
    to = (cfg.get("notifications") or {}).get("email_to") or EMAIL
    send_email(to_emails=to, subject=subject, body=html)

def process_positions_tick(*, cfg_path: str = CONFIG_PATH) -> None:
    """
    One 'tick' to be called by your worker every notifications.poll_interval seconds.

    - Maintains in-memory position map (_POS_MAP)
    - Sends email once when a position transitions to 'SL/TP set'
    - Detects when positions close; sends 'account flat' if no positions remain for an account
    """
    cfg = load_config(cfg_path)
    user_id = cfg["user_id"]

    positions = get_positions(user_id=user_id, cfg_path=cfg_path)
    # refresh account open counts
    _rebuild_account_counts(positions)

    live_ids = set()
    for p in positions:
        pid = int(p.get("id"))
        acc = int(p.get("accountId"))
        sym = str(p.get("symbolId") or p.get("symbolName") or "")
        has_now = _has_both_sltp(p)
        live_ids.add(pid)

        st = _POS_MAP.get(pid)
        if st is None:
            # first time seeing this pos in memory
            _POS_MAP[pid] = _PosState(account_id=acc, position_id=pid, symbol_id=sym, had_sltp=has_now)
            continue

        # transition: SL/TP became set -> send email ONCE
        if not st.had_sltp and has_now:
            payload = format_position_email(p)  # event=position_final_with_sltp
            try:
                _send_email(payload["subject"], payload["html"], cfg)
                append_to_csv(dated_csv_path(PORTFOLIO_PATH, "notifications.csv"), {
                    "event": "sltp_set",
                    "accountId": acc,
                    "positionId": pid,
                    "symbolId": sym
                })
                logger.info(f"📧 SL/TP-set email sent for pos {pid} (acct {acc})")
            except Exception as e:
                logger.warning(f"Email send failed for SL/TP-set pos {pid}: {e}")
        st.had_sltp = has_now

    # detect closures: anything in _POS_MAP not in live_ids
    closed_pids = [pid for pid in list(_POS_MAP.keys()) if pid not in live_ids]
    for pid in closed_pids:
        st = _POS_MAP.pop(pid, None)
        if not st:
            continue
        # decrement the account's open count, if it exists
        if st.account_id in _ACCT_OPEN_COUNTS:
            _ACCT_OPEN_COUNTS[st.account_id] = max(0, _ACCT_OPEN_COUNTS.get(st.account_id, 0) - 1)

        # If account has become flat (no positions), email “account flat”
        if _ACCT_OPEN_COUNTS.get(st.account_id, 0) == 0:
            subj = f"[Topstep] Account {st.account_id} is FLAT"
            html = f"<p>All positions closed for account <b>{st.account_id}</b>. Last closed: {st.symbol_id} (pos {pid}).</p>"
            try:
                _send_email(subj, html, cfg)
                append_to_csv(dated_csv_path(PORTFOLIO_PATH, "notifications.csv"), {
                    "event": "account_flat",
                    "accountId": st.account_id,
                    "last_positionId": pid,
                    "last_symbolId": st.symbol_id
                })
                logger.info(f"📧 account flat email sent (acct {st.account_id})")
            except Exception as e:
                logger.warning(f"Email send failed for account flat (acct {st.account_id}): {e}")

# --------------------------------------------------------------------------------------
# Full Orchestration (UNCHANGED public signature, ONLY adds: send email after SL/TP)
# --------------------------------------------------------------------------------------
def _poll_position_until_seen(
    *,
    user_id: int,
    account_id: int,
    symbol_id: str,
    interval_s: float = 0.5,
    max_wait_s: float = 5.0,
) -> Optional[Dict[str, Any]]:
    deadline = time.time() + max_wait_s
    while time.time() < deadline:
        pos = get_positions(user_id=user_id)
        match = _find_position_for_account(pos, account_id=account_id, symbol_id=symbol_id)
        if match:
            return match
        time.sleep(interval_s)
    return None

def topstep_order_execution(
    *,
    side: str,
    order_type: Optional[Union[int, str]] = None,
    account_id: Optional[int] = None,
    cfg_path: str = CONFIG_PATH,
    portfolio_dir: str = PORTFOLIO_PATH,
    add_app_headers: bool = False,
    poll_interval_s: float = 0.5,
    poll_timeout_s: float = 5.0,
) -> Dict[str, Any]:
    """
    Same flow as your base; ONE addition:
    - After SL/TP is successfully set, we send the SL/TP email **right there**.
    """
    cfg = load_config(cfg_path)
    symbol_id = cfg["symbol_id"]
    user_id = cfg.get("user_id")
    if not user_id:
        raise TopstepConfigError("user_id missing in config.")
    accounts = [account_id] if account_id else cfg["account_ids"]

    resolved_type = _resolve_order_type_for_side(cfg, symbol_id, side, explicit=order_type)

    order_results = send_order(
        side=side,
        order_type=resolved_type,
        cfg_path=cfg_path,
        account_id=account_id,
        add_app_headers=add_app_headers,
        dry_run=False,
        fail_fast=False,
        skip_if_open=True,
        check_symbol_only=True,
    )
    append_to_csv(dated_csv_path(portfolio_dir, "orders.csv"), order_results)

    summaries: List[Dict[str, Any]] = []
    try:
        sl_pts, tp_pts = _symbol_params(cfg, symbol_id)
    except Exception as e:
        reason = f"Cannot read stop_loss/take_profit for {symbol_id}: {e}"
        for acc in accounts:
            summaries.append({"accountId": acc, "ok": False, "phase": "pre_sltp", "reason": str(e)})
        append_to_csv(dated_csv_path(portfolio_dir, "operations.csv"), [
            {"side": side, "order_type": resolved_type, **s} for s in summaries
        ])
        return {"symbol": symbol_id, "side": side, "order_type": resolved_type, "summaries": summaries}

    skipped_accounts = {r.get("accountId") for r in order_results if r.get("skipped")}
    actionable_accounts = [a for a in accounts if a not in skipped_accounts]

    for acc in actionable_accounts:
        pos = _poll_position_until_seen(
            user_id=user_id,
            account_id=acc,
            symbol_id=symbol_id,
            interval_s=poll_interval_s,
            max_wait_s=poll_timeout_s,
        )
        if not pos:
            summaries.append({"accountId": acc, "ok": False, "phase": "poll_after_order", "reason": "no position observed"})
            continue

        append_to_csv(dated_csv_path(portfolio_dir, "positions_before_sltp.csv"), pos)

        try:
            avg = float(pos.get("averagePrice"))
            if not avg or avg <= 0:
                raise ValueError("averagePrice missing/invalid")
        except Exception as e:
            summaries.append({"accountId": acc, "ok": False, "phase": "avg_price", "reason": str(e)})
            continue

        try:
            stop_px, take_px = _calc_sl_tp_from_avg(avg, side, sl_pts, tp_pts)
        except Exception as e:
            summaries.append({"accountId": acc, "ok": False, "phase": "compute_sltp", "reason": str(e)})
            continue

        position_id = int(pos["id"])
        try:
            resp = edit_stop_loss_account(
                tradingAccountId=acc,
                positionId=position_id,
                stopLoss=stop_px,
                takeProfit=take_px,
                cfg_path=cfg_path,
                add_app_headers=add_app_headers,
            )
        except Exception as e:
            summaries.append({"accountId": acc, "ok": False, "phase": "edit_sltp", "reason": str(e)})
            continue

        append_to_csv(dated_csv_path(portfolio_dir, "sltp_updates.csv"), {
            **resp,
            "accountId": acc,
            "positionId": position_id,
            "computed_stopLoss": stop_px,
            "computed_takeProfit": take_px,
        })

        # === NEW: send email immediately after SL/TP set ===
        try:
            # refresh the single position to include SL/TP we just set
            pos_after = get_positions(user_id=user_id, contract_name=symbol_id)
            cur = _find_position_for_account(pos_after, account_id=acc, symbol_id=symbol_id) or pos
            payload = format_position_email(cur)  # this picks the "finalized (SL/TP set)" subject
            _send_email(payload["subject"], payload["html"], cfg)
            append_to_csv(dated_csv_path(portfolio_dir, "notifications.csv"), {
                "event": "sltp_set",
                "accountId": acc,
                "positionId": position_id,
                "symbolId": symbol_id
            })
            logger.info(f"📧 SL/TP-set email sent (acct {acc}, pos {position_id})")
        except Exception as e:
            logger.warning(f"Email send failed after SL/TP set (acct {acc}, pos {position_id}): {e}")

        summaries.append({
            "accountId": acc,
            "positionId": position_id,
            "avg_price": avg,
            "stopLoss_set": stop_px,
            "takeProfit_set": take_px,
            "validated": True,  # we emailed right after setting; validation step kept simple
        })

    for acc in skipped_accounts:
        summaries.append({
            "accountId": acc,
            "skipped": True,
            "reason": "open_position_exists",
            "validated": False,
        })

    append_to_csv(dated_csv_path(portfolio_dir, "operations.csv"), [
        {"side": side, "order_type": resolved_type, **s} for s in summaries
    ])
    return {"symbol": symbol_id, "side": side, "order_type": resolved_type, "summaries": summaries}
