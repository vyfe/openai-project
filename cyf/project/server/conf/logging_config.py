import logging
import sys
from logging.handlers import RotatingFileHandler


def configure_root_logging(debug: bool = True):
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        force=True,
    )

    if debug:
        root_logger = logging.getLogger()
        if not any(isinstance(handler, logging.StreamHandler) for handler in root_logger.handlers):
            root_logger.addHandler(logging.StreamHandler(stream=sys.stdout))
    return logging.getLogger()


def configure_logging(app, debug: bool = False):
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        filemode="a",
    )

    if debug:
        handler = logging.StreamHandler(stream=sys.stdout)
    else:
        handler = RotatingFileHandler("app.log", maxBytes=10 * 1024 * 1024, backupCount=5, encoding="UTF-8")
        handler.setLevel(logging.INFO)

    app.logger.addHandler(handler)
    return app.logger
