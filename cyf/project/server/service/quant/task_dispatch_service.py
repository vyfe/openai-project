from __future__ import annotations

import threading
import uuid
from collections import OrderedDict
from datetime import datetime, timedelta
from typing import Optional

from quant_client.constants import DEFAULT_TASK_TYPE


_TASK_LOCK = threading.Lock()
_TASKS: "OrderedDict[str, dict]" = OrderedDict()
_DEFAULT_LEASE_SECONDS = 10 * 60


def _now() -> datetime:
    return datetime.now()


def _serialize_task(task: dict) -> dict:
    data = dict(task)
    for key in ("created_at", "leased_at", "lease_expires_at", "finished_at"):
        value = data.get(key)
        data[key] = value.isoformat() if isinstance(value, datetime) else None
    return data


def _recycle_expired_leases(now: Optional[datetime] = None):
    current = now or _now()
    for task in _TASKS.values():
        if task["status"] == "leased" and task.get("lease_expires_at") and task["lease_expires_at"] <= current:
            task["status"] = "pending"
            task["leased_at"] = None
            task["lease_expires_at"] = None
            task["client_id"] = ""
            task["message"] = "租约过期，已重新入队"


def create_fetch_bars_task(
    symbols: list[str],
    start_date: str,
    end_date: str,
    provider: str = "auto",
    adjust_flag: str = "qfq",
    note: str = "",
    lease_seconds: int = _DEFAULT_LEASE_SECONDS,
) -> dict:
    task_id = uuid.uuid4().hex
    task = {
        "task_id": task_id,
        "task_type": DEFAULT_TASK_TYPE,
        "status": "pending",
        "payload": {
            "provider": provider,
            "symbols": symbols,
            "start_date": start_date,
            "end_date": end_date,
            "adjust_flag": adjust_flag,
        },
        "note": note,
        "client_id": "",
        "lease_seconds": max(60, int(lease_seconds or _DEFAULT_LEASE_SECONDS)),
        "attempts": 0,
        "message": "",
        "import_batch": None,
        "created_at": _now(),
        "leased_at": None,
        "lease_expires_at": None,
        "finished_at": None,
    }
    with _TASK_LOCK:
        _TASKS[task_id] = task
    return _serialize_task(task)


def list_tasks(limit: int = 100) -> list[dict]:
    with _TASK_LOCK:
        _recycle_expired_leases()
        items = list(_TASKS.values())[-limit:]
        return [_serialize_task(item) for item in reversed(items)]


def claim_next_task(client_id: str, capabilities: Optional[list[str]] = None) -> Optional[dict]:
    del capabilities  # 当前版本暂不做能力过滤，后续可替换为队列匹配规则。
    with _TASK_LOCK:
        current = _now()
        _recycle_expired_leases(current)
        for task in _TASKS.values():
            if task["status"] != "pending":
                continue
            task["status"] = "leased"
            task["client_id"] = client_id
            task["leased_at"] = current
            task["lease_expires_at"] = current + timedelta(seconds=task["lease_seconds"])
            task["attempts"] += 1
            task["message"] = "任务已认领"
            return _serialize_task(task)
    return None


def mark_task_success(task_id: str, client_id: str, import_batch: Optional[dict] = None, message: str = "") -> dict:
    with _TASK_LOCK:
        task = _TASKS.get(task_id)
        if not task:
            raise ValueError("任务不存在")
        if task["status"] not in ("leased", "pending"):
            raise ValueError(f"任务当前状态不允许完成: {task['status']}")
        if task["client_id"] and task["client_id"] != client_id:
            raise ValueError("任务不属于当前客户端")
        task["status"] = "success"
        task["message"] = message or "任务执行成功"
        task["import_batch"] = import_batch
        task["finished_at"] = _now()
        task["lease_expires_at"] = None
        return _serialize_task(task)


def mark_task_failed(task_id: str, client_id: str, message: str) -> dict:
    with _TASK_LOCK:
        task = _TASKS.get(task_id)
        if not task:
            raise ValueError("任务不存在")
        if task["client_id"] and task["client_id"] != client_id:
            raise ValueError("任务不属于当前客户端")
        task["status"] = "failed"
        task["message"] = message or "任务执行失败"
        task["finished_at"] = _now()
        task["lease_expires_at"] = None
        return _serialize_task(task)


def reset_task(task_id: str) -> dict:
    with _TASK_LOCK:
        task = _TASKS.get(task_id)
        if not task:
            raise ValueError("任务不存在")
        task["status"] = "pending"
        task["client_id"] = ""
        task["leased_at"] = None
        task["lease_expires_at"] = None
        task["finished_at"] = None
        task["message"] = "任务已重置"
        return _serialize_task(task)

