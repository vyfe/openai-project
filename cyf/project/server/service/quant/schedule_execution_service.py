from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta

from quant.entities import QuantPositionJournal, QuantScheduleConfig, QuantScheduleRun
from service.quant.common import normalize_symbol
from service.quant.im_delivery_service import send_position_summary_to_channel, send_report_to_channel
from service.quant.memory_service import curate_symbol_memories
from service.quant.report_service import create_report_for_run
from service.quant.schedule_log_service import build_schedule_log_path, schedule_run_log_context
from service.quant.schedule_query_service import RUN_STATUS_FAILED, RUN_STATUS_PENDING, RUN_STATUS_RETRY, RUN_STATUS_RUNNING, RUN_STATUS_SUCCESS
from service.quant.strategy_service import list_strategies, run_strategy
from service.quant.task_dispatch_service import create_fetch_bars_task
from service.quant.trade_calendar_service import shift_trade_day

logger = logging.getLogger("quant.scheduler")


def available_strategy_options() -> list[dict]:
    return [{"id": item["id"], "name": item["name"], "status": item["status"]} for item in list_strategies()]


def collect_active_user_symbols() -> list[str]:
    symbols = set()
    for entry in QuantPositionJournal.select(QuantPositionJournal.symbol).distinct():
        sym = str(entry.symbol or "").strip()
        if sym:
            symbols.add(sym)
    return sorted(symbols)


def resolve_fetch_window(payload: dict, trade_date) -> tuple[str, str]:
    if payload.get("start_date") and payload.get("end_date"):
        return str(payload["start_date"]), str(payload["end_date"])
    lookback_trade_days = max(1, int(payload.get("lookback_trade_days", 20) or 20))
    start_day = shift_trade_day(trade_date, -(lookback_trade_days - 1), "A_SHARE")
    return start_day.isoformat(), trade_date.isoformat()


def execute_data_sync(run: QuantScheduleRun) -> dict:
    payload = json.loads(run.payload_json or "{}")
    symbols = payload.get("symbols") or []
    if isinstance(symbols, str):
        symbols = [item.strip() for item in symbols.split(",") if item.strip()]
    for sym in collect_active_user_symbols():
        if sym not in symbols:
            symbols.append(sym)
    for idx in ["000001.SH", "399001.SZ", "399006.SZ", "000688.SH", "000300.SH"]:
        if idx not in symbols:
            symbols.append(idx)
    normalized_symbols = [normalize_symbol(item) for item in symbols]
    start_date, end_date = resolve_fetch_window(payload, run.trade_date)
    task = create_fetch_bars_task(
        symbols=normalized_symbols,
        start_date=start_date,
        end_date=end_date,
        provider=str(payload.get("provider", "auto")).strip() or "auto",
        adjust_flag=str(payload.get("adjust_flag", "qfq")).strip() or "qfq",
        note=str(payload.get("note", "")).strip() or f"schedule:{run.schedule_name}",
        lease_seconds=int(payload.get("lease_seconds", 600) or 600),
    )
    return {"client_task": task, "window": {"start_date": start_date, "end_date": end_date}}


def deliver_to_bound_users() -> list[dict]:
    from service.quant.binding_service import list_all_bindings
    from service.quant.position_service import list_position_summary

    bindings = list_all_bindings()
    if not bindings:
        return []
    results = []
    for binding in bindings:
        username = binding["username"]
        try:
            positions = list_position_summary(created_by=username)
            if not positions:
                continue
            delivery = send_position_summary_to_channel(channel_id=None, strategy_id=None)
            delivery["target_user"] = username
            results.append(delivery)
        except Exception as exc:
            results.append({"target_user": username, "error": str(exc)})
    return results


def execute_analysis_report(run: QuantScheduleRun) -> dict:
    payload = json.loads(run.payload_json or "{}")
    strategy_ids = payload.get("strategy_ids") or []
    channel_ids = payload.get("channel_ids") or []
    if isinstance(strategy_ids, str):
        strategy_ids = [item.strip() for item in strategy_ids.split(",") if item.strip()]
    if isinstance(channel_ids, str):
        channel_ids = [item.strip() for item in channel_ids.split(",") if item.strip()]
    save_all_signals = str(payload.get("save_all_signals", True)).strip().lower() in ("true", "1", "yes", "on")
    results, reports, deliveries = [], [], []
    for raw_strategy_id in strategy_ids:
        strategy_id = int(raw_strategy_id)
        strategy_run = run_strategy(strategy_id=strategy_id, trade_date=run.trade_date.isoformat() if run.trade_date else None, save_all_signals=save_all_signals)
        results.append(strategy_run)
        report = create_report_for_run(int(strategy_run["id"]), report_type="test_report", schedule_run_id=run.id)
        reports.append(report)
        for raw_channel_id in channel_ids:
            deliveries.append(send_report_to_channel(int(report["id"]), channel_id=int(raw_channel_id)))
    user_deliveries = deliver_to_bound_users()
    total_signals = sum(int(item.get("signals_total", 0) or 0) for item in results)
    return {
        "trade_date": run.trade_date.isoformat() if run.trade_date else None,
        "strategy_runs": results,
        "reports": reports,
        "deliveries": deliveries,
        "user_deliveries": user_deliveries,
        "summary": {
            "strategy_count": len(results),
            "signals_total": total_signals,
            "mode": "test_report",
            "delivery_count": len(deliveries),
            "user_delivery_count": len(user_deliveries),
        },
    }


def execute_memory_digest(run: QuantScheduleRun) -> dict:
    payload = json.loads(run.payload_json or "{}")
    symbols = payload.get("symbols")
    lookback_days = max(1, int(payload.get("lookback_days", 120) or 120))
    limit = max(1, int(payload.get("limit", 50) or 50))
    curated = curate_symbol_memories(symbols=symbols, lookback_days=lookback_days, limit=limit)
    return {"mode": "local_memory_digest", "lookback_days": lookback_days, "files": curated, "count": len(curated)}


def execute_schedule_run(run_id: int) -> dict:
    run = QuantScheduleRun.get_by_id(run_id)
    if run.status not in (RUN_STATUS_PENDING, RUN_STATUS_RETRY):
        raise ValueError(f"当前 run 状态不允许执行: {run.status}")
    run.status = RUN_STATUS_RUNNING
    run.started_at = datetime.now()
    run.attempts += 1
    if not run.log_file:
        run.log_file = build_schedule_log_path(run.id, run.started_at)
    run.save()
    try:
        with schedule_run_log_context(logger, run.log_file, run_id=run.id, task_type=run.task_type):
            logger.info("schedule run start id=%s task_type=%s log_file=%s", run.id, run.task_type, run.log_file)
            if run.task_type == "data_sync":
                result = execute_data_sync(run)
            elif run.task_type == "analysis_report":
                result = execute_analysis_report(run)
            elif run.task_type == "memory_digest":
                result = execute_memory_digest(run)
            else:
                raise ValueError(f"不支持的调度任务类型: {run.task_type}")
            run.status = RUN_STATUS_SUCCESS
            run.message = "执行成功"
            run.result_json = json.dumps(result, ensure_ascii=False)
            run.next_retry_at = None
            run.finished_at = datetime.now()
            run.save()
            logger.info("schedule run success id=%s", run.id)
            return run.to_dict()
    except Exception as exc:
        logger.exception("schedule run failed id=%s", run.id)
        run.message = str(exc)
        if run.attempts <= run.max_retries:
            run.status = RUN_STATUS_RETRY
            retry_delay = QuantScheduleConfig.get_by_id(run.schedule_id).retry_delay_seconds
            run.next_retry_at = datetime.now() + timedelta(seconds=retry_delay)
            run.finished_at = datetime.now()
            run.save()
        else:
            run.status = RUN_STATUS_FAILED
            run.finished_at = datetime.now()
            run.save()
        raise
