import asyncio
import logging
import os
from datetime import date

import yaml
from flask import Blueprint, current_app, jsonify, request

logger = logging.getLogger(__name__)
from trading_core.file_manager import FileManager
from trading_core.directory_manager import DirectoryManager
from trading_engine import pnl_helper
from trading_utils import date_utils
from trading_utils import streaming_util
from trading_utils.ib_execution_reports import fetch_ib_execution_reports_for_range

from pprint import pprint
app_bp = Blueprint("app_bp", __name__)


def _optional_account_list() -> list[str] | None:
    """
    Optional IB account filter only.

    GET: optional query param ``account`` (single value).
    POST: optional JSON field ``account``; query ``account`` also accepted.
    """
    raw = None
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        raw = data.get("account", request.args.get("account"))
    else:
        raw = request.args.get("account")
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return None
    if isinstance(raw, str):
        return [raw.strip()]
    return None


@app_bp.route("/api/ib/execution-reports", methods=["GET", "POST"])
def ib_execution_reports():
    """
    Today's IBKR executions (``reqExecutions`` cache), via dedicated ``api_ib_client_id``.

    No date parameters — always **calendar today**. Optional ``account`` only (GET query
    or POST JSON) to limit to one account; omit for all accounts.

    Does not use the trading engine's connection. Not a substitute for Flex historical range.
    """
    cfg = current_app.config.get("APP_CONFIG")
    if not cfg:
        return jsonify({"status": "error", "message": "APP_CONFIG not loaded"}), 500

    today = date.today()
    start = end = today
    accounts = _optional_account_list()

    ip = cfg.get("ip")
    port = cfg.get("port")
    if ip is None or port is None:
        return jsonify({"status": "error", "message": "Config missing ip or port."}), 500

    cid = cfg.get("client_id")
    if cid is None:
        return jsonify({"status": "error", "message": "Config missing client_id."}), 500
    api_cid = cfg.get("api_ib_client_id", int(cid) + 1)

    try:
        payload = asyncio.run(
            fetch_ib_execution_reports_for_range(
                str(ip),
                int(port),
                int(api_cid),
                start=start,
                end=end,
                accounts=accounts,
            )
        )
    except Exception as e:
        logger.exception("ib execution reports failed")
        return jsonify({"status": "error", "message": str(e)}), 500

    payload["status"] = "ok"
    payload["timestamp"] = date_utils.time_now_yyyy_mm_dd_hh_mm_ss()
    return jsonify(payload), 200


@app_bp.route("/api/get-closed-order-sets", methods=["GET"])
def get_order_history():

    results_dir = FileManager.dirs.results
    logger.info(f"Getting closed order sets {results_dir}")

    closed_order_sets_w_pnl_df = FileManager.load_my_df("closed_order_sets_w_pnl_df")
    closed_legs_w_pnl_df = FileManager.load_my_df("closed_legs_w_pnl_df")

    if closed_order_sets_w_pnl_df is None or closed_legs_w_pnl_df is None:
        logger.warning("closed_order_sets_w_pnl_df or closed_legs_w_pnl_df is None, cannot calculate pnl object for stream.")
        return {}

    pnl_stats_map = pnl_helper.calculate_pnl_stats(closed_order_sets_w_pnl_df)
    payload = streaming_util.df_to_stream_payload(parent_df=closed_order_sets_w_pnl_df,child_df=closed_legs_w_pnl_df,key_col='order_set_id')

    FileManager.save_named_json(payload, file_name="closed_order_sets_with_pnl_payload.json", dir="default", min_interval_sec=5*60)

    packet = {
        "type": "order_sets_with_pnl",
        "closed_order_sets": payload,
        "pnl_stats": pnl_stats_map,
        "timestamp": date_utils.time_now_yyyy_mm_dd_hh_mm_ss(),
        "status": "ok"
    }
    logger.info(pprint(packet))

    logger.info("[order_sets_with_pnl] Streaming ....")

    return jsonify(packet), 200


@app_bp.route("/api/get-order-set-details", methods=["POST"])
def get_order_set_details():

    data = request.json
    logger.info(f"[get_order_set_details] Received data: {data}")
    order_set_id = data.get("order_set_id")
    if not order_set_id:
        logger.error("[get_order_set_details] No order_set_id provided in the request.")
        return jsonify({"error": "order_set_id is required"}), 400

    results_dir = FileManager.dirs.default
    logger.info(f"Getting closed order sets {results_dir}")

    order_set_file_name = f"{order_set_id}_closed.json"

    payload = FileManager.load_named_json(full_path=f"{results_dir}/{order_set_file_name}")

    packet = {
        "type": "closed_order_set_details",
        "closed_order_set": payload,
        "timestamp": date_utils.time_now_yyyy_mm_dd_hh_mm_ss(),
        "status": "ok"
    }
    # logger.info(pprint(packet))

    logger.info("[get_order_set_details] Sending  ....")

    return jsonify(packet), 200


@app_bp.route("/api/get-archived-user-requests", methods=["GET"])
def get_archived_user_requests():

    archived_user_requests_df = FileManager.load_my_df("archived_user_requests")

    if archived_user_requests_df is None :
        logger.warning("archived_user_requests_df  is None")
        return {}

    payload = streaming_util.convert_df_to_dic_for_stream(archived_user_requests_df)

    FileManager.save_named_json(payload, file_name="archived_user_requests_df.json", dir="default", min_interval_sec=5 * 60)

    packet = {
        "type": "archived_user_requests",
        "archived_user_requests": payload,
        "timestamp": date_utils.time_now_yyyy_mm_dd_hh_mm_ss(),
        "status": "ok"
    }

    logger.info(f"[get_archived_user_requests] Streaming ....{pprint(packet)}")

    return jsonify(packet), 200


from flask import send_file, abort

@app_bp.route("/api/view-file", methods=["POST"])
def view_file():
    logger.info(f"[view_file] Received request to view file with args: {request.args}")
    data = request.json
    logger.info(f"[view_file] Received data: {data}")
    file_name = data.get("file_name")


    base_dir = "../configs"   # change to your path
    file_path = os.path.join(base_dir, file_name)

    if not os.path.exists(file_path):
        logger.info(f"[view_file] File {file_path} does not exist")
        abort(404)

    with open(file_path, "r", encoding="utf-8") as f:
        payload = yaml.safe_load(f)   # converts YAML → dict

    packet = {
        "type": "config_file_content",
        "file_name": file_name,
        "content": payload,   # already JSON serializable
        "timestamp": date_utils.time_now_yyyy_mm_dd_hh_mm_ss(),
        "status": "ok"
    }

    logger.info("[get_config] Sending config file content ....")
    logger.info(pprint(packet))

    return jsonify(packet), 200


@app_bp.route("/api/save-file", methods=["POST"])
def save_file():
    logger.info(f"[save_file] Received request to save file with args: {request.args}")
    data = request.json
    logger.info(f"[save_file] Received data: {data}")
    file_name = data.get("file_name")
    content = data.get("content")

    logger.info(pprint(data))

    base_dir = "../configs"   # change to your path
    file_path = os.path.join(base_dir, file_name)


    try:
        # content = json.loads(content)
        content = yaml.safe_load(content)
        logger.info(pprint(content))
        with open(file_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(
                content,
                f,
                sort_keys=False,  # important for config readability
                allow_unicode=True
            )

        logger.info(f"[save_file] Saved JSON to {file_path}")

        packet = {
            "type": "config_file_content",
            "file_name": file_name,
            "timestamp": date_utils.time_now_yyyy_mm_dd_hh_mm_ss(),
            "status": "ok"
        }

        return jsonify(packet), 200

    except Exception as e:
        logger.exception("[save_file] Failed saving file")

        return jsonify({
            "type": "config_file_content",
            "status": "error",
            "message": str(e)
        }), 500
