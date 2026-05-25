import json

from flask import Blueprint, request

from dto.common import error_response, get_request_data, parse_json_list, success_response
from service.auth_service import require_admin_auth, require_auth
from service.quant.report_service import (
    create_prompt_template,
    create_report_for_run,
    delete_prompt_template,
    get_prompt_template,
    get_report,
    list_prompt_templates,
    list_reports,
    update_prompt_template,
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
from service.quant.symbol_search_service import search_symbols_fallback


bp = Blueprint("quant_strategy_routes", __name__, url_prefix="/never_guess_my_usage/quant")


@bp.route("/strategy/list", methods=["GET"])
@require_auth
def quant_strategy_list(user, password):
    del user, password
    status = str(request.args.get("status", "")).strip() or None
    return success_response(data=list_strategies(status=status))


@bp.route("/strategy/get/<int:strategy_id>", methods=["GET"])
@require_auth
def quant_strategy_get(user, password, strategy_id):
    del user, password
    try:
        return success_response(data=get_strategy(strategy_id))
    except Exception as exc:
        return error_response(f"获取策略失败: {exc}")


@bp.route("/strategy/create", methods=["POST"])
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


@bp.route("/strategy/update", methods=["POST"])
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


@bp.route("/strategy/delete", methods=["POST"])
@require_admin_auth
def quant_strategy_delete():
    try:
        data = get_request_data()
        strategy_id = int(data.get("id"))
        delete_strategy(strategy_id)
        return success_response(msg="策略删除成功")
    except Exception as exc:
        return error_response(f"删除策略失败: {exc}")


@bp.route("/strategy/run", methods=["POST"])
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


@bp.route("/strategy/runs", methods=["GET"])
@require_auth
def quant_strategy_runs(user, password):
    del user, password
    strategy_id = request.args.get("strategy_id", type=int)
    limit = request.args.get("limit", default=50, type=int) or 50
    limit = max(1, min(limit, 500))
    return success_response(data=list_strategy_runs(strategy_id=strategy_id, limit=limit))


@bp.route("/strategy/signals", methods=["GET"])
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


@bp.route("/symbols", methods=["GET"])
@require_auth
def quant_symbols(user, password):
    del user, password
    limit = request.args.get("limit", default=500, type=int) or 500
    limit = max(1, min(limit, 5000))
    return success_response(data=list_available_symbols(limit=limit))


@bp.route("/symbols/search", methods=["GET"])
@require_auth
def quant_symbol_search(user, password):
    del user, password
    keyword = str(request.args.get("keyword", "")).strip()
    limit = request.args.get("limit", default=20, type=int) or 20
    try:
        results = search_symbols_fallback(keyword, limit=max(1, min(limit, 50)))
        return success_response(data=results, msg=f"找到 {len(results)} 个匹配")
    except Exception as exc:
        return error_response(f"搜索失败: {exc}")


@bp.route("/prompt_templates", methods=["GET"])
@require_auth
def quant_prompt_templates(user, password):
    del user, password
    strategy_id = request.args.get("strategy_id", type=int)
    report_type = str(request.args.get("report_type", "")).strip() or None
    return success_response(data=list_prompt_templates(strategy_id=strategy_id, report_type=report_type))


@bp.route("/prompt_template/<int:template_id>", methods=["GET"])
@require_auth
def quant_prompt_template_get(user, password, template_id):
    del user, password
    try:
        return success_response(data=get_prompt_template(template_id))
    except Exception as exc:
        return error_response(f"获取 Prompt 模板失败: {exc}")


@bp.route("/prompt_template/create", methods=["POST"])
@require_admin_auth
def quant_prompt_template_create():
    try:
        data = get_request_data()
        result = create_prompt_template(
            strategy_id=data.get("strategy_id"),
            template_name=str(data.get("template_name", "default")).strip() or "default",
            prompt_version=str(data.get("prompt_version", "")).strip(),
            status=str(data.get("status", "active")).strip() or "active",
            report_type=str(data.get("report_type", "test_report")).strip() or "test_report",
            prompt_template=str(data.get("prompt_template", "")).strip(),
            change_note=str(data.get("change_note", "")).strip(),
        )
        return success_response(data=result, msg="Prompt 模板创建成功")
    except Exception as exc:
        return error_response(f"创建 Prompt 模板失败: {exc}")


@bp.route("/prompt_template/update", methods=["POST"])
@require_admin_auth
def quant_prompt_template_update():
    try:
        data = get_request_data()
        template_id = int(data.get("id"))
        updates = {key: data.get(key) for key in ("strategy_id", "template_name", "prompt_version", "status", "report_type", "prompt_template", "change_note") if key in data}
        result = update_prompt_template(template_id, **updates)
        return success_response(data=result, msg="Prompt 模板更新成功")
    except Exception as exc:
        return error_response(f"更新 Prompt 模板失败: {exc}")


@bp.route("/prompt_template/delete", methods=["POST"])
@require_admin_auth
def quant_prompt_template_delete():
    try:
        data = get_request_data()
        delete_prompt_template(int(data.get("id")))
        return success_response(msg="Prompt 模板删除成功")
    except Exception as exc:
        return error_response(f"删除 Prompt 模板失败: {exc}")


@bp.route("/reports", methods=["GET"])
@require_auth
def quant_reports(user, password):
    del user, password
    strategy_id = request.args.get("strategy_id", type=int)
    run_id = request.args.get("run_id", type=int)
    limit = request.args.get("limit", default=100, type=int) or 100
    limit = max(1, min(limit, 300))
    return success_response(data=list_reports(strategy_id=strategy_id, run_id=run_id, limit=limit))


@bp.route("/report/<int:report_id>", methods=["GET"])
@require_auth
def quant_report_get(user, password, report_id):
    del user, password
    try:
        return success_response(data=get_report(report_id))
    except Exception as exc:
        return error_response(f"获取报告失败: {exc}")


@bp.route("/report/generate", methods=["POST"])
@require_admin_auth
def quant_report_generate():
    try:
        data = get_request_data()
        run_id = int(data.get("run_id"))
        report_type = str(data.get("report_type", "test_report")).strip() or "test_report"
        result = create_report_for_run(run_id=run_id, report_type=report_type)
        return success_response(data=result, msg="测试报告生成成功")
    except Exception as exc:
        return error_response(f"生成测试报告失败: {exc}")

