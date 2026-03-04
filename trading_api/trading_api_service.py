# app.py
import argparse
import logging
import sys
from flask import Flask
from flask_cors import CORS

sys.path.insert(0, f'../')

from trading_core.config_manager import ConfigManager
from trading_core.logging_manager import LoggingManager
from trading_core.file_manager import FileManager
from trading_core.directory_manager import DirectoryManager

# General shared endpoints
from trading_core.broker import broker_bp

# project-specific endpoints
from app_api_routes import app_bp


def create_app(portfolio_id):
    app = Flask(__name__)
    CORS(app)

    # Shared endpoints
    app.register_blueprint(broker_bp)

    # Project endpoints
    app.register_blueprint(app_bp)

    return app


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--portfolio-id", required=True)
    args = parser.parse_args()

    portfolio_id = args.portfolio_id

    # Load config
    app_config = ConfigManager.load(portfolio_id)

    dirs = DirectoryManager(
        portfolio_id=portfolio_id,
        app_config=app_config
    )

    FileManager.set_dirs(dirs)
    FileManager.set_files_config(app_config.get("files", {}))

    api_service_cfg = app_config["api_service"]

    logger = LoggingManager.setup(
        log_dir=f'../../portfolios/{portfolio_id}/logs/api_service',
        portfolio_id=portfolio_id,
        logging_level=logging.INFO
    )
    logger.info("===========================================")
    logger.info(f"Starting api_service API for portfolio {portfolio_id}")
    logger.info(f"Config Loaded: {api_service_cfg}")
    logger.info("===========================================")

    app = create_app(portfolio_id)

    app.run(
        host=api_service_cfg.get("host", "0.0.0.0"),
        port=api_service_cfg.get("port", 2222),
        debug=False,
        use_reloader=False
    )
