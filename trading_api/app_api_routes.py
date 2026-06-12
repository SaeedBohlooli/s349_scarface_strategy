from flask import Blueprint, request, jsonify
import logging
import os
import yaml
logger = logging.getLogger(__name__)
from trading_core.file_manager import FileManager
from trading_core.directory_manager import DirectoryManager
from trading_utils import streaming_util
from trading_utils import date_utils
from trading_engine import pnl_helper

from pprint import pprint
app_bp = Blueprint("app_bp", __name__)


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
        payload = yaml.safe_load(f)   # converts YAML - > dict

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
