from __future__ import annotations

import logging
import sys
import threading
import time
import uuid
from typing import Optional

from flask import Flask, g, request

from conf.runtime import runtime_state
from conf.runtime_logging import (
    client_ip_var,
    cleanup_runtime_logs,
    configure_logger,
    duration_ms_var,
    method_var,
    path_var,
    request_id_var,
    status_var,
    user_agent_var,
    user_var,
)


_LOG_MAINTENANCE_THREAD: Optional[threading.Thread] = None
_LOG_MAINTENANCE_STOP = threading.Event()


def _runtime_level() -> int:
    return getattr(logging, str(runtime_state.settings.runtime_log_level or "INFO").upper(), logging.INFO)


def _configure_root_logger():
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(logging.WARNING)
    stream_handler = logging.StreamHandler(stream=sys.stderr)
    stream_handler.setLevel(logging.WARNING)
    root_logger.addHandler(stream_handler)


def _configure_named_loggers():
    configure_logger("llm.web", "llm", "app.log", level=_runtime_level())
    configure_logger("llm.access", "llm", "access.log", level=_runtime_level())
    configure_logger("quant", "quant", "web.log", level=_runtime_level())
    logging.getLogger("quant").propagate = False
    configure_logger("quant.access", "quant", "access.log", level=_runtime_level())
    configure_logger("quant.scheduler", "quant", "scheduler.log", level=_runtime_level())
    configure_logger("quant.client", "quant", "client.log", level=_runtime_level())
    configure_logger("ops.archive", "ops", "archive.log", level=_runtime_level())
    configure_logger("ops.restore", "ops", "restore.log", level=_runtime_level())


def _bind_app_logger(app: Flask):
    llm_logger = logging.getLogger("llm.web")
    app_logger = app.logger
    app_logger.handlers.clear()
    app_logger.setLevel(llm_logger.level)
    for handler in llm_logger.handlers:
        app_logger.addHandler(handler)
    app_logger.propagate = False
    app_logger.name = "llm.web"


def _clear_request_context():
    request_id_var.set("")
    user_var.set("")
    path_var.set("")
    method_var.set("")
    status_var.set("")
    duration_ms_var.set("")
    client_ip_var.set("")
    user_agent_var.set("")


def set_log_user(username: str | None):
    user_var.set(str(username or ""))


def configure_logging(app: Flask, debug: bool = False):
    del debug
    _configure_root_logger()
    _configure_named_loggers()
    _bind_app_logger(app)
    cleanup_runtime_logs()
    _register_request_logging(app)
    _start_log_maintenance_thread()
    return app.logger


def configure_root_logging(debug: bool = True):
    del debug
    _configure_root_logger()
    _configure_named_loggers()
    cleanup_runtime_logs()
    return logging.getLogger()


def _register_request_logging(app: Flask):
    @app.before_request
    def _before_request_logging():
        g.request_started_at = time.time()
        request_id = request.headers.get("X-Request-Id", "").strip() or uuid.uuid4().hex
        request_id_var.set(request_id)
        path_var.set(request.path or "")
        method_var.set(request.method or "")
        status_var.set("")
        duration_ms_var.set("")
        user_var.set("")
        client_ip_var.set(request.headers.get("X-Forwarded-For", request.remote_addr or "").split(",")[0].strip())
        user_agent_var.set(request.headers.get("User-Agent", ""))
        g.request_id = request_id

    @app.after_request
    def _after_request_logging(response):
        response.headers["X-Request-Id"] = getattr(g, "request_id", "")
        if request.method != "OPTIONS" and request.path not in ("/", "") and not request.path.startswith("/static") and request.path != "/never_guess_my_usage/test":
            duration_ms = int((time.time() - getattr(g, "request_started_at", time.time())) * 1000)
            status_var.set(str(response.status_code))
            duration_ms_var.set(str(duration_ms))
            logger_name = "quant.access" if request.path.startswith("/never_guess_my_usage/quant") else "llm.access"
            access_logger = logging.getLogger(logger_name)
            access_logger.info("request_completed")
        _clear_request_context()
        return response


def _start_log_maintenance_thread():
    global _LOG_MAINTENANCE_THREAD
    if _LOG_MAINTENANCE_THREAD and _LOG_MAINTENANCE_THREAD.is_alive():
        return

    def _loop():
        while not _LOG_MAINTENANCE_STOP.is_set():
            try:
                cleanup_runtime_logs()
            except Exception:
                logging.getLogger("llm.web").exception("runtime log cleanup failed")
            _LOG_MAINTENANCE_STOP.wait(timeout=6 * 60 * 60)

    _LOG_MAINTENANCE_THREAD = threading.Thread(target=_loop, name="runtime-log-maintenance", daemon=True)
    _LOG_MAINTENANCE_THREAD.start()
