from __future__ import annotations

import json
import time
from datetime import datetime, timedelta
from typing import Optional

from peewee import fn

from quant.db import quant_db
from quant.entities import QuantDailyBar, QuantScheduleConfig, QuantScheduleRun
from service.quant.cron_utils import CronExpression
from service.quant.schedule_log_service import build_schedule_log_path
from service.quant.trade_calendar_service import resolve_trade_date_for_schedule

TASK_TYPE_DATA_SYNC = "data_sync"
TASK_TYPE_ANALYSIS = "analysis_report"
TASK_TYPE_MEMORY_DIGEST = "memory_digest"
SUPPORTED_SCHEDULE_TYPES = {TASK_TYPE_DATA_SYNC, TASK_TYPE_ANALYSIS, TASK_TYPE_MEMORY_DIGEST}
RUN_STATUS_PENDING = "pending"
RUN_STATUS_RUNNING = "running"
RUN_STATUS_SUCCESS = "success"
RUN_STATUS_FAILED = "failed"
RUN_STATUS_SKIPPED = "skipped"
RUN_STATUS_RETRY = "retry_wait"


def normalize_payload(payload) -> dict:
    if payload is None:
        return {}
    if isinstance(payload, str):
        text = payload.strip()
        if not text:
            return {}
        return json.loads(text)
    if isinstance(payload, dict):
        return payload
    raise ValueError("payload 格式不正确")


def to_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in ("true", "1", "yes", "on")


def validate_schedule(task_type: str, cron_expr: str, payload: dict):
    normalized_task_type = str(task_type or "").strip()
    if not normalized_task_type:
        raise ValueError("task_type 不能为空")
    if normalized_task_type not in SUPPORTED_SCHEDULE_TYPES:
        raise ValueError(f"不支持的 task_type: {task_type}")
    CronExpression(cron_expr)
    if normalized_task_type == TASK_TYPE_DATA_SYNC:
        raw_symbols = payload.get("symbols") or []
        if isinstance(raw_symbols, str):
            raw_symbols = [item.strip() for item in raw_symbols.split(",") if item.strip()]
        if not raw_symbols:
            raise ValueError("data_sync 任务至少需要一个 symbol")
    if normalized_task_type == TASK_TYPE_ANALYSIS:
        if not payload.get("strategy_ids"):
            raise ValueError("analysis_report 任务至少需要一个 strategy_id")
    if normalized_task_type == TASK_TYPE_MEMORY_DIGEST:
        lookback_days = int(payload.get("lookback_days", 120) or 120)
        if lookback_days < 1:
            raise ValueError("memory_digest.lookback_days 必须大于 0")


def serialize_schedule(item: QuantScheduleConfig) -> dict:
    payload = item.to_dict()
    payload["cron_preview"] = payload["cron_expr"]
    return payload


def list_schedule_configs(status: Optional[str] = None, task_type: Optional[str] = None) -> list[dict]:
    query = QuantScheduleConfig.select().order_by(QuantScheduleConfig.id.desc())
    if status:
        query = query.where(QuantScheduleConfig.status == status)
    if task_type:
        query = query.where(QuantScheduleConfig.task_type == task_type)
    return [serialize_schedule(item) for item in query.iterator()]


def get_schedule_config(schedule_id: int) -> dict:
    return serialize_schedule(QuantScheduleConfig.get_by_id(schedule_id))


def create_schedule_config(*, name: str, task_type: str, cron_expr: str, payload=None, status: str = "active", market_calendar: str = "A_SHARE", timezone: str = "Asia/Shanghai", retry_max: int = 1, retry_delay_seconds: int = 180, allow_manual_run: bool = True, description: str = "") -> dict:
    if not str(name or "").strip():
        raise ValueError("name 不能为空")
    normalized_payload = normalize_payload(payload)
    validate_schedule(task_type, cron_expr, normalized_payload)
    record = QuantScheduleConfig.create(
        name=str(name or "").strip(),
        task_type=str(task_type).strip(),
        status=str(status or "active").strip() or "active",
        cron_expr=str(cron_expr).strip(),
        market_calendar=str(market_calendar or "A_SHARE").strip() or "A_SHARE",
        timezone=str(timezone or "Asia/Shanghai").strip() or "Asia/Shanghai",
        payload_json=json.dumps(normalized_payload, ensure_ascii=False),
        retry_max=max(0, int(retry_max or 0)),
        retry_delay_seconds=max(30, int(retry_delay_seconds or 180)),
        allow_manual_run=to_bool(allow_manual_run),
        description=str(description or "").strip(),
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    return serialize_schedule(record)


def update_schedule_config(schedule_id: int, **updates) -> dict:
    record = QuantScheduleConfig.get_by_id(schedule_id)
    task_type = str(updates.get("task_type", record.task_type)).strip()
    cron_expr = str(updates.get("cron_expr", record.cron_expr)).strip()
    payload = normalize_payload(updates.get("payload", json.loads(record.payload_json or "{}")))
    validate_schedule(task_type, cron_expr, payload)
    if "name" in updates:
        record.name = str(updates["name"] or "").strip()
    if "task_type" in updates:
        record.task_type = task_type
    if "status" in updates:
        record.status = str(updates["status"] or "active").strip() or "active"
    if "cron_expr" in updates:
        record.cron_expr = cron_expr
    if "market_calendar" in updates:
        record.market_calendar = str(updates["market_calendar"] or "A_SHARE").strip() or "A_SHARE"
    if "timezone" in updates:
        record.timezone = str(updates["timezone"] or "Asia/Shanghai").strip() or "Asia/Shanghai"
    if "payload" in updates:
        record.payload_json = json.dumps(payload, ensure_ascii=False)
    if "retry_max" in updates:
        record.retry_max = max(0, int(updates["retry_max"] or 0))
    if "retry_delay_seconds" in updates:
        record.retry_delay_seconds = max(30, int(updates["retry_delay_seconds"] or 180))
    if "allow_manual_run" in updates:
        record.allow_manual_run = to_bool(updates["allow_manual_run"])
    if "description" in updates:
        record.description = str(updates["description"] or "").strip()
    record.updated_at = datetime.now()
    record.save()
    return serialize_schedule(record)


def delete_schedule_config(schedule_id: int) -> bool:
    record = QuantScheduleConfig.get_by_id(schedule_id)
    with quant_db.atomic():
        QuantScheduleRun.delete().where(QuantScheduleRun.schedule_id == schedule_id).execute()
        record.delete_instance()
    return True


def list_schedule_runs(schedule_id: Optional[int] = None, status: Optional[str] = None, limit: int = 100) -> list[dict]:
    query = QuantScheduleRun.select().order_by(QuantScheduleRun.id.desc())
    if schedule_id:
        query = query.where(QuantScheduleRun.schedule_id == schedule_id)
    if status:
        query = query.where(QuantScheduleRun.status == status)
    query = query.limit(limit)
    return [item.to_dict() for item in query.iterator()]


def get_schedule_run(run_id: int) -> dict:
    return QuantScheduleRun.get_by_id(run_id).to_dict()


def build_run_key(schedule_id: int, scheduled_for: datetime, trigger_source: str) -> str:
    base = scheduled_for.strftime("%Y%m%d%H%M")
    if trigger_source == "manual":
        return f"schedule-{schedule_id}-{base}-manual-{int(time.time())}"
    return f"schedule-{schedule_id}-{base}"


def enqueue_schedule_run(schedule_id: int, *, scheduled_for: datetime, trigger_source: str = "cron", payload_override: Optional[dict] = None, trade_date_override=None, allow_duplicate: bool = False) -> dict:
    schedule = QuantScheduleConfig.get_by_id(schedule_id)
    payload = payload_override if payload_override is not None else json.loads(schedule.payload_json or "{}")
    trade_date = trade_date_override or resolve_trade_date_for_schedule(scheduled_for, schedule.market_calendar)
    run_key = build_run_key(schedule.id, scheduled_for, trigger_source)
    if not allow_duplicate:
        existing = QuantScheduleRun.get_or_none(QuantScheduleRun.run_key == run_key)
        if existing:
            return existing.to_dict()
    record = QuantScheduleRun.create(
        schedule_id=schedule.id,
        schedule_name=schedule.name,
        task_type=schedule.task_type,
        run_key=run_key,
        trigger_source=trigger_source,
        status=RUN_STATUS_PENDING,
        scheduled_for=scheduled_for.replace(second=0, microsecond=0),
        trade_date=trade_date,
        attempts=0,
        max_retries=schedule.retry_max,
        payload_json=json.dumps(payload, ensure_ascii=False),
        created_at=datetime.now(),
    )
    record.log_file = build_schedule_log_path(record.id, scheduled_for)
    record.save()
    return record.to_dict()


def manual_trigger_schedule(schedule_id: int) -> dict:
    schedule = QuantScheduleConfig.get_by_id(schedule_id)
    if not schedule.allow_manual_run:
        raise ValueError("当前调度配置不允许手工重跑")
    return enqueue_schedule_run(schedule_id, scheduled_for=datetime.now(), trigger_source="manual", allow_duplicate=True)


def reset_schedule_run(run_id: int, *, allow_success: bool = False) -> dict:
    run = QuantScheduleRun.get_by_id(run_id)
    allowed_statuses = {RUN_STATUS_FAILED, RUN_STATUS_RETRY, RUN_STATUS_SKIPPED}
    if allow_success:
        allowed_statuses.add(RUN_STATUS_SUCCESS)
    if run.status not in allowed_statuses:
        raise ValueError(f"当前 run 状态不支持重置: {run.status}")
    run.status = RUN_STATUS_PENDING
    run.message = "已重置，等待重新执行"
    run.result_json = "{}"
    run.next_retry_at = None
    run.attempts = 0
    run.started_at = None
    run.finished_at = None
    run.save()
    return run.to_dict()


def get_scheduler_overview() -> dict:
    latest_run = QuantScheduleRun.select().order_by(QuantScheduleRun.id.desc()).first()
    active_count = QuantScheduleConfig.select().where(QuantScheduleConfig.status == "active").count()
    failed_count = QuantScheduleRun.select().where(QuantScheduleRun.status == RUN_STATUS_FAILED).count()
    pending_count = QuantScheduleRun.select().where(QuantScheduleRun.status.in_([RUN_STATUS_PENDING, RUN_STATUS_RETRY])).count()
    return {
        "active_configs": active_count,
        "pending_runs": pending_count,
        "failed_runs": failed_count,
        "latest_run": latest_run.to_dict() if latest_run else None,
    }


def enqueue_due_runs(now_dt: Optional[datetime] = None, lookback_minutes: int = 0) -> list[dict]:
    current = (now_dt or datetime.now()).replace(second=0, microsecond=0)
    created = []
    minutes = max(0, int(lookback_minutes or 0))
    candidates = [current - timedelta(minutes=offset) for offset in range(minutes, -1, -1)]
    schedules = list(QuantScheduleConfig.select().where(QuantScheduleConfig.status == "active"))
    for schedule in schedules:
        cron = CronExpression(schedule.cron_expr)
        for candidate in candidates:
            if not cron.matches(candidate):
                continue
            trade_date = resolve_trade_date_for_schedule(candidate, schedule.market_calendar)
            if candidate.date() != trade_date:
                continue
            created.append(enqueue_schedule_run(schedule.id, scheduled_for=candidate, trigger_source="compensation" if candidate != current else "cron", trade_date_override=trade_date, allow_duplicate=False))
    return created


def acquire_runnable_runs(limit: int = 10) -> list[dict]:
    now = datetime.now()
    query = (
        QuantScheduleRun.select()
        .where(((QuantScheduleRun.status == RUN_STATUS_PENDING) & (QuantScheduleRun.scheduled_for <= now)) | ((QuantScheduleRun.status == RUN_STATUS_RETRY) & (QuantScheduleRun.next_retry_at <= now)))
        .order_by(QuantScheduleRun.scheduled_for.asc(), QuantScheduleRun.id.asc())
        .limit(limit)
    )
    return [item.to_dict() for item in query.iterator()]


def latest_market_data_date() -> Optional[str]:
    latest_day = QuantDailyBar.select(fn.MAX(QuantDailyBar.trade_date)).scalar()
    return latest_day.isoformat() if latest_day else None
