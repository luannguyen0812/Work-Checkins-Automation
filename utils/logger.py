import logging
import os
from datetime import date
from pythonjsonlogger import jsonlogger


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = jsonlogger.JsonFormatter("%(asctime)s %(name)s %(levelname)s %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)

        log_dir = os.path.join(os.path.dirname(__file__), "..", "logs")
        os.makedirs(log_dir, exist_ok=True)
        file_handler = logging.FileHandler(
            os.path.join(log_dir, f"bot_{date.today().isoformat()}.log")
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        level = logging.DEBUG if os.environ.get("DEBUG") else logging.INFO
        logger.setLevel(level)

    return logger
