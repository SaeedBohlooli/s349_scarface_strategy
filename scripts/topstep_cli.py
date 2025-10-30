# ======================
# Interactive CLI runner
# ======================
import os
import uuid
import json
from typing import Any, Dict, List, Optional, Sequence, Union
import requests
import yaml
import csv
from pathlib import Path
from datetime import datetime, timezone

from topstep_client_1 import _normalize_order_type, send_order, flat_account, load_config, CONFIG_PATH
def _prompt_choice(prompt: str, options: List[str], default: Optional[str] = None) -> str:
    opts_show = "/".join(options)
    while True:
        val = input(f"{prompt} [{opts_show}]{' (default: '+default+')' if default else ''}: ").strip()
        if not val and default:
            return default
        if val.lower() in [o.lower() for o in options]:
            return val.lower()
        print(f"Invalid choice. Please pick one of: {opts_show}")

def _prompt_float(prompt: str) -> float:
    while True:
        val = input(f"{prompt}: ").strip()
        try:
            return float(val)
        except ValueError:
            print("Please enter a valid number (e.g., 2385.4)")

def _select_account_from_cfg(cfg: Dict[str, Any]) -> Optional[int]:
    accounts = cfg["account_ids"]
    if not accounts:
        return None
    if len(accounts) == 1:
        return accounts[0]
    print("\nAvailable accounts:")
    for i, a in enumerate(accounts, 1):
        print(f"  {i}) {a}")
    print("  A) All")
    while True:
        choice = input("Pick account (number) or 'A' for all [A]: ").strip()
        if choice == "" or choice.lower() == "a":
            return None  # None => send to all accounts
        if choice.isdigit() and 1 <= int(choice) <= len(accounts):
            return accounts[int(choice) - 1]
        print("Invalid selection.")

def run_cli():
    # Load config once to show accounts and symbol
    cfg = load_config(CONFIG_PATH)
    print("\n=== Topstep Order CLI ===")
    print(f"Symbol: {cfg['symbol_id']} | Size per side: {cfg['number_of_cons']}")
    print(f"Accounts in config: {', '.join(map(str, cfg['account_ids']))}")

    # Side
    side = _prompt_choice("Side", ["long", "short"], default="long")

    # Order type selection
    # Show friendly menu for types we support
    menu = [
        ("limit", 1),
        ("market", 2),
        ("stop", 4),
        ("trailingStop", 5),
        ("joinBid", 6),
        ("joinAsk", 7),
    ]
    print("\nOrder types:")
    for i, (name, code) in enumerate(menu, 1):
        print(f"  {i}) {name:<12} -> {code}")
    print("You can type the name (e.g., joinBid) or the code (e.g., 6).")

    order_type_raw = input("Order type: ").strip()
    # Normalize to name/code accepted by send_order()
    # Accept menu index as well
    order_type_value: Union[int, str]
    if order_type_raw.isdigit():
        idx_or_code = int(order_type_raw)
        # If it's 1..len(menu), map to name; if it's a code value, pass as int
        if 1 <= idx_or_code <= len(menu):
            order_type_value = menu[idx_or_code - 1][0]
        else:
            order_type_value = idx_or_code
    else:
        order_type_value = order_type_raw

    # Collect prices if needed
    limit_price = None
    stop_price = None
    # Determine what’s required based on the normalized mapping we already enforce in send_order()
    try:
        # Try a dry payload build to know which fields are required
        # We won't send; just reuse the validator by attempting with missing fields.
        _ = _normalize_order_type(order_type_value)
        tcode = _  # int code
        if tcode == 1:  # Limit
            limit_price = _prompt_float("Limit price")
        elif tcode == 4:  # Stop
            stop_price = _prompt_float("Stop price")
        elif tcode == 5:  # TrailingStop (you can adapt to ask for trail params if needed)
            stop_price = _prompt_float("Initial stop price")
    except Exception as e:
        print(f"Error: {e}")
        return

    # Choose account (single or all)
    account_id = _select_account_from_cfg(cfg)

    # Confirm summary
    print("\nSummary:")
    print(f"  Side: {side}")
    print(f"  Type: {order_type_value}")
    if limit_price is not None:
        print(f"  Limit price: {limit_price}")
    if stop_price is not None:
        print(f"  Stop price: {stop_price}")
    print(f"  Accounts: {'ALL from config' if account_id is None else account_id}")
    go = _prompt_choice("Send order?", ["y", "n"], default="y")
    if go != "y":
        print("Aborted.")
        return

    # Send the order
    try:
        res = send_order(
            side=side,
            order_type=order_type_value,
            account_id=account_id,
            limit_price=limit_price,
            stop_price=stop_price,
            add_app_headers=False,   # flip to True if required by your token/session
        )
        print("\nOrder response:")
        for r in res:
            acct = r.get("accountId")
            status = r.get("status_code")
            ok = r.get("ok")
            print(f"  account={acct} -> status={status} ok={ok}")
            if "json" in r and r["json"]:
                print(f"    body: {json.dumps(r['json'], ensure_ascii=False)}")
            elif r.get("text"):
                print(f"    body: {r['text'][:200]}")
    except Exception as e:
        print(f"\nOrder failed: {e}")
        return

    # Ask to flatten
    print("")
    do_flat = _prompt_choice("Flatten account(s) now?", ["y", "n"], default="n")
    if do_flat != "y":
        print("Done.")
        return

    # If a single account was used, default to that; else ask
    flatten_account_id = account_id
    if flatten_account_id is None:
        # multiple accounts — ask which one to flatten or all
        print("\nSelect account to flatten:")
        flatten_account_id = _select_account_from_cfg(cfg)  # None == all
    # Execute flatten: if None -> all accounts; else one account
    try:
        if flatten_account_id is None:
            print("\nFlattening ALL accounts from config...")
            for acct in cfg["account_ids"]:
                r = flat_account(acct)
                print(f"  flattened {acct}: status={r.get('status_code')} ok={r.get('ok')}")
        else:
            r = flat_account(flatten_account_id)
            print(f"\nFlattened {flatten_account_id}: status={r.get('status_code')} ok={r.get('ok')}")
    except Exception as e:
        print(f"\nFlatten failed: {e}")
        return

    print("Done.")

