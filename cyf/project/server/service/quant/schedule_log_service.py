from __future__ import annotations

import logging
import os
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from datetime import datetime

from conf.runtime_logging import build_plain_file_handler, build_schedule_run_log_path, cleanup_runtime_logs, run_id_var, task_type_var


def build_schedule_log_path(run_id: int, started_at: datetime | None = None) -> str:
    return build_schedule_run_log_path(run_id, started_at=started_at)


@contextmanager
def schedule_run_log_context(logger: logging.Logger, log_path: str, *, run_id: int | None = None, task_type: str | None = None):
    handler = build_plain_file_handler(log_path, service="quant", level=logging.INFO)
    run_token = run_id_var.set(str(run_id or ""))
    task_token = task_type_var.set(str(task_type or ""))
    logger.addHandler(handler)
    try:
        with open(log_path, "a", encoding="utf-8") as log_stream:
            with redirect_stdout(log_stream), redirect_stderr(log_stream):
                yield handler
    finally:
        logger.removeHandler(handler)
        handler.close()
        run_id_var.reset(run_token)
        task_type_var.reset(task_token)


def cleanup_expired_schedule_logs(retention_days: int | None = None) -> int:
    del retention_days
    return cleanup_runtime_logs()


def read_schedule_run_log_tail(log_path: str, limit_lines: int = 200) -> str:
    if not log_path or not os.path.exists(log_path):
        return ""
    limit = max(1, int(limit_lines or 200))
    with open(log_path, "r", encoding="utf-8", errors="ignore") as fp:
        lines = fp.readlines()
    return "".join(lines[-limit:])
