import json

from flask import Blueprint, request

from dto.common import error_response, get_request_data, parse_json_list, success_response
from service.auth_service import require_admin_auth, require_auth
from service.quant.backtest_service import delete_backtest_run, get_backtest_run, list_backtest_runs, run_backtest
from service.quant.dashboard_service import get_dashboard_overview
from service.quant.import_service import fetch_import_batches, import_bundle, parse_bundle_bytes
from service.quant.ops_service import (
    create_operation_record,
    delete_operation_record,
    get_operation_record,
    list_operation_records,
    update_operation_record,
)
from service.quant.provider_factory import list_supported_providers
from service.quant.query_service import fetch_daily_bars
from service.quant.schedule_service import (
    TASK_TYPE_ANALYSIS,
    TASK_TYPE_DATA_SYNC,
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
    update_schedule_config,
)
from service.quant.strategy_service import (
    create_strategy,
    delete_strategy,
    get_strategy,
    list_available_symbols,
    list_strategies,
    list_strategy_runs,
    list_strategy_signals,
    run_strategy,
    update_strategy,
)
from service.quant.task_dispatch_service import (
    claim_next_task,
    create_fetch_bars_task,
    list_tasks,
    mark_task_failed,
    mark_task_success,
    reset_task,
)


quant_bp = Blueprint("quant_routes", __name__, url_prefix="/never_guess_my_usage/quant")


@quant_bp.route("/dashboard/overview", methods=["GET"])
@require_auth
def quant_dashboard_overview(user, password):
    del user, password
    return success_response(data=get_dashboard_overview())


@quant_bp.route("/scheduler/meta", methods=["GET"])
@require_auth
def quant_scheduler_meta(user, password):
    del user, password
    return success_response(
        data={
            "task_types": [TASK_TYPE_DATA_SYNC, TASK_TYPE_ANALYSIS],
            "market_calendars": ["A_SHARE"],
            "strategy_options": available_strategy_options(),
            "latest_market_data_date": latest_market_data_date(),
            "overview": get_scheduler_overview(),
        }
    )


@quant_bp.route("/scheduler/overview", methods=["GET"])
@require_auth
def quant_scheduler_overview(user, password):
    del user, password
    return success_response(data=get_scheduler_overview())


@quant_bp.route("/scheduler/configs", methods=["GET"])
@require_auth
def quant_scheduler_configs(user, password):
    del user, password
    status = str(request.args.get("status", "")).strip() or None
    task_type = str(request.args.get("task_type", "")).strip() or None
    return success_response(data=list_schedule_configs(status=status, task_type=task_type))


@quant_bp.route("/scheduler/config/<int:schedule_id>", methods=["GET"])
@require_auth
def quant_scheduler_config_get(user, password, schedule_id):
    del user, password
    try:
        return success_response(data=get_schedule_config(schedule_id))
    except Exception as exc:
        return error_response(f"获取调度配置失败: {exc}")


@quant_bp.route("/scheduler/config/create", methods=["POST"])
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


@quant_bp.route("/scheduler/config/update", methods=["POST"])
@require_admin_auth
def quant_scheduler_config_update():
    try:
        data = get_request_data()
        schedule_id = int(data.get("id"))
        updates = {}
        for key in (
            "name",
            "task_type",
            "cron_expr",
            "status",
            "market_calendar",
            "timezone",
            "retry_max",
            "retry_delay_seconds",
            "allow_manual_run",
            "description",
        ):
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


@quant_bp.route("/scheduler/config/delete", methods=["POST"])
@require_admin_auth
def quant_scheduler_config_delete():
    try:
        data = get_request_data()
        delete_schedule_config(int(data.get("id")))
        return success_response(msg="调度配置删除成功")
    except Exception as exc:
        return error_response(f"删除调度配置失败: {exc}")


@quant_bp.route("/scheduler/runs", methods=["GET"])
@require_auth
def quant_scheduler_runs(user, password):
    del user, password
    schedule_id = request.args.get("schedule_id", type=int)
    status = str(request.args.get("status", "")).strip() or None
    limit = request.args.get("limit", default=100, type=int) or 100
    limit = max(1, min(limit, 300))
    return success_response(data=list_schedule_runs(schedule_id=schedule_id, status=status, limit=limit))


@quant_bp.route("/scheduler/run/<int:run_id>", methods=["GET"])
@require_auth
def quant_scheduler_run_get(user, password, run_id):
    del user, password
    try:
        return success_response(data=get_schedule_run(run_id))
    except Exception as exc:
        return error_response(f"获取调度执行记录失败: {exc}")


@quant_bp.route("/scheduler/manual_run", methods=["POST"])
@require_admin_auth
def quant_scheduler_manual_run():
    try:
        data = get_request_data()
        schedule_id = int(data.get("schedule_id"))
        result = manual_trigger_schedule(schedule_id)
        return success_response(data=result, msg="已创建手工执行任务")
    except Exception as exc:
        return error_response(f"手工触发调度失败: {exc}")


@quant_bp.route("/scheduler/rebuild_due_runs", methods=["POST"])
@require_admin_auth
def quant_scheduler_rebuild_due_runs():
    try:
        data = get_request_data()
        lookback_minutes = int(data.get("lookback_minutes", 60) or 60)
        result = enqueue_due_runs(lookback_minutes=lookback_minutes)
        return success_response(data=result, msg="补偿执行记录已生成")
    except Exception as exc:
        return error_response(f"生成补偿执行记录失败: {exc}")


@quant_bp.route("/scheduler/execute_run", methods=["POST"])
@require_admin_auth
def quant_scheduler_execute_run():
    try:
        data = get_request_data()
        run_id = int(data.get("run_id"))
        result = execute_schedule_run(run_id)
        return success_response(data=result, msg="调度任务执行成功")
    except Exception as exc:
        return error_response(f"执行调度任务失败: {exc}")


@quant_bp.route("/providers", methods=["GET"])
@require_auth
def quant_providers(user, password):
    return success_response(
        data={
            "market": "A_SHARE",
            "providers": list_supported_providers(),
        }
    )


@quant_bp.route("/data/import", methods=["POST"])
@require_admin_auth
def quant_data_import():
    try:
        if "bundle" in request.files:
            upload = request.files["bundle"]
            file_bytes = upload.read()
            bundle = parse_bundle_bytes(file_bytes)
            result = import_bundle(bundle, file_name=upload.filename or "", payload_bytes=file_bytes)
            return success_response(data=result, msg="导入成功")

        data = get_request_data()
        payload = data.get("bundle")
        if payload is None and isinstance(data, dict):
            payload = data
        if isinstance(payload, str):
            payload = json.loads(payload)
        if not isinstance(payload, dict):
            return error_response("缺少 bundle 数据")

        payload_bytes = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        result = import_bundle(payload, payload_bytes=payload_bytes)
        return success_response(data=result, msg="导入成功")
    except Exception as exc:
        return error_response(f"导入数据失败: {exc}")


@quant_bp.route("/data/import_batches", methods=["GET"])
@require_admin_auth
def quant_import_batches():
    limit = request.args.get("limit", default=20, type=int) or 20
    limit = max(1, min(limit, 200))
    return success_response(data=fetch_import_batches(limit=limit))


@quant_bp.route("/data/daily_bars", methods=["GET"])
@require_auth
def quant_daily_bars(user, password):
    try:
        symbol = str(request.args.get("symbol", "")).strip()
        if not symbol:
            return error_response("symbol 不能为空")
        start_date = request.args.get("start_date")
        end_date = request.args.get("end_date")
        limit = request.args.get("limit", default=500, type=int) or 500
        limit = max(1, min(limit, 5000))
        data = fetch_daily_bars(symbol=symbol, start_date=start_date, end_date=end_date, limit=limit)
        return success_response(data=data)
    except Exception as exc:
        return error_response(f"查询日线失败: {exc}")


@quant_bp.route("/strategy/list", methods=["GET"])
@require_auth
def quant_strategy_list(user, password):
    del user, password
    status = str(request.args.get("status", "")).strip() or None
    return success_response(data=list_strategies(status=status))


@quant_bp.route("/strategy/get/<int:strategy_id>", methods=["GET"])
@require_auth
def quant_strategy_get(user, password, strategy_id):
    del user, password
    try:
        return success_response(data=get_strategy(strategy_id))
    except Exception as exc:
        return error_response(f"获取策略失败: {exc}")


@quant_bp.route("/strategy/create", methods=["POST"])
@require_admin_auth
def quant_strategy_create():
    try:
        data = get_request_data()
        name = str(data.get("name", "")).strip()
        if not name:
            return error_response("name 不能为空")
        symbols = parse_json_list(data.get("symbols"))
        rule_config = data.get("rule_config")
        if isinstance(rule_config, str):
            rule_config = json.loads(rule_config)
        result = create_strategy(
            name=name,
            description=str(data.get("description", "")).strip(),
            symbols=symbols,
            rule_config=rule_config,
            status=str(data.get("status", "active")).strip() or "active",
        )
        return success_response(data=result, msg="策略创建成功")
    except Exception as exc:
        return error_response(f"创建策略失败: {exc}")


@quant_bp.route("/strategy/update", methods=["POST"])
@require_admin_auth
def quant_strategy_update():
    try:
        data = get_request_data()
        strategy_id = int(data.get("id"))
        symbols = parse_json_list(data.get("symbols")) if "symbols" in data else None
        rule_config = data.get("rule_config") if "rule_config" in data else None
        if isinstance(rule_config, str):
            rule_config = json.loads(rule_config)
        updates = {}
        for key in ("name", "description", "status"):
            if key in data:
                updates[key] = data.get(key)
        if symbols is not None:
            updates["symbols"] = symbols
        if rule_config is not None:
            updates["rule_config"] = rule_config
        return success_response(data=update_strategy(strategy_id, **updates), msg="策略更新成功")
    except Exception as exc:
        return error_response(f"更新策略失败: {exc}")


@quant_bp.route("/strategy/delete", methods=["POST"])
@require_admin_auth
def quant_strategy_delete():
    try:
        data = get_request_data()
        strategy_id = int(data.get("id"))
        delete_strategy(strategy_id)
        return success_response(msg="策略删除成功")
    except Exception as exc:
        return error_response(f"删除策略失败: {exc}")


@quant_bp.route("/strategy/run", methods=["POST"])
@require_admin_auth
def quant_strategy_run():
    try:
        data = get_request_data()
        strategy_id = int(data.get("strategy_id"))
        trade_date = str(data.get("trade_date", "")).strip() or None
        save_all_signals = str(data.get("save_all_signals", "true")).lower() in ("true", "1", "yes")
        result = run_strategy(strategy_id=strategy_id, trade_date=trade_date, save_all_signals=save_all_signals)
        return success_response(data=result, msg="策略执行成功")
    except Exception as exc:
        return error_response(f"执行策略失败: {exc}")


@quant_bp.route("/strategy/runs", methods=["GET"])
@require_auth
def quant_strategy_runs(user, password):
    del user, password
    strategy_id = request.args.get("strategy_id", type=int)
    limit = request.args.get("limit", default=50, type=int) or 50
    limit = max(1, min(limit, 500))
    return success_response(data=list_strategy_runs(strategy_id=strategy_id, limit=limit))


@quant_bp.route("/strategy/signals", methods=["GET"])
@require_auth
def quant_strategy_signals(user, password):
    del user, password
    strategy_id = request.args.get("strategy_id", type=int)
    run_id = request.args.get("run_id", type=int)
    passed_only = str(request.args.get("passed_only", "false")).lower() in ("true", "1", "yes")
    limit = request.args.get("limit", default=200, type=int) or 200
    limit = max(1, min(limit, 2000))
    return success_response(
        data=list_strategy_signals(strategy_id=strategy_id, run_id=run_id, passed_only=passed_only, limit=limit)
    )


@quant_bp.route("/symbols", methods=["GET"])
@require_auth
def quant_symbols(user, password):
    del user, password
    limit = request.args.get("limit", default=500, type=int) or 500
    limit = max(1, min(limit, 5000))
    return success_response(data=list_available_symbols(limit=limit))


@quant_bp.route("/operations/list", methods=["GET"])
@require_auth
def quant_operations_list(user, password):
    del user, password
    strategy_id = request.args.get("strategy_id", type=int)
    symbol = str(request.args.get("symbol", "")).strip() or None
    status = str(request.args.get("status", "")).strip() or None
    limit = request.args.get("limit", default=100, type=int) or 100
    limit = max(1, min(limit, 500))
    return success_response(
        data=list_operation_records(strategy_id=strategy_id, symbol=symbol, status=status, limit=limit)
    )


@quant_bp.route("/operations/get/<int:record_id>", methods=["GET"])
@require_auth
def quant_operations_get(user, password, record_id):
    del user, password
    try:
        return success_response(data=get_operation_record(record_id))
    except Exception as exc:
        return error_response(f"获取操作记录失败: {exc}")


@quant_bp.route("/operations/create", methods=["POST"])
@require_auth
def quant_operations_create(user, password):
    del password
    try:
        data = get_request_data()
        symbol = str(data.get("symbol", "")).strip()
        trade_date = str(data.get("trade_date", "")).strip()
        if not symbol or not trade_date:
            return error_response("symbol 和 trade_date 不能为空")
        record = create_operation_record(
            symbol=symbol,
            trade_date=trade_date,
            action=data.get("action", "buy"),
            status=data.get("status", "draft"),
            result_status=data.get("result_status", ""),
            strategy_id=data.get("strategy_id"),
            run_id=data.get("run_id"),
            signal_id=data.get("signal_id"),
            price=data.get("price"),
            quantity=data.get("quantity"),
            amount=data.get("amount"),
            thesis=data.get("thesis", ""),
            execution_note=data.get("execution_note", ""),
            review_note=data.get("review_note", ""),
            result_pct=data.get("result_pct"),
            result_amount=data.get("result_amount"),
            tags=parse_json_list(data.get("tags")) if "tags" in data else data.get("tags"),
            meta=data.get("meta"),
            created_by=user,
        )
        return success_response(data=record, msg="操作记录创建成功")
    except Exception as exc:
        return error_response(f"创建操作记录失败: {exc}")


@quant_bp.route("/operations/update", methods=["POST"])
@require_auth
def quant_operations_update(user, password):
    del user, password
    try:
        data = get_request_data()
        record_id = int(data.get("id"))
        updates = {
            key: data.get(key)
            for key in (
                "strategy_id",
                "run_id",
                "signal_id",
                "symbol",
                "action",
                "status",
                "result_status",
                "trade_date",
                "price",
                "quantity",
                "amount",
                "thesis",
                "execution_note",
                "review_note",
                "result_pct",
                "result_amount",
                "meta",
            )
            if key in data
        }
        if "tags" in data:
            updates["tags"] = parse_json_list(data.get("tags")) if isinstance(data.get("tags"), str) else data.get("tags")
        return success_response(data=update_operation_record(record_id, **updates), msg="操作记录更新成功")
    except Exception as exc:
        return error_response(f"更新操作记录失败: {exc}")


@quant_bp.route("/operations/delete", methods=["POST"])
@require_auth
def quant_operations_delete(user, password):
    del user, password
    try:
        data = get_request_data()
        record_id = int(data.get("id"))
        delete_operation_record(record_id)
        return success_response(msg="操作记录删除成功")
    except Exception as exc:
        return error_response(f"删除操作记录失败: {exc}")


@quant_bp.route("/backtest/list", methods=["GET"])
@require_auth
def quant_backtest_list(user, password):
    del user, password
    strategy_id = request.args.get("strategy_id", type=int)
    status = str(request.args.get("status", "")).strip() or None
    limit = request.args.get("limit", default=30, type=int) or 30
    limit = max(1, min(limit, 200))
    return success_response(data=list_backtest_runs(strategy_id=strategy_id, status=status, limit=limit))


@quant_bp.route("/backtest/get/<int:backtest_id>", methods=["GET"])
@require_auth
def quant_backtest_get(user, password, backtest_id):
    del user, password
    try:
        return success_response(data=get_backtest_run(backtest_id))
    except Exception as exc:
        return error_response(f"获取回测结果失败: {exc}")


@quant_bp.route("/backtest/run", methods=["POST"])
@require_admin_auth
def quant_backtest_run():
    try:
        data = get_request_data()
        strategy_id = int(data.get("strategy_id"))
        start_date = str(data.get("start_date", "")).strip()
        end_date = str(data.get("end_date", "")).strip()
        if not start_date or not end_date:
            return error_response("start_date 和 end_date 不能为空")
        result = run_backtest(
            strategy_id=strategy_id,
            start_date=start_date,
            end_date=end_date,
            top_n=data.get("top_n", 3),
            hold_days=data.get("hold_days", 5),
            initial_capital=data.get("initial_capital", 100000),
            commission_rate=data.get("commission_rate", 0.001),
            slippage_rate=data.get("slippage_rate", 0.0005),
            benchmark_symbol=str(data.get("benchmark_symbol", "")).strip(),
            symbols=parse_json_list(data.get("symbols")) if "symbols" in data else data.get("symbols"),
        )
        return success_response(data=result, msg="回测执行成功")
    except Exception as exc:
        return error_response(f"执行回测失败: {exc}")


@quant_bp.route("/backtest/delete", methods=["POST"])
@require_admin_auth
def quant_backtest_delete():
    try:
        data = get_request_data()
        backtest_id = int(data.get("id"))
        delete_backtest_run(backtest_id)
        return success_response(msg="回测记录删除成功")
    except Exception as exc:
        return error_response(f"删除回测记录失败: {exc}")


@quant_bp.route("/client/tasks/create", methods=["POST"])
@require_admin_auth
def quant_client_task_create():
    try:
        data = get_request_data()
        symbols = parse_json_list(data.get("symbols"))
        if not symbols:
            raw_symbols = str(data.get("symbols_text", "")).strip()
            if raw_symbols:
                symbols = [item.strip() for item in raw_symbols.split(",") if item.strip()]
        if not symbols:
            return error_response("symbols 不能为空")

        start_date = str(data.get("start_date", "")).strip()
        end_date = str(data.get("end_date", "")).strip()
        if not start_date or not end_date:
            return error_response("start_date 和 end_date 不能为空")

        task = create_fetch_bars_task(
            symbols=symbols,
            start_date=start_date,
            end_date=end_date,
            provider=str(data.get("provider", "auto")).strip() or "auto",
            adjust_flag=str(data.get("adjust_flag", "qfq")).strip() or "qfq",
            note=str(data.get("note", "")).strip(),
            lease_seconds=int(data.get("lease_seconds", 600) or 600),
        )
        return success_response(data=task, msg="任务创建成功")
    except Exception as exc:
        return error_response(f"创建客户端任务失败: {exc}")


@quant_bp.route("/client/tasks/list", methods=["GET"])
@require_admin_auth
def quant_client_task_list():
    limit = request.args.get("limit", default=100, type=int) or 100
    limit = max(1, min(limit, 500))
    return success_response(data=list_tasks(limit=limit))


@quant_bp.route("/client/tasks/reset", methods=["POST"])
@require_admin_auth
def quant_client_task_reset():
    try:
        data = get_request_data()
        task_id = str(data.get("task_id", "")).strip()
        if not task_id:
            return error_response("task_id 不能为空")
        return success_response(data=reset_task(task_id), msg="任务已重置")
    except Exception as exc:
        return error_response(f"重置任务失败: {exc}")


@quant_bp.route("/client/tasks/claim", methods=["POST"])
@require_auth
def quant_client_task_claim(user, password):
    del user, password
    try:
        data = get_request_data()
        client_id = str(data.get("client_id", "")).strip()
        if not client_id:
            return error_response("client_id 不能为空")
        capabilities = parse_json_list(data.get("capabilities"))
        task = claim_next_task(client_id=client_id, capabilities=capabilities)
        return success_response(data=task, msg="已分派任务" if task else "当前无可执行任务")
    except Exception as exc:
        return error_response(f"认领任务失败: {exc}")


@quant_bp.route("/client/tasks/report", methods=["POST"])
@require_auth
def quant_client_task_report(user, password):
    del user, password
    try:
        data = get_request_data()
        client_id = str(data.get("client_id", "")).strip()
        task_id = str(data.get("task_id", "")).strip()
        status = str(data.get("status", "success")).strip().lower()
        message = str(data.get("message", "")).strip()
        if not client_id or not task_id:
            return error_response("client_id 和 task_id 不能为空")

        if status == "failed":
            task = mark_task_failed(task_id=task_id, client_id=client_id, message=message or "客户端上报失败")
            return success_response(data=task, msg="失败状态已记录")

        import_result = None
        if "bundle" in request.files:
            upload = request.files["bundle"]
            file_bytes = upload.read()
            bundle = parse_bundle_bytes(file_bytes)
            import_result = import_bundle(bundle, file_name=upload.filename or "", payload_bytes=file_bytes)
        else:
            payload = data.get("bundle")
            if isinstance(payload, str):
                payload = json.loads(payload)
            if isinstance(payload, dict):
                payload_bytes = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
                import_result = import_bundle(payload, payload_bytes=payload_bytes)

        task = mark_task_success(
            task_id=task_id,
            client_id=client_id,
            import_batch=import_result,
            message=message or "客户端上报成功",
        )
        return success_response(data=task, msg="任务上报成功")
    except Exception as exc:
        return error_response(f"上报任务结果失败: {exc}")
