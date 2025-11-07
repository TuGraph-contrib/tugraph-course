import os
import logging
from datetime import datetime


def _timestamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _setup_multipurpose_logger(log_dir: str, filename: str):
    logger = logging.getLogger("train_logger")
    logger.setLevel(logging.INFO)

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)
    stream_formatter = logging.Formatter("%(message)s")

    file_handler = logging.FileHandler(
        filename=os.path.join(log_dir, filename), mode="a", encoding="utf-8"
    )
    file_formatter = logging.Formatter("[%(levelname)s %(asctime)s]: %(message)s")

    stream_handler.setFormatter(stream_formatter)
    file_handler.setFormatter(file_formatter)

    logger.addHandler(stream_handler)
    logger.addHandler(file_handler)

    return logger


def setup_grader_logger(fname: str, log_dir: str = "./logs"):
    timestamp = _timestamp()

    filename = f"{fname}-{timestamp}"
    filename += ".log"
    return _setup_multipurpose_logger(log_dir, filename)
