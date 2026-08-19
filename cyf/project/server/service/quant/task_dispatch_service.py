from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional

from quant.db import quant_db
from quant.entities import QuantClientTask, QuantScheduleRun
from quant_client.constants import DEFAULT_TASK_TYPE
from conf.runtime_logging import build_plain_file_handler, run_id_var, task_type_var
from service.quant.schedule_query_service import (
    RUN_STATUS_AWAITING_DATA,
    RUN_STATUS_FAILED,
    RUN_STATUS_SUCCESS,
)


logger = logging.getLogger("quant.task_dispatch")


_DEFAULT_LEASE_SECONDS = 10 * 60


def _now() -> datetime:
    return datetime.now()


def _serialize_task(task: QuantClientTask) -> dict:
    return {
        "task_id": task.task_id,
        "task_type": task.task_type,
        "status": task.status,
        "payload": json.loads(task.payload_json or "{}"),
        "note": task.note,
        "client_id": task.client_id,
        "lease_seconds": task.lease_seconds,
        "attempts": task.attempts,
        "message": task.message,
        "import_batch": json.loads(task.import_batch_json or "{}"),
        "schedule_run_id": task.schedule_run_id,
        "leased_at": task.leased_at.isoformat() if task.leased_at else None,
        "lease_expires_at": task.lease_expires_at.isoformat() if task.lease_expires_at else None,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "finished_at": task.finished_at.isoformat() if task.finished_at else None,
    }


def _recycle_expired_leases(now: Optional[datetime] = None) -> int:
    """把租约已过期的 leased 任务回滚成 pending。"""
    current = now or _now()
    expired = (
        QuantClientTask.select(QuantClientTask.id)
        .where(
            (QuantClientTask.status == "leased")
            & (QuantClientTask.lease_expires_at.is_null(False))
            & (QuantClientTask.lease_expires_at <= current)
        )
    )
    ids = [row.id for row in expired.iterator()]
    if not ids:
        return 0
    updated = (
        QuantClientTask.update(
            {
                QuantClientTask.status: "pending",
                QuantClientTask.leased_at: None,
                QuantClientTask.lease_expires_at: None,
                QuantClientTask.client_id: "",
                QuantClientTask.message: "租约过期，已重新入队",
            }
        )
        .where(QuantClientTask.id.in_(ids))
        .execute()
    )
    return int(updated or 0)


def create_fetch_bars_task(
    symbols: list[str],
    start_date: str,
    end_date: str,
    provider: str = "auto",
    adjust_flag: str = "qfq",
    note: str = "",
    lease_seconds: int = _DEFAULT_LEASE_SECONDS,
    schedule_run_id: Optional[int] = None,
) -> dict:
    task_id = uuid.uuid4().hex
    payload = {
        "provider": provider,
        "symbols": list(symbols or []),
        "start_date": start_date,
        "end_date": end_date,
        "adjust_flag": adjust_flag,
    }
    record = QuantClientTask.create(
        task_id=task_id,
        task_type=DEFAULT_TASK_TYPE,
        status="pending",
        payload_json=json.dumps(payload, ensure_ascii=False),
        note=note,
        lease_seconds=max(60, int(lease_seconds or _DEFAULT_LEASE_SECONDS)),
        attempts=0,
        schedule_run_id=schedule_run_id,
        created_at=_now(),
    )
    logger.info(
        "task_created task_id=%s provider=%s symbols=%s start=%s end=%s lease=%ss schedule_run_id=%s note=%s",
        record.task_id, provider, len(symbols), start_date, end_date,
        record.lease_seconds, schedule_run_id, note,
    )
    return _serialize_task(record)


def list_tasks(limit: int = 100) -> list[dict]:
    _recycle_expired_leases()
    query = QuantClientTask.select().order_by(QuantClientTask.created_at.desc()).limit(limit)
    return [_serialize_task(item) for item in query.iterator()]


def claim_next_task(client_id: str, capabilities: Optional[list[str]] = None) -> Optional[dict]:
    del capabilities  # 当前版本暂不做能力过滤，后续可替换为队列匹配规则。
    current = _now()
    _recycle_expired_leases(current)
    with quant_db.atomic():
        candidate = (
            QuantClientTask.select()
            .where(QuantClientTask.status == "pending")
            .order_by(QuantClientTask.created_at.asc(), QuantClientTask.id.asc())
            .first()
        )
        if not candidate:
            return None
        candidate.status = "leased"
        candidate.client_id = client_id
        candidate.leased_at = current
        candidate.lease_expires_at = current + timedelta(seconds=candidate.lease_seconds)
        candidate.attempts += 1
        candidate.message = "任务已认领"
        candidate.save()
        logger.info(
            "task_claimed task_id=%s client_id=%s lease_expires_at=%s",
            candidate.task_id, client_id, candidate.lease_expires_at.isoformat(),
        )
        return _serialize_task(candidate)


def _get_task_or_raise(task_id: str) -> QuantClientTask:
    task = QuantClientTask.get_or_none(QuantClientTask.task_id == task_id)
    if not task:
        raise ValueError("任务不存在")
    return task


def _append_schedule_run_log(run: QuantScheduleRun, level: int, message: str) -> None:
    """把一行日志追加到 schedule_run 对应的 per-run 日志文件里。

    Agent 上报时已经过了 `schedule_run_log_context`，handler 已被移除——所以这里临时
    构造一个 FileHandler 写到那个文件；并设置好 run_id / task_type context vars，让
    formatter 渲染出和 execute_schedule_run 时一致的格式。

    per-run 日志是"针对本次执行的详细轨迹"，不应受 `runtime_log.level` 全局级别影响——
    所以直接构造 LogRecord 走 handler.handle()，绕过 logger 自身的 setLevel 过滤。
    """
    if not run or not run.log_file:
        return
    scheduler_logger = logging.getLogger("quant.scheduler")
    try:
        handler = build_plain_file_handler(run.log_file, service="quant", level=level)
        run_token = run_id_var.set(str(run.id or ""))
        task_token = task_type_var.set(str(run.task_type or ""))
        try:
            record = scheduler_logger.makeRecord(
                name=scheduler_logger.name,
                level=level,
                fn="",
                lno=0,
                msg=message,
                args=(),
                exc_info=None,
            )
            handler.handle(record)
        finally:
            run_id_var.reset(run_token)
            task_type_var.reset(task_token)
            handler.close()
    except Exception as exc:
        logger.warning(
            "schedule_run_log_append_failed schedule_run_id=%s err=%s",
            run.id, exc,
        )


def _complete_linked_schedule_run(task: QuantClientTask, *, success: bool, message: str) -> Optional[dict]:
    """当任务来自调度器（schedule_run_id 非空）时，把结果回写到 schedule_run。

    只有当 schedule_run 仍处于 awaiting_data 状态时才会改动——避免覆盖手工重跑后的新状态。
    """
    if not task.schedule_run_id:
        return None
    run = QuantScheduleRun.get_or_none(QuantScheduleRun.id == task.schedule_run_id)
    if not run:
        logger.warning(
            "schedule_run_missing task_id=%s schedule_run_id=%s",
            task.task_id, task.schedule_run_id,
        )
        return None
    if run.status != RUN_STATUS_AWAITING_DATA:
        logger.info(
            "schedule_run_skip task_id=%s schedule_run_id=%s current_status=%s reason=not_awaiting_data",
            task.task_id, run.id, run.status,
        )
        return None
    target_status = RUN_STATUS_SUCCESS if success else RUN_STATUS_FAILED
    prefix = "Agent 上报成功" if success else "Agent 上报失败"
    run.status = target_status
    run.message = f"{prefix}：{message or ('任务执行成功' if success else '任务执行失败')}"
    run.finished_at = _now()
    run.next_retry_at = None
    run.save()
    log_level = logging.INFO if success else logging.WARNING
    _append_schedule_run_log(
        run,
        log_level,
        f"agent_report_received task_id={task.task_id} client_id={task.client_id} status={target_status} message={message or ''}",
    )
    logger.info(
        "schedule_run_completed task_id=%s schedule_run_id=%s status=%s",
        task.task_id, run.id, target_status,
    )
    return run.to_dict()


def mark_task_success(task_id: str, client_id: str, import_batch: Optional[dict] = None, message: str = "") -> dict:
    with quant_db.atomic():
        task = _get_task_or_raise(task_id)
        if task.status not in ("leased", "pending"):
            raise ValueError(f"任务当前状态不允许完成: {task.status}")
        if task.client_id and task.client_id != client_id:
            raise ValueError("任务不属于当前客户端")
        task.status = "success"
        task.message = message or "任务执行成功"
        task.import_batch_json = json.dumps(import_batch or {}, ensure_ascii=False)
        task.finished_at = _now()
        task.lease_expires_at = None
        task.save()
        linked_run = _complete_linked_schedule_run(task, success=True, message=task.message)
        logger.info(
            "task_succeeded task_id=%s client_id=%s batch=%s linked_schedule_run_id=%s",
            task.task_id, client_id,
            (import_batch or {}).get("batch_id", "") if isinstance(import_batch, dict) else "",
            linked_run["id"] if linked_run else "",
        )
        return _serialize_task(task)


def mark_task_failed(task_id: str, client_id: str, message: str) -> dict:
    with quant_db.atomic():
        task = _get_task_or_raise(task_id)
        if task.client_id and task.client_id != client_id:
            raise ValueError("任务不属于当前客户端")
        task.status = "failed"
        task.message = message or "任务执行失败"
        task.finished_at = _now()
        task.lease_expires_at = None
        task.save()
        linked_run = _complete_linked_schedule_run(task, success=False, message=task.message)
        logger.warning(
            "task_failed task_id=%s client_id=%s message=%s linked_schedule_run_id=%s",
            task.task_id, client_id, message,
            linked_run["id"] if linked_run else "",
        )
        return _serialize_task(task)


def reset_task(task_id: str) -> dict:
    with quant_db.atomic():
        task = _get_task_or_raise(task_id)
        task.status = "pending"
        task.client_id = ""
        task.leased_at = None
        task.lease_expires_at = None
        task.finished_at = None
        task.message = "任务已重置"
        task.save()
        logger.info("task_reset task_id=%s", task.task_id)
        return _serialize_task(task)