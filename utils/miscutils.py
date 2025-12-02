import logging

logger = logging.getLogger(__name__)

def setup_logger(name, level=logging.INFO, fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s'):
    logger = logging.getLogger(name)
    # logger.setLevel(level)
    logger.setLevel(logging.INFO)

    if not logger.handlers:  # Prevent adding multiple handlers

        handler = logging.StreamHandler()
        formatter = logging.Formatter(fmt)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.propagate = False
    return logger




