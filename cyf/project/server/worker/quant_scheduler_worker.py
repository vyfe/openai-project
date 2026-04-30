#!/usr/bin/env python3
from __future__ import annotations

import logging
import os
import sys
import time
from datetime import datetime


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
SERVER_DIR = os.path.dirname(CURRENT_DIR)
if SERVER_DIR not in sys.path:
    sys.path.insert(0, SERVER_DIR)

from conf.logging_config import configure_root_logging
from quant.entities import QUANT_MODELS
from quant.db import init_quant_db
from service.quant.schedule_service import acquire_runnable_runs, enqueue_due_runs, execute_schedule_run


def main():
    configure_root_logging()
    logger = logging.getLogger("quant_scheduler_worker")
    init_quant_db(QUANT_MODELS)
    logger.info("quant scheduler worker started")

    while True:
        loop_started_at = datetime.now()
        try:
            enqueue_due_runs(loop_started_at, lookback_minutes=2)
            runnable = acquire_runnable_runs(limit=20)
            for item in runnable:
                try:
                    logger.info("execute schedule run id=%s, task_type=%s, source=%s", item["id"], item["task_type"], item["trigger_source"])
                    execute_schedule_run(int(item["id"]))
                except Exception as exc:
                    logger.exception("schedule run failed id=%s, err=%s", item["id"], exc)
        except Exception as exc:
            logger.exception("scheduler loop failed: %s", exc)

        sleep_seconds = max(5, 30 - int((datetime.now() - loop_started_at).total_seconds()))
        time.sleep(sleep_seconds)


if __name__ == "__main__":
    main()
