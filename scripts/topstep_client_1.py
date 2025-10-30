# file: root/scripts/topstep_client_1.py
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
from utils.email_util_ver_02 import send_email
import math

# --- add near the top of the file ---
from concurrent.futures import ThreadPoolExecutor, as_completed

logging_level = 'INFO'
logging.basicConfig(level=logging_level, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------------------
# Paths & Config
# --------------------------------------------------------------------------------------
EMAIL = "vikaskaler.bnr@gmail.com"
SCRIPT_DIR = os.path.dirname(__file__)
CONFIG_PATH = os.path.join(SCRIPT_DIR, "configs", "topstep-config.yaml")
# Where we keep dated CSVs by default (…/portfolios/topstep/YYYY-MM-DD/*.csv)
PORTFOLIO_PATH = os.path.join(os.path.dirname(__file__), "..", "portfolios/topstep")


# --------------------------------------------------------------------------------------
# Exceptions
# --------------------------------------------------------------------------------------
class TopstepConfigError(RuntimeError):
    ...


class TopstepApiError(RuntimeError):
    ...


class TopstepPayloadError(RuntimeError):
    ...


# --------------------------------------------------------------------------------------
# CSV Helpers
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

    - Creates file/folders if missing
    - Adds UTC timestamp column (ts_utc) by default
    - Expands headers if new keys appear later
    - Accepts dict or list of dicts
    """
    path = Path(csv_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    rows = [data] if isinstance(data, dict) else data
    if not rows:
        return path

    if add_timestamp:
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        for row in rows:
            # Do not overwrite existing ts_utc if caller set it
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
# Config & Utilities
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

    return cfg


def _symbol_params(cfg: Dict[str, Any], symbol_id: str) -> Tuple[float, float]:
    """
    Read per-symbol SL/TP (points) from config.
    Example:
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
    """
    Futures points model:
      long  → SL = avg - sl_pts, TP = avg + tp_pts
      short → SL = avg + sl_pts, TP = avg - tp_pts
    """
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
    """
    Choose the most recent open position for (account_id [, symbol_id]).
    If symbol_id is None, returns the newest position for that account regardless of symbol.
    """
    if symbol_id:
        candidates = [
            p for p in positions
            if p.get("accountId") == account_id and p.get("symbolId") == symbol_id
        ]
    else:
        candidates = [p for p in positions if p.get("accountId") == account_id]

    if not candidates:
        return None

    # Pick the newest by entryTime if present
    try:
        candidates.sort(key=lambda p: p.get("entryTime", ""), reverse=True)
    except Exception:
        pass
    return candidates[0]


def _poll_position_until_seen(
    *,
    user_id: int,
    account_id: int,
    symbol_id: str,
    interval_s: float = 0.5,
    max_wait_s: float = 5.0,
) -> Optional[Dict[str, Any]]:
    """
    Poll /Position/all/user/{user_id} until a matching open position appears, or timeout.
    """
    deadline = time.time() + max_wait_s
    while time.time() < deadline:
        pos = get_positions(user_id=user_id)  # uses config token/headers
        match = _find_position_for_account(pos, account_id=account_id, symbol_id=symbol_id)
        if match:
            return match
        time.sleep(interval_s)
    return None


# --------------------------------------------------------------------------------------
# HTTP Helpers (API endpoints)
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
    # Enforce common expectations and avoid sending nulls.
    if t == 1:  # Limit
        if limit_price is None:
            raise TopstepPayloadError("Limit order requires limit_price.")
    elif t == 4:  # Stop
        if stop_price is None:
            raise TopstepPayloadError("Stop order requires stop_price.")
    elif t == 5:  # TrailingStop (API may need additional trail params; adapt as needed)
        if stop_price is None:
            raise TopstepPayloadError("TrailingStop typically requires stop_price (adapt if API uses trail params).")
    else:
        # Market / JoinBid / JoinAsk: prices must NOT be sent
        if limit_price is not None or stop_price is not None:
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

    # Guard rails for join types:
    if t == 6 and s not in ("long", "buy", "bid", "joiningbid", "joining-bid"):
        raise TopstepPayloadError("JoinBid (type=6) expects side='long'/'buy'.")
    if t == 7 and s not in ("short", "sell", "ask", "joiningask", "joining-ask"):
        raise TopstepPayloadError("JoinAsk (type=7) expects side='short'/'sell'.")

    # Position sign: long=+qty, short=-qty
    if s in ("long", "buy", "bid", "joiningbid", "joining-bid"):
        position_size = qty
    elif s in ("short", "sell", "ask", "joiningask", "joining-ask"):
        position_size = -qty
    else:
        raise TopstepPayloadError("side must be 'long'|'short' (aliases: buy/bid, sell/ask).")

    _validate_prices(t, limit_price, stop_price)

    body: Dict[str, Any] = {
        "accountId": int(account_id),
        "symbolId": symbol_id,
        "type": t,
        "positionSize": position_size,
        "timeType": time_type,
        "customTag": str(uuid.uuid4()),  # must be unique each order
    }

    # Only include price fields when required/valid
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
    """
    Priority:
      1) explicit order_type argument
      2) config[symbol_id].order_type
      3) default: joinBid for long, joinAsk for short
    """
    if explicit is not None:
        return _normalize_order_type(explicit)

    sym_cfg = cfg.get(symbol_id) or {}
    ot = sym_cfg.get("order_type")  # may be "market", "limit", "join_bid", "join_ask"
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
    Also: send an email per position with a template based on SL/TP presence.
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

    # Filter if requested
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

    # --- EMAIL ON FOUND POSITIONS ---
    if positions:
        for p in positions:
            try:
                payload = format_position_email(p)
                # Be flexible with your send_email signature.
                try:
                    # Preferred full fields
                    send_email(
                        to_emails=EMAIL,
                        subject=payload["subject"],
                        body=payload["html"],
                    )
                except TypeError:
                    # Fallbacks if your helper has a different signature
                    try:
                        send_email(
                            to_emails=EMAIL,
                            subject=payload["subject"],
                            body=payload["html"],
                        )
                    except TypeError:
                        send_email(
                            to_emails=EMAIL,
                            subject=payload["subject"],
                            body=payload["html"],
                        )
                logger.info(f"Position email sent for {p.get('symbolId')} acct {p.get('accountId')}")
            except Exception as e:
                logger.warning(f"Failed to send position email: {e}")

    return positions


def has_open_position(
    account_id: int,
    *,
    symbol_id: Optional[str] = None,
    cfg_path: str = CONFIG_PATH,
    add_app_headers: bool = False,
) -> bool:
    """
    Return True if the user has any open position for the given account (and symbol, if provided).
    """
    cfg = load_config(cfg_path)
    user_id = cfg["user_id"]
    positions = get_positions(user_id=user_id, cfg_path=cfg_path, add_app_headers=add_app_headers)
    pos = _find_position_for_account(positions, account_id=account_id, symbol_id=symbol_id)
    return pos is not None


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
    """
    Update SL/TP for a position on a given trading account.
    """
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
    """
    Flatten (close all positions) for a given Topstep account via HTTP DELETE.
    Returns 200 OK with empty body on success.
    """
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
    """
    Flatten (close all positions) for all accounts in the config.
    """
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
# Order Sender (with chronology + "skip if position open" safeguard)
# --------------------------------------------------------------------------------------
# def send_order(
#     *,
#     side: str,
#     order_type: Union[int, str],
#     cfg_path: str = CONFIG_PATH,
#     account_id: Optional[int] = None,
#     base_url: str = "https://userapi.topstepx.com/Order",
#     timeout: float = 10.0,
#     add_app_headers: bool = False,
#     time_type: int = 0,
#     limit_price: Optional[float] = None,
#     stop_price: Optional[float] = None,
#     dry_run: bool = False,
#     fail_fast: bool = False,
#     skip_if_open: bool = True,  # NEW: if True, we skip placing a new order when an open position exists
#     check_symbol_only: bool = True,  # if True, only skip when open position matches cfg['symbol_id']; if False, any open pos
# ) -> List[Dict[str, Any]]:
#     """
#     Generic sender supporting multiple order types.
#
#     Args:
#       side: 'long'|'short' (aliases buy/bid, sell/ask)
#       order_type: {'limit','market','stop','trailingStop','joinBid','joinAsk'} or codes {1,2,4,5,6,7}
#       account_id: if None, sends to all accounts in config.account_ids
#       limit_price/stop_price: provided only for types that require them
#       dry_run: logger.info request instead of sending
#       fail_fast: raise on first failure if True
#       skip_if_open: skip placing an order for an account that already has an open position
#       check_symbol_only: if True, skip only when open position is for cfg['symbol_id']; otherwise any open position triggers skip
#     """
#     cfg = load_config(cfg_path)
#     token = cfg["token"]
#     symbol_id = cfg["symbol_id"]
#     qty = cfg["number_of_cons"]
#     accounts: Sequence[int] = [account_id] if account_id else cfg["account_ids"]
#
#     headers = {
#         "Authorization": f"Bearer {token}",
#         "Accept": "application/json",
#         "Content-Type": "application/json",
#     }
#     if add_app_headers:
#         headers["x-app-type"] = cfg.get("x_app_type", "px-desktop")
#         headers["x-app-version"] = cfg.get("x_app_version", "1.22.19")
#
#     session = requests.Session()
#     results: List[Dict[str, Any]] = []
#
#     total = len(accounts)
#     logger.info(f"\nSending order to {total} account(s): side={side}, type={order_type}, symbol={symbol_id}, qty={qty}")
#
#     for idx, acc in enumerate(accounts, 1):
#         logger.info(f" → [{idx}/{total}] account {acc} ...", end="", flush=True)
#
#         # --- Skip if open position safeguard ---
#         if skip_if_open:
#             already_open = has_open_position(
#                 acc,
#                 symbol_id=symbol_id if check_symbol_only else None,
#                 cfg_path=cfg_path,
#                 add_app_headers=add_app_headers,
#             )
#             if already_open:
#                 logger.info(" ⏭️  skipped (open position exists)")
#                 skip_info = {
#                     "accountId": acc,
#                     "skipped": True,
#                     "reason": "open_position_exists",
#                     "symbol_scoped": check_symbol_only,
#                     "symbolId": symbol_id,
#                 }
#                 results.append(skip_info)
#                 # Log skip
#                 append_to_csv(dated_csv_path(PORTFOLIO_PATH, "order_skips.csv"), skip_info)
#                 continue
#
#         try:
#             body = _payload(
#                 side=side,
#                 account_id=acc,
#                 symbol_id=symbol_id,
#                 qty=qty,
#                 order_type=order_type,
#                 time_type=time_type,
#                 limit_price=limit_price,
#                 stop_price=stop_price,
#             )
#
#             if dry_run:
#                 logger.info(" DRY RUN")
#                 logger.info(f"    POST {base_url}")
#                 logger.info(f"    Headers: {headers}")
#                 logger.info(f"    Body: {json.dumps(body)}")
#                 results.append({"accountId": acc, "dryRun": True, "payload": body})
#                 continue
#
#             resp = session.post(base_url, headers=headers, json=body, timeout=timeout)
#             item = {
#                 "accountId": acc,
#                 "status_code": resp.status_code,
#                 "ok": resp.ok,
#                 "text": (resp.text or "").strip(),
#             }
#             try:
#                 if item["text"]:
#                     item["json"] = resp.json()
#             except Exception:
#                 pass
#
#             results.append(item)
#             if resp.ok:
#                 logger.info(f" ✅ (HTTP {resp.status_code})")
#             else:
#                 logger.info(f" ⚠️  (HTTP {resp.status_code})")
#                 if fail_fast:
#                     raise TopstepApiError(
#                         f"send_order(side={side}, type={order_type}) failed for account {acc} "
#                         f"(HTTP {resp.status_code}) -> {item['text'][:500]}"
#                     )
#         except Exception as e:
#             logger.info(" ❌")
#             err = {"accountId": acc, "error": str(e)}
#             results.append(err)
#             if fail_fast:
#                 raise
#
#     logger.info("\nAll order requests processed.\n")
#     return results


# --------------------------------------------------------------------------------------
# Safety: flatten & log helper
# --------------------------------------------------------------------------------------
def _safety_flat_and_log(
    *,
    account_id: int,
    symbol_id: str,
    portfolio_dir: str,
    reason: str,
    add_app_headers: bool,
    cfg_path: str,
) -> None:
    try:
        append_to_csv(dated_csv_path(portfolio_dir, "safety_flats.csv"), {
            "accountId": account_id,
            "symbolId": symbol_id,
            "reason": reason,
        })
        r = flat_account(account_id, cfg_path=cfg_path, add_app_headers=add_app_headers)
        append_to_csv(dated_csv_path(portfolio_dir, "safety_flats.csv"), {
            "accountId": account_id,
            "symbolId": symbol_id,
            "flatten_result": r.get("status_code"),
        })
    except Exception as e:
        append_to_csv(dated_csv_path(portfolio_dir, "safety_flats.csv"), {
            "accountId": account_id,
            "symbolId": symbol_id,
            "flatten_error": str(e)[:500],
        })


# --------------------------------------------------------------------------------------
# Full Orchestration: place order -> poll -> compute SL/TP -> set -> validate -> CSVs
# --------------------------------------------------------------------------------------
def topstep_order_execution(
    *,
    side: str,
    order_type: Optional[Union[int, str]] = None,  # may be None -> resolve via config/default
    account_id: Optional[int] = None,
    cfg_path: str = CONFIG_PATH,
    portfolio_dir: str = PORTFOLIO_PATH,
    add_app_headers: bool = False,
    poll_interval_s: float = 0.5,
    poll_timeout_s: float = 5.0,
) -> Dict[str, Any]:
    """
    One full operation:
      1) resolve order type (config/default) and place order(s) — but skip accounts with open positions
      2) poll positions → get avg price
      3) compute SL/TP (points from config)
      4) edit stop loss / take profit
      5) refetch positions → validate
      6) write all steps to dated CSVs
      7) if SL/TP cannot be resolved at any point → FLATTEN that account
    """
    cfg = load_config(cfg_path)
    symbol_id = cfg["symbol_id"]
    user_id = cfg.get("user_id")
    if not user_id:
        raise TopstepConfigError("user_id missing in config.")
    accounts = [account_id] if account_id else cfg["account_ids"]

    # Resolve initial order type (market/limit/joinBid/joinAsk)
    resolved_type = _resolve_order_type_for_side(cfg, symbol_id, side, explicit=order_type)

    # Place the initial order(s) with skip-if-open safeguard
    order_results = send_order(
        side=side,
        order_type=resolved_type,
        cfg_path=cfg_path,
        account_id=account_id,     # single or all
        add_app_headers=add_app_headers,
        dry_run=False,
        fail_fast=False,
        skip_if_open=True,
        check_symbol_only=True,    # skip only if same-symbol position already open
    )
    append_to_csv(dated_csv_path(portfolio_dir, "orders.csv"), order_results)

    # Prepare SL/TP params; if missing, flatten accounts (can’t manage risk)
    summaries: List[Dict[str, Any]] = []
    try:
        sl_pts, tp_pts = _symbol_params(cfg, symbol_id)
    except Exception as e:
        reason = f"Cannot read stop_loss/take_profit for {symbol_id}: {e}"
        for acc in accounts:
            _safety_flat_and_log(
                account_id=acc,
                symbol_id=symbol_id,
                portfolio_dir=portfolio_dir,
                reason=reason,
                add_app_headers=add_app_headers,
                cfg_path=cfg_path,
            )
            summaries.append({"accountId": acc, "ok": False, "phase": "pre_sltp", "action": "flattened", "reason": str(e)})
        append_to_csv(dated_csv_path(portfolio_dir, "operations.csv"), [
            {"side": side, "order_type": resolved_type, **s} for s in summaries
        ])
        return {"symbol": symbol_id, "side": side, "order_type": resolved_type, "summaries": summaries}

    # For each account: only proceed with SL/TP if we actually placed an order (not skipped)
    # Determine which accounts were skipped
    skipped_accounts = {r.get("accountId") for r in order_results if r.get("skipped")}
    actionable_accounts = [a for a in accounts if a not in skipped_accounts]

    for acc in actionable_accounts:
        # Poll for the new/open position
        pos = _poll_position_until_seen(
            user_id=user_id,
            account_id=acc,
            symbol_id=symbol_id,
            interval_s=poll_interval_s,
            max_wait_s=poll_timeout_s,
        )
        if not pos:
            reason = f"No position appeared for account {acc} within {poll_timeout_s}s."
            _safety_flat_and_log(
                account_id=acc,
                symbol_id=symbol_id,
                portfolio_dir=portfolio_dir,
                reason=reason,
                add_app_headers=add_app_headers,
                cfg_path=cfg_path,
            )
            summaries.append({"accountId": acc, "ok": False, "phase": "poll_after_order", "action": "flattened", "reason": reason})
            continue

        append_to_csv(dated_csv_path(portfolio_dir, "positions_before_sltp.csv"), pos)

        try:
            avg = float(pos.get("averagePrice"))
            if not avg or avg <= 0:
                raise ValueError("averagePrice missing/invalid")
        except Exception as e:
            reason = f"Cannot resolve averagePrice for account {acc}: {e}"
            _safety_flat_and_log(
                account_id=acc,
                symbol_id=symbol_id,
                portfolio_dir=portfolio_dir,
                reason=reason,
                add_app_headers=add_app_headers,
                cfg_path=cfg_path,
            )
            summaries.append({"accountId": acc, "ok": False, "phase": "avg_price", "action": "flattened", "reason": str(e)})
            continue

        # Compute absolute SL/TP and set them
        try:
            stop_px, take_px = _calc_sl_tp_from_avg(avg, side, sl_pts, tp_pts)
        except Exception as e:
            reason = f"SL/TP compute failure for account {acc}: {e}"
            _safety_flat_and_log(
                account_id=acc,
                symbol_id=symbol_id,
                portfolio_dir=portfolio_dir,
                reason=reason,
                add_app_headers=add_app_headers,
                cfg_path=cfg_path,
            )
            summaries.append({"accountId": acc, "ok": False, "phase": "compute_sltp", "action": "flattened", "reason": str(e)})
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
            reason = f"SL/TP API failure for account {acc}: {e}"
            _safety_flat_and_log(
                account_id=acc,
                symbol_id=symbol_id,
                portfolio_dir=portfolio_dir,
                reason=reason,
                add_app_headers=add_app_headers,
                cfg_path=cfg_path,
            )
            summaries.append({"accountId": acc, "ok": False, "phase": "edit_sltp", "action": "flattened", "reason": str(e)})
            continue

        append_to_csv(dated_csv_path(portfolio_dir, "sltp_updates.csv"), {
            **resp,
            "accountId": acc,
            "positionId": position_id,
            "computed_stopLoss": stop_px,
            "computed_takeProfit": take_px,
        })

        # Validate by re-fetching positions
        pos_after = get_positions(user_id=user_id, contract_name=symbol_id)
        cur = _find_position_for_account(pos_after, account_id=acc, symbol_id=symbol_id)
        append_to_csv(dated_csv_path(portfolio_dir, "positions_after_sltp.csv"), cur or {
            "accountId": acc, "symbolId": symbol_id, "warning": "position not found after SL/TP set"
        })

        ok = False
        if cur:
            def _float_eq(a: Optional[float], b: Optional[float], eps: float = 1e-6) -> bool:
                try:
                    return abs(float(a) - float(b)) <= eps
                except Exception:
                    return False
            ok = _float_eq(cur.get("stopLoss"), stop_px) and _float_eq(cur.get("takeProfit"), take_px)

        summaries.append({
            "accountId": acc,
            "positionId": position_id,
            "avg_price": avg,
            "stopLoss_set": stop_px,
            "takeProfit_set": take_px,
            "validated": ok,
        })

    # Also record the skipped accounts as part of the operation summary
    for acc in skipped_accounts:
        summaries.append({
            "accountId": acc,
            "skipped": True,
            "reason": "open_position_exists",
            "validated": False,
        })

    # Write operation summary
    append_to_csv(dated_csv_path(portfolio_dir, "operations.csv"), [
        {"side": side, "order_type": resolved_type, **s} for s in summaries
    ])

    return {"symbol": symbol_id, "side": side, "order_type": resolved_type, "summaries": summaries}

# --------------------------------------------------------------------------------------
# Order Sender (with chronology + "skip if position open" safeguard)
# --------------------------------------------------------------------------------------
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
    skip_if_open: bool = True,       # keep your safeguard
    check_symbol_only: bool = True,  # scope skip by symbol
    fanout: bool = True,             # NEW: parallelize initial orders by default
    max_workers: Optional[int] = None,  # NEW: override worker count if desired
) -> List[Dict[str, Any]]:
    """
    Generic sender supporting multiple order types.

    Args:
      side: 'long'|'short'
      order_type: {'limit','market','stop','trailingStop','joinBid','joinAsk'} or codes {1,2,4,5,6,7}
      account_id: if None, sends to all accounts in config.account_ids
      ...
      fanout: if True, send to all accounts in parallel (recommended for initial entries)
      max_workers: cap the thread pool size; default uses cfg['parallel_max_workers'] or len(accounts)
    """
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

    # worker sizing
    default_workers = cfg.get("parallel_max_workers") or len(accounts)
    workers = min(len(accounts), max_workers or default_workers or 8)

    logger.info(f"\nSending order to {len(accounts)} account(s): side={side}, type={order_type}, symbol={symbol_id}, qty={qty}")
    results: List[Dict[str, Any]] = []

    # --- Inner worker (thread-safe) ---
    def _place_one(acc: int) -> Dict[str, Any]:
        # Skip-if-open safeguard (per account)
        if skip_if_open:
            already_open = has_open_position(
                acc,
                symbol_id=symbol_id if check_symbol_only else None,
                cfg_path=cfg_path,
                add_app_headers=add_app_headers,
            )
            if already_open:
                logger.info(f" → account {acc} ⏭️  skipped (open position exists)")
                skip_info = {
                    "accountId": acc,
                    "skipped": True,
                    "reason": "open_position_exists",
                    "symbol_scoped": check_symbol_only,
                    "symbolId": symbol_id,
                }
                append_to_csv(dated_csv_path(PORTFOLIO_PATH, "order_skips.csv"), skip_info)
                return skip_info

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
            logger.info(f" → account {acc} DRY RUN\n    POST {base_url}\n    Headers: {headers}\n    Body: {json.dumps(body)}")
            return {"accountId": acc, "dryRun": True, "payload": body}

        try:
            # one-off request in this thread (Session not shared across threads)
            resp = requests.post(base_url, headers=headers, json=body, timeout=timeout)
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

            if resp.ok:
                logger.info(f" → account {acc} ✅ (HTTP {resp.status_code})")
            else:
                logger.info(f" → account {acc} ⚠️  (HTTP {resp.status_code})")

            if fail_fast and not resp.ok:
                # bubble up to fail the whole send quickly
                raise TopstepApiError(
                    f"send_order(side={side}, type={order_type}) failed for account {acc} "
                    f"(HTTP {resp.status_code}) -> {item['text'][:500]}"
                )
            return item
        except Exception as e:
            logger.info(f" → account {acc} ❌ {e}")
            if fail_fast:
                raise
            return {"accountId": acc, "error": str(e)}

    # --- Parallel fan-out path ---
    if fanout and len(accounts) > 1:
        logger.info(f"Fan-out enabled (workers={workers})")
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futures = {ex.submit(_place_one, acc): acc for acc in accounts}
            for fut in as_completed(futures):
                results.append(fut.result())
    else:
        # Fallback: sequential (original behavior)
        for idx, acc in enumerate(accounts, 1):
            logger.info(f" → [{idx}/{len(accounts)}] account {acc} ...", end="", flush=True)
            res = _place_one(acc)
            results.append(res)

    logger.info("\nAll order requests processed.\n")
    return results


# --------------------------------------------------------------------------------------
# Optional: flatten multiple accounts in parallel (useful for synchronized exits)
# --------------------------------------------------------------------------------------
def flat_accounts_parallel(
    account_ids: Optional[Sequence[int]] = None,
    *,
    cfg_path: str = CONFIG_PATH,
    base_url: str = "https://userapi.topstepx.com/Order/CloseAll",
    timeout: float = 10.0,
    add_app_headers: bool = False,
    dry_run: bool = False,
    max_workers: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Flatten (close all positions) for given or configured accounts in parallel.
    If account_ids is None or empty, it will load account_ids from the YAML config.
    """
    cfg = load_config(cfg_path)

    # --- Default to config.account_ids if not provided ---
    if not account_ids:
        account_ids = cfg.get("account_ids", [])
        if not account_ids:
            raise TopstepConfigError(f"No account_ids provided or found in {cfg_path}")

    default_workers = cfg.get("parallel_max_workers") or len(account_ids)
    workers = min(len(account_ids), max_workers or default_workers or 8)

    logger.info(f"\nFlattening {len(account_ids)} account(s) in parallel (workers={workers})...")

    out: List[Dict[str, Any]] = []

    def _flat_one(acc_id: int) -> Dict[str, Any]:
        try:
            res = flat_account(
                account_id=acc_id,
                cfg_path=cfg_path,
                base_url=base_url,
                timeout=timeout,
                add_app_headers=add_app_headers,
                dry_run=dry_run,
            )
            if res.get("ok"):
                logger.info(f" → account {acc_id} ✅ flattened (HTTP {res['status_code']})")
            else:
                logger.info(f" → account {acc_id} ⚠️  status {res.get('status_code')}")
            return res
        except Exception as e:
            logger.info(f" → account {acc_id} ❌ {e}")
            return {"accountId": acc_id, "error": str(e)}

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(_flat_one, a): a for a in account_ids}
        for fut in as_completed(futures):
            out.append(fut.result())

    logger.info("\nAll flatten requests processed.\n")
    return out


def format_position_email(p: Dict[str, Any], tz_name: str = "America/Toronto") -> Dict[str, str]:
    """
    Returns a dict: {event, subject, text, html}
    Case A (just opened): stopLoss and takeProfit are None
    Case B (final position): both present
    """
    # Extract + normalize
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

    # Direction
    direction = "LONG" if (size or 0) > 0 else ("SHORT" if (size or 0) < 0 else "FLAT")

    # Entry time pretty (localize gently without external libs)
    # entryTime example: "2025-10-28T00:37:10.808704+00:00"
    try:
        dt_utc = datetime.fromisoformat(entry_time.replace("Z", "+00:00")) if entry_time else None
    except Exception:
        dt_utc = None
    pretty_time = entry_time
    try:
        if dt_utc:
            # basic local conversion without pytz: offset for America/Toronto is not trivial year-round;
            # If you already have pytz/zoneinfo in the project, replace this with a proper localization.
            # For now, just show UTC + raw ISO as a fallback.
            pretty_time = dt_utc.strftime("%Y-%m-%d %H:%M:%S %Z") + " (UTC)"
    except Exception:
        pass

    # Decide case
    just_opened = (sl is None and tp is None)

    # Subject / event
    if just_opened:
        event   = "position_opened_no_sltp"
        subject = f"[Topstep] {symbol_name} {direction} x{abs(size)} opened (acct {account_id})"
        lead    = f"{symbol_name} {direction} position opened — SL/TP pending"
    else:
        event   = "position_final_with_sltp"
        subject = f"[Topstep] {symbol_name} {direction} x{abs(size)} finalized (SL/TP set)"
        lead    = f"{symbol_name} {direction} position finalized — SL/TP set"

    # Numbers pretty
    def f(x: Optional[float]) -> str:
        if x is None:
            return "—"
        if isinstance(x, (int, float)) and (math.isfinite(x)):
            # futures often need 3 decimals; keep precision but strip trailing zeros
            s = f"{x:.6f}".rstrip("0").rstrip(".")
            return s
        return str(x)

    text_lines = [
        lead,
        "",
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
# Quick manual run (comment out in prod)
# --------------------------------------------------------------------------------------
if __name__ == "__main__":
    # Example: Use config's order_type; if absent -> joinBid/joinAsk by side
    # Run one full operation LONG for all accounts (skips those already holding symbol)
    # flat_accounts_parallel(cfg_path=CONFIG_PATH)
    # send_order(side='long', order_type='market')
    # flat_all(cfg_path=CONFIG_PATH)
    # pos = get_positions(cfg_path=CONFIG_PATH)
    # logger.info(json.dumps(pos, indent=2))
    # stopLoss = 25951
    # profit = 26031
    # slTp = edit_stop_loss_account(
    #     tradingAccountId=12977613,
    #     positionId=415926290,
    #     stopLoss=stopLoss,
    #     takeProfit=profit,
    #     cfg_path=CONFIG_PATH,
    #     add_app_headers=False,
    # )
    # logger.info(json.dumps(slTp, indent=2))
    # pos2 = get_positions(cfg_path=CONFIG_PATH)
    # logger.info(json.dumps(pos2, indent=2))
    # try:
    #     result = topstep_order_execution(side="short", add_app_headers=False)
    #     logger.info(json.dumps(result, indent=2))
    # except Exception as e:
    #     logger.info("Error:", e)
