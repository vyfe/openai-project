from __future__ import annotations

import gzip
import json
import logging
import os
import re
import shutil
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timedelta
from logging.handlers import TimedRotatingFileHandler
from typing import Optional

from conf.runtime import runtime_state


request_id_var: ContextVar[str] = ContextVar("request_id", default="")
user_var: ContextVar[str] = ContextVar("user", default="")
path_var: ContextVar[str] = ContextVar("path", default="")
method_var: ContextVar[str] = ContextVar("method", default="")
status_var: ContextVar[str] = ContextVar("status", default="")
duration_ms_var: ContextVar[str] = ContextVar("duration_ms", default="")
client_ip_var: ContextVar[str] = ContextVar("client_ip", default="")
user_agent_var: ContextVar[str] = ContextVar("user_agent", default="")
run_id_var: ContextVar[str] = ContextVar("run_id", default="")
task_type_var: ContextVar[str] = ContextVar("task_type", default="")

_RUNTIME_ROTATED_LOG_PATTERN = re.compile(r".+\.log\.\d{4}-\d{2}-\d{2}$")
_SCHEDULE_RUN_LOG_PATTERN = re.compile(r"^schedule-run-\d+-\d{8}T\d{6}\.log$")


@dataclass(frozen=True)
class LogSpec:
    service: str
    logger_name: str
    file_name: str
    level: int = logging.INFO
    propagate: bool = False


class ContextLogFilter(logging.Filter):
    def __init__(self, service: str):
        super().__init__()
        self.service = service

    def filter(self, record: logging.LogRecord) -> bool:
        record.service = getattr(record, "service", self.service)
        record.request_id = request_id_var.get("")
        record.user = user_var.get("")
        record.path = path_var.get("")
        record.method = method_var.get("")
        record.status = status_var.get("")
        record.duration_ms = duration_ms_var.get("")
        record.client_ip = client_ip_var.get("")
        record.user_agent = user_agent_var.get("")
        record.run_id = run_id_var.get("")
        record.task_type = task_type_var.get("")
        return True


class TextKvFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        fields = {
            "ts": datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S"),
            "level": record.levelname,
            "service": getattr(record, "service", ""),
            "logger": record.name,
            "pid": record.process,
            "tid": record.thread,
            "request_id": getattr(record, "request_id", ""),
            "user": getattr(record, "user", ""),
            "path": getattr(record, "path", ""),
            "method": getattr(record, "method", ""),
            "status": getattr(record, "status", ""),
            "duration_ms": getattr(record, "duration_ms", ""),
            "client_ip": getattr(record, "client_ip", ""),
            "user_agent": getattr(record, "user_agent", ""),
            "run_id": getattr(record, "run_id", ""),
            "task_type": getattr(record, "task_type", ""),
            "message": super().format(record),
        }
        return " ".join(f"{key}={_safe_text(value)}" for key, value in fields.items())


class CleanTimedRotatingFileHandler(TimedRotatingFileHandler):
    def __init__(self, filename: str, *, backup_count: int, compress_backups: bool, **kwargs):
        self.compress_backups = compress_backups
        super().__init__(filename, backupCount=backup_count, encoding="utf-8", utc=False, **kwargs)


def _safe_text(value) -> str:
    text = "" if value is None else str(value)
    text = text.replace("\n", "\\n").replace("\r", "\\r")
    if not text:
        return '""'
    if any(ch.isspace() for ch in text) or "=" in text or '"' in text:
        return json.dumps(text, ensure_ascii=False)
    return text


def runtime_log_root() -> str:
    root = os.path.abspath(runtime_state.settings.runtime_log_root_dir or os.path.join(runtime_state.settings.base_dir, "logs"))
    os.makedirs(root, exist_ok=True)
    return root


def build_runtime_log_path(service: str, file_name: str) -> str:
    directory = os.path.join(runtime_log_root(), service)
    os.makedirs(directory, exist_ok=True)
    return os.path.join(directory, file_name)


def schedule_run_log_dir() -> str:
    configured = str(runtime_state.settings.quant_schedule_log_dir or "").strip()
    directory = os.path.abspath(configured) if configured else os.path.join(runtime_log_root(), "quant", "runs")
    os.makedirs(directory, exist_ok=True)
    return directory


def build_runtime_handler(service: str, file_name: str, level: Optional[int] = None) -> logging.Handler:
    retention_days = max(1, int(runtime_state.settings.runtime_log_plain_retention_days or 7))
    archive_days = max(retention_days, int(runtime_state.settings.runtime_log_archive_retention_days or 30))
    backup_count = max(archive_days + 2, retention_days + 2)
    handler = CleanTimedRotatingFileHandler(
        build_runtime_log_path(service, file_name),
        when="midnight",
        interval=1,
        backup_count=backup_count,
        compress_backups=bool(runtime_state.settings.runtime_log_compress_backups),
    )
    handler.suffix = "%Y-%m-%d"
    handler.setLevel(level or getattr(logging, str(runtime_state.settings.runtime_log_level or "INFO").upper(), logging.INFO))
    handler.setFormatter(TextKvFormatter("%(message)s"))
    handler.addFilter(ContextLogFilter(service))
    return handler


def build_schedule_run_log_path(run_id: int, started_at: datetime | None = None) -> str:
    current = started_at or datetime.now()
    directory = schedule_run_log_dir()
    filename = f"schedule-run-{int(run_id)}-{current.strftime('%Y%m%dT%H%M%S')}.log"
    return os.path.join(directory, filename)


def cleanup_runtime_logs() -> int:
    removed = 0
    plain_days = max(1, int(runtime_state.settings.runtime_log_plain_retention_days or 7))
    archive_days = max(plain_days, int(runtime_state.settings.runtime_log_archive_retention_days or 30))
    cutoff_plain = datetime.now() - timedelta(days=plain_days)
    cutoff_archive = datetime.now() - timedelta(days=archive_days)
    seen_roots = set()
    for root in (runtime_log_root(), schedule_run_log_dir()):
        if root in seen_roots:
            continue
        seen_roots.add(root)
        for dirpath, _, filenames in os.walk(root):
            for filename in filenames:
                full_path = os.path.join(dirpath, filename)
                if _maybe_archive_runtime_log(full_path, filename, cutoff_plain):
                    removed += 1
                    continue
                if _should_remove_runtime_log(full_path, filename, cutoff_archive):
                    try:
                        os.remove(full_path)
                        removed += 1
                    except OSError:
                        continue
    return removed


def _maybe_archive_runtime_log(full_path: str, filename: str, cutoff_plain: datetime) -> bool:
    if not bool(runtime_state.settings.runtime_log_compress_backups):
        return False
    if not os.path.isfile(full_path):
        return False
    if filename.endswith(".gz"):
        return False
    if not _is_archivable_log_file(filename):
        return False
    if datetime.fromtimestamp(os.path.getmtime(full_path)) >= cutoff_plain:
        return False
    try:
        _gzip_file(full_path)
        return True
    except OSError:
        return False


def _is_archivable_log_file(filename: str) -> bool:
    return bool(_RUNTIME_ROTATED_LOG_PATTERN.match(filename) or _SCHEDULE_RUN_LOG_PATTERN.match(filename))


def _should_remove_runtime_log(full_path: str, filename: str, cutoff_archive: datetime) -> bool:
    if not os.path.isfile(full_path):
        return False
    if not filename.endswith(".gz"):
        return False
    mtime = datetime.fromtimestamp(os.path.getmtime(full_path))
    return mtime < cutoff_archive


def build_plain_file_handler(log_path: str, *, service: str, level: Optional[int] = None) -> logging.Handler:
    os.makedirs(os.path.dirname(os.path.abspath(log_path)), exist_ok=True)
    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setLevel(level or getattr(logging, str(runtime_state.settings.runtime_log_level or "INFO").upper(), logging.INFO))
    handler.setFormatter(TextKvFormatter("%(message)s"))
    handler.addFilter(ContextLogFilter(service))
    return handler


def close_logger_handlers(logger: logging.Logger):
    for handler in list(logger.handlers):
        try:
            handler.close()
        finally:
            logger.removeHandler(handler)


def configure_logger(logger_name: str, service: str, file_name: str, level: Optional[int] = None, propagate: bool = False) -> logging.Logger:
    logger = logging.getLogger(logger_name)
    close_logger_handlers(logger)
    logger.setLevel(level or getattr(logging, str(runtime_state.settings.runtime_log_level or "INFO").upper(), logging.INFO))
    logger.propagate = propagate
    logger.addHandler(build_runtime_handler(service, file_name, level=level))
    return logger


def _gzip_file(file_path: str):
    gz_path = f"{file_path}.gz"
    if os.path.exists(gz_path):
        return
    with open(file_path, "rb") as source, gzip.open(gz_path, "wb") as target:
        shutil.copyfileobj(source, target)
    os.remove(file_path)
