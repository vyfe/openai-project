#!/usr/bin/env python3
from __future__ import annotations

import logging
import os
import sys


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
SERVER_DIR = os.path.dirname(CURRENT_DIR)
if SERVER_DIR not in sys.path:
    sys.path.insert(0, SERVER_DIR)

from quant_client.cli import main
from conf.logging_config import configure_root_logging


if __name__ == "__main__":
    configure_root_logging()
    logging.getLogger("quant.client.agent").info("quant data agent started")
    main()
