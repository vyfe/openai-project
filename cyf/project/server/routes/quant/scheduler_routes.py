import json

from flask import Blueprint, request

from dto.common import error_response, get_request_data, success_response
from service.auth_service import require_admin_auth, require_auth
from service.quant.schedule_service import (
    TASK_TYPE_ANALYSIS,
    TASK_TYPE_DATA_SYNC,
    TASK_TYPE_MEMORY_DIGEST,
    available_strategy_options,
    create_schedule_config,
    delete_schedule_config,
    enqueue_due_runs,
    execute_schedule_run,
    get_schedule_config,
    get_schedule_run,
    get_scheduler_overview,
    latest_market_data_date,
    list_schedule_configs,
    list_schedule_runs,
    manual_trigger_schedule,
    reset_schedule_run,
    update_schedule_config,
)
from service.quant.schedule_log_service import read_schedule_run_log_tail


bp = Blueprint("quant_scheduler_routes", __name__)


@bp.route("/scheduler/meta", methods=["GET"])
@require_auth
def quant_scheduler_meta(user, password):
    del user, password
    return success_response(
        data={
            "task_types": [TASK_TYPE_DATA_SYNC, TASK_TYPE_ANALYSIS, TASK_TYPE_MEMORY_DIGEST],
            "market_calendars": ["A_SHARE"],
            "strategy_options": available_strategy_options(),
            "latest_market_data_date": latest_market_data_date(),
            "overview": get_scheduler_overview(),
        }
    )


@bp.route("/scheduler/overview", methods=["GET"])
@require_auth
def quant_scheduler_overview(user, password):
    del user, password
    return success_response(data=get_scheduler_overview())


@bp.route("/scheduler/configs", methods=["GET"])
@require_auth
def quant_scheduler_configs(user, password):
    del user, password
    status = str(request.args.get("status", "")).strip() or None
    task_type = str(request.args.get("task_type", "")).strip() or None
    return success_response(data=list_schedule_configs(status=status, task_type=task_type))


@bp.route("/scheduler/config/<int:schedule_id>", methods=["GET"])
@require_auth
def quant_scheduler_config_get(user, password, schedule_id):
    del user, password
    try:
        return success_response(data=get_schedule_config(schedule_id))
    except Exception as exc:
        return error_response(f"获取调度配置失败: {exc}")


@bp.route("/scheduler/config/create", methods=["POST"])
@require_admin_auth
def quant_scheduler_config_create():
    try:
        data = get_request_data()
        payload = data.get("payload")
        if isinstance(payload, str):
            payload = json.loads(payload)
        result = create_schedule_config(
            name=str(data.get("name", "")).strip(),
            task_type=str(data.get("task_type", "")).strip(),
            cron_expr=str(data.get("cron_expr", "")).strip(),
            payload=payload,
            status=str(data.get("status", "active")).strip() or "active",
            market_calendar=str(data.get("market_calendar", "A_SHARE")).strip() or "A_SHARE",
            timezone=str(data.get("timezone", "Asia/Shanghai")).strip() or "Asia/Shanghai",
            retry_max=int(data.get("retry_max", 1) or 1),
            retry_delay_seconds=int(data.get("retry_delay_seconds", 180) or 180),
            allow_manual_run=str(data.get("allow_manual_run", "true")).lower() in ("true", "1", "yes"),
            description=str(data.get("description", "")).strip(),
        )
        return success_response(data=result, msg="调度配置创建成功")
    except Exception as exc:
        return error_response(f"创建调度配置失败: {exc}")


@bp.route("/scheduler/config/update", methods=["POST"])
@require_admin_auth
def quant_scheduler_config_update():
    try:
        data = get_request_data()
        schedule_id = int(data.get("id"))
        updates = {}
        for key in ("name", "task_type", "cron_expr", "status", "market_calendar", "timezone", "retry_max", "retry_delay_seconds", "allow_manual_run", "description"):
            if key in data:
                updates[key] = data.get(key)
        if "payload" in data:
            payload = data.get("payload")
            if isinstance(payload, str):
                payload = json.loads(payload)
            updates["payload"] = payload
        result = update_schedule_config(schedule_id, **updates)
        return success_response(data=result, msg="调度配置更新成功")
    except Exception as exc:
        return error_response(f"更新调度配置失败: {exc}")


@bp.route("/scheduler/config/delete", methods=["POST"])
@require_admin_auth
def quant_scheduler_config_delete():
    try:
        data = get_request_data()
        delete_schedule_config(int(data.get("id")))
        return success_response(msg="调度配置删除成功")
    except Exception as exc:
        return error_response(f"删除调度配置失败: {exc}")


@bp.route("/scheduler/runs", methods=["GET"])
@require_auth
def quant_scheduler_runs(user, password):
    del user, password
    schedule_id = request.args.get("schedule_id", type=int)
    status = str(request.args.get("status", "")).strip() or None
    limit = request.args.get("limit", default=100, type=int) or 100
    limit = max(1, min(limit, 300))
    return success_response(data=list_schedule_runs(schedule_id=schedule_id, status=status, limit=limit))


@bp.route("/scheduler/run/<int:run_id>", methods=["GET"])
@require_auth
def quant_scheduler_run_get(user, password, run_id):
    del user, password
    try:
        record = get_schedule_run(run_id)
        record["log_tail"] = read_schedule_run_log_tail(record.get("log_file", ""), limit_lines=200)
        return success_response(data=record)
    except Exception as exc:
        return error_response(f"获取调度执行记录失败: {exc}")


@bp.route("/scheduler/run/<int:run_id>/log", methods=["GET"])
@require_auth
def quant_scheduler_run_log(user, password, run_id):
    del user, password
    try:
        limit_lines = request.args.get("limit", default=200, type=int) or 200
        record = get_schedule_run(run_id)
        return success_response(
            data={
                "run_id": run_id,
                "log_file": record.get("log_file", ""),
                "log_tail": read_schedule_run_log_tail(record.get("log_file", ""), limit_lines=limit_lines),
            }
        )
    except Exception as exc:
        return error_response(f"获取调度日志失败: {exc}")


@bp.route("/scheduler/manual_run", methods=["POST"])
@require_admin_auth
def quant_scheduler_manual_run():
    try:
        data = get_request_data()
        schedule_id = int(data.get("schedule_id"))
        result = manual_trigger_schedule(schedule_id)
        return success_response(data=result, msg="已创建手工执行任务")
    except Exception as exc:
        return error_response(f"手工触发调度失败: {exc}")


@bp.route("/scheduler/rebuild_due_runs", methods=["POST"])
@require_admin_auth
def quant_scheduler_rebuild_due_runs():
    try:
        data = get_request_data()
        lookback_minutes = int(data.get("lookback_minutes", 60) or 60)
        result = enqueue_due_runs(lookback_minutes=lookback_minutes)
        return success_response(data=result, msg="补偿执行记录已生成")
    except Exception as exc:
        return error_response(f"生成补偿执行记录失败: {exc}")


@bp.route("/scheduler/execute_run", methods=["POST"])
@require_admin_auth
def quant_scheduler_execute_run():
    try:
        data = get_request_data()
        run_id = int(data.get("run_id"))
        result = execute_schedule_run(run_id)
        return success_response(data=result, msg="调度任务执行成功")
    except Exception as exc:
        return error_response(f"执行调度任务失败: {exc}")


@bp.route("/scheduler/reset_run", methods=["POST"])
@require_admin_auth
def quant_scheduler_reset_run():
    try:
        data = get_request_data()
        run_id = int(data.get("run_id"))
        allow_success = str(data.get("allow_success", "false")).strip().lower() in ("true", "1", "yes")
        result = reset_schedule_run(run_id, allow_success=allow_success)
        return success_response(data=result, msg="调度执行记录已重置")
    except Exception as exc:
        return error_response(f"重置调度执行记录失败: {exc}")
