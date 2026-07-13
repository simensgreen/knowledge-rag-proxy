"""Application logging configured to match uvicorn's colored output."""

from __future__ import annotations

import logging

from uvicorn.logging import DefaultFormatter

from server.env_config import get_log_level

LOG_FORMAT = "%(levelprefix)s %(asctime)s %(name)s %(message)s"
DATE_FORMAT = "%H:%M:%S"


def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(DefaultFormatter(fmt=LOG_FORMAT, datefmt=DATE_FORMAT))

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(get_log_level())
