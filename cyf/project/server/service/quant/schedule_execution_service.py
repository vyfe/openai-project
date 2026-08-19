from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta

from quant.entities import QuantPositionJournal, QuantReportRecord, QuantScheduleConfig, QuantScheduleRun
from service.quant.common import normalize_symbol
from service.quant.im_delivery_service import send_position_summary_to_channel, send_report_to_channel
from service.quant.industry_service import collect_industry, get_industry_board, get_industry_dashboard, render_industry_daily_markdown
from service.quant.memory_service import curate_symbol_memories
from service.quant.report_service import create_report_for_run
from service.quant.schedule_log_service import build_schedule_log_path, schedule_run_log_context
from service.quant.schedule_query_service import RUN_STATUS_AWAITING_DATA, RUN_STATUS_FAILED, RUN_STATUS_PENDING, RUN_STATUS_RETRY, RUN_STATUS_RUNNING, RUN_STATUS_SUCCESS
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
    provider = str(payload.get("provider", "auto")).strip() or "auto"
    adjust_flag = str(payload.get("adjust_flag", "qfq")).strip() or "qfq"
    note = str(payload.get("note", "")).strip() or f"schedule:{run.schedule_name}"
    lease_seconds = int(payload.get("lease_seconds", 600) or 600)
    logger.info(
        "data_sync_start run_id=%s schedule_id=%s trade_date=%s symbols=%s window=%s~%s provider=%s adjust=%s",
        run.id, run.schedule_id, run.trade_date, len(normalized_symbols),
        start_date, end_date, provider, adjust_flag,
    )
    task = create_fetch_bars_task(
        symbols=normalized_symbols,
        start_date=start_date,
        end_date=end_date,
        provider=provider,
        adjust_flag=adjust_flag,
        note=note,
        lease_seconds=lease_seconds,
        schedule_run_id=run.id,
    )
    logger.info(
        "data_sync_enqueued run_id=%s task_id=%s symbols=%s window=%s~%s",
        run.id, task.get("task_id"), len(normalized_symbols), start_date, end_date,
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
    logger.info(
        "analysis_report_start run_id=%s trade_date=%s strategy_ids=%s channel_ids=%s save_all_signals=%s",
        run.id, run.trade_date, strategy_ids, channel_ids, save_all_signals,
    )
    results, reports, deliveries = [], [], []
    for raw_strategy_id in strategy_ids:
        strategy_id = int(raw_strategy_id)
        logger.info("analysis_report_strategy run_id=%s strategy_id=%s", run.id, strategy_id)
        strategy_run = run_strategy(strategy_id=strategy_id, trade_date=run.trade_date.isoformat() if run.trade_date else None, save_all_signals=save_all_signals)
        results.append(strategy_run)
        report = create_report_for_run(int(strategy_run["id"]), report_type="test_report", schedule_run_id=run.id)
        reports.append(report)
        logger.info(
            "analysis_report_created run_id=%s strategy_id=%s report_id=%s signals=%s",
            run.id, strategy_id, report.get("id"), strategy_run.get("signals_total"),
        )
        for raw_channel_id in channel_ids:
            deliveries.append(send_report_to_channel(int(report["id"]), channel_id=int(raw_channel_id)))
    user_deliveries = deliver_to_bound_users()
    total_signals = sum(int(item.get("signals_total", 0) or 0) for item in results)
    logger.info(
        "analysis_report_done run_id=%s strategy_count=%s signals_total=%s reports=%s deliveries=%s user_deliveries=%s",
        run.id, len(results), total_signals, len(reports), len(deliveries), len(user_deliveries),
    )
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
    logger.info(
        "memory_digest_start run_id=%s symbols=%s lookback_days=%s limit=%s",
        run.id, symbols if isinstance(symbols, list) else "ALL", lookback_days, limit,
    )
    curated = curate_symbol_memories(symbols=symbols, lookback_days=lookback_days, limit=limit)
    logger.info("memory_digest_done run_id=%s files=%s", run.id, len(curated))
    return {"mode": "local_memory_digest", "lookback_days": lookback_days, "files": curated, "count": len(curated)}


def _payload_list(payload: dict, key: str) -> list:
    value = payload.get(key)
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return [value]


def execute_industry_collect(run: QuantScheduleRun) -> dict:
    payload = json.loads(run.payload_json or "{}")
    targets = _payload_list(payload, "targets") or None
    board_ids = _payload_list(payload, "board_ids")
    board_keys = _payload_list(payload, "board_keys")
    if payload.get("board_id"):
        board_ids.append(payload.get("board_id"))
    if payload.get("board_key"):
        board_keys.append(payload.get("board_key"))
    logger.info(
        "industry_collect_start run_id=%s board_ids=%s board_keys=%s targets=%s",
        run.id, board_ids, board_keys, targets if isinstance(targets, list) else "ALL",
    )
    if not board_ids and not board_keys:
        result = collect_industry(targets=targets)
        logger.info("industry_collect_done run_id=%s boards=1 mode=all", run.id)
        return result
    results = []
    for board_id in board_ids:
        results.append(collect_industry(board_id=int(board_id), targets=targets))
    for board_key in board_keys:
        results.append(collect_industry(board_key=str(board_key), targets=targets))
    logger.info("industry_collect_done run_id=%s boards=%s", run.id, len(results))
    return {"boards": len(results), "results": results}


def execute_industry_report(run: QuantScheduleRun) -> dict:
    payload = json.loads(run.payload_json or "{}")
    board_ids = _payload_list(payload, "board_ids")
    board_keys = _payload_list(payload, "board_keys")
    if payload.get("board_id"):
        board_ids.append(payload.get("board_id"))
    if payload.get("board_key"):
        board_keys.append(payload.get("board_key"))
    channel_ids = _payload_list(payload, "channel_ids")
    logger.info(
        "industry_report_start run_id=%s trade_date=%s board_ids=%s board_keys=%s channel_ids=%s",
        run.id, run.trade_date, board_ids, board_keys, channel_ids,
    )
    reports, deliveries = [], []
    targets = [(int(board_id), "") for board_id in board_ids] + [(None, str(board_key)) for board_key in board_keys]
    for board_id, board_key in targets:
        board = get_industry_board(board_id=board_id, board_key=board_key)
        dashboard = get_industry_dashboard(board_id=board.id)
        markdown = render_industry_daily_markdown(board_id=board.id)
        trade_date = run.trade_date or datetime.now().date()
        report_key = f"industry-{board.board_key}-{trade_date.isoformat()}-{run.id}"
        report = QuantReportRecord.create(
            report_key=report_key,
            strategy_id=0,
            run_id=None,
            schedule_run_id=run.id,
            trade_date=trade_date,
            report_type="industry_daily_report",
            status="success",
            bundle_version="industry-bundle-v1",
            prompt_version="industry-template-v1",
            title=f"{board.name} 行业跟踪日报",
            analysis_bundle_json=json.dumps(dashboard, ensure_ascii=False),
            report_draft_json=json.dumps({"mode": "template", "board_key": board.board_key}, ensure_ascii=False),
            final_markdown=markdown,
            memory_references_json="[]",
            meta_json=json.dumps({"board_id": board.id, "board_key": board.board_key}, ensure_ascii=False),
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        report_dict = report.to_dict()
        reports.append(report_dict)
        logger.info(
            "industry_report_created run_id=%s report_id=%s board_key=%s markdown_len=%s",
            run.id, report.id, board.board_key, len(markdown or ""),
        )
        for raw_channel_id in channel_ids:
            deliveries.append(send_report_to_channel(report.id, channel_id=int(raw_channel_id)))
    logger.info(
        "industry_report_done run_id=%s reports=%s deliveries=%s",
        run.id, len(reports), len(deliveries),
    )
    return {
        "trade_date": run.trade_date.isoformat() if run.trade_date else None,
        "reports": reports,
        "deliveries": deliveries,
        "summary": {
            "report_count": len(reports),
            "delivery_count": len(deliveries),
            "mode": "industry_daily_report",
        },
    }


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
                run.result_json = json.dumps(result, ensure_ascii=False)
                run.status = RUN_STATUS_AWAITING_DATA
                task_id = (result.get("client_task") or {}).get("task_id") or ""
                run.message = f"已下发任务 {task_id}，等待 Agent 上报"
                run.finished_at = None
                run.next_retry_at = None
                run.save()
                logger.info(
                    "schedule run awaiting_data id=%s task_id=%s symbols=%s",
                    run.id, task_id, len((result.get("client_task") or {}).get("payload", {}).get("symbols") or []),
                )
                return run.to_dict()
            elif run.task_type == "analysis_report":
                result = execute_analysis_report(run)
            elif run.task_type == "memory_digest":
                result = execute_memory_digest(run)
            elif run.task_type == "industry_collect":
                result = execute_industry_collect(run)
            elif run.task_type == "industry_report":
                result = execute_industry_report(run)
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
