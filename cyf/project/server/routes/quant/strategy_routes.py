import json

from flask import Blueprint, request

from dto.common import error_response, get_request_data, parse_json_list, success_response
from service.auth_service import require_admin_auth, require_auth
from service.quant.common import normalize_symbol
from service.quant.expression_engine import (
    BAR_FIELD_NAMES,
    EXPRESSION_FUNCTION_NAMES,
    validate_expression,
)
from service.quant.indicator_registry import INDICATOR_REGISTRY, catalog_payload
from service.quant.query_service import fetch_daily_bars
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
from service.quant.rule_engine import evaluate_series
from service.quant.rule_migration import migrate_v1_to_v2
from service.quant.expr_llm_service import generate_expr_from_description
from service.quant.strategy_service import (
    batch_soft_delete_instruments,
    count_available_symbols,
    create_strategy,
    delete_strategy,
    get_strategy,
    list_available_symbols,
    list_strategies,
    list_strategy_runs,
    list_strategy_signals,
    run_strategy,
    soft_delete_instrument,
    update_strategy,
)
from service.quant.strategy_templates import STRATEGY_TEMPLATES
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
    limit = request.args.get("limit", default=100, type=int) or 100
    limit = max(1, min(limit, 500))
    offset = request.args.get("offset", default=0, type=int) or 0
    offset = max(0, offset)
    keyword = str(request.args.get("keyword", "")).strip() or None
    items = list_available_symbols(limit=limit, offset=offset, keyword=keyword)
    total = count_available_symbols(keyword=keyword)
    return success_response(data={"items": items, "total": total, "limit": limit, "offset": offset})


@bp.route("/symbols", methods=["DELETE"])
@require_admin_auth
def quant_symbol_delete():
    """软删除单个股票池条目。"""
    try:
        symbol = str(request.args.get("symbol", "")).strip()
        if not symbol:
            return error_response("symbol 不能为空")
        deleted = soft_delete_instrument(symbol)
        if not deleted:
            return error_response(f"未找到 active 状态的 {symbol}（可能已经删除）")
        return success_response(data={"symbol": symbol, "deleted": True}, msg=f"已删除 {symbol}")
    except Exception as exc:
        return error_response(f"删除股票失败: {exc}")


@bp.route("/symbols/batch_delete", methods=["POST"])
@require_admin_auth
def quant_symbol_batch_delete():
    """批量软删除股票池条目。body: {symbols: [...]}
    返回 {deleted: [...], missing: [...]}；missing = 不在 active 集合里（可能已经被删/不存在）。"""
    try:
        data = get_request_data()
        symbols = parse_json_list(data.get("symbols"))
        if not symbols:
            return error_response("symbols 不能为空")
        result = batch_soft_delete_instruments(symbols)
        msg = f"删除 {len(result['deleted'])} 条"
        if result["missing"]:
            msg += f"，{len(result['missing'])} 条已不在池中"
        return success_response(data=result, msg=msg)
    except Exception as exc:
        return error_response(f"批量删除失败: {exc}")


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


# ===========================================================================
# 策略 IDE 元数据 + 试算（P1 前端用）
# ===========================================================================


@bp.route("/meta/indicators", methods=["GET"])
@require_auth
def quant_meta_indicators(user, password):
    """指标 catalog：前端据此渲染指标面板 + 参数表单。

    返回 [{key, label, category, base_lookback, params: [...], outputs: [...]}, ...]
    """
    del user, password
    return success_response(data=catalog_payload())


@bp.route("/meta/expression_functions", methods=["GET"])
@require_auth
def quant_meta_expression_functions(user, password):
    """表达式沙箱允许的函数 + bar 字段；前端用来做变量/函数自动补全。

    返回 {bar_fields: [...], functions: [...]}，每个 function 给出签名。
    """
    del user, password
    functions = [
        {"name": "prev", "signature": "prev(x)", "desc": "x 的前 1 根（与 ref(x, 1) 等价）"},
        {"name": "ref", "signature": "ref(x, n)", "desc": "x 的前 n 根"},
        {"name": "avg", "signature": "avg(x, n)", "desc": "x 在当前及之前 n-1 根的均值"},
        {"name": "abs", "signature": "abs(x)", "desc": "绝对值"},
        {"name": "min", "signature": "min(a, b, ...)", "desc": "最小值，跳过 None"},
        {"name": "max", "signature": "max(a, b, ...)", "desc": "最大值，跳过 None"},
        {"name": "cross_up", "signature": "cross_up(a, b)", "desc": "a 上穿 b（当前 a>b 且前一根 a<=b）"},
        {"name": "cross_down", "signature": "cross_down(a, b)", "desc": "a 下穿 b"},
        {"name": "any_", "signature": "any_(a, b, ...)", "desc": "任一为真"},
        {"name": "all_", "signature": "all_(a, b, ...)", "desc": "全部为真"},
    ]
    return success_response(data={"bar_fields": list(BAR_FIELD_NAMES), "functions": functions})


@bp.route("/meta/strategy_templates", methods=["GET"])
@require_auth
def quant_meta_strategy_templates(user, password):
    """预设策略模板（v2 形态）；前端"模板"按钮据此渲染。"""
    del user, password
    return success_response(data=STRATEGY_TEMPLATES)


@bp.route("/strategy/validate", methods=["POST"])
@require_auth
def quant_strategy_validate(user, password):
    """校验 rule_config 各条 expr 的语法与变量合法性，不落库、不打数据库。

    body: {rule_config: {...}} 或直接传 v2 配置。
    返回 {ok, rules: [{id, label, expr, ok, error}]}。
    """
    del user, password
    try:
        data = get_request_data() or {}
        cfg = data.get("rule_config") or {}
        if not isinstance(cfg, dict):
            return error_response("rule_config 必须是 JSON 对象")
        v2 = migrate_v1_to_v2(cfg)
        # 收集已知变量：bar 字段 + registry 中所有字面 + 模板展开后的 output 名
        known: set = set(BAR_FIELD_NAMES)
        known.update({"open", "high", "low", "close", "vol", "amt", "pct", "turnover"})  # 别名
        for spec in INDICATOR_REGISTRY.values():
            for out in spec.outputs:
                if "{" not in out.name:
                    known.add(out.name)
                else:
                    # 模板展开：用 spec.params 的 default 把 {window} 等替换成具体名
                    if spec.key == "ma":
                        for w in spec.params[0].default:
                            known.add(out.name.replace("{window}", str(w)))
                    elif spec.key in ("vol_ratio", "period_return", "rolling_high_low"):
                        # 第一参数即 window，default 必有
                        try:
                            w = spec.params[0].default
                            known.add(out.name.replace("{window}", str(w)))
                        except (IndexError, AttributeError):
                            pass
        known.update(EXPRESSION_FUNCTION_NAMES)

        results = []
        any_error = False
        for rule in v2.get("rules") or []:
            if not isinstance(rule, dict):
                continue
            rid = str(rule.get("id") or "")
            expr_text = str(rule.get("expr") or "")
            label = str(rule.get("label") or rid)
            vr = validate_expression(expr_text, known)
            if not vr.ok:
                any_error = True
            results.append({
                "id": rid,
                "label": label,
                "expr": expr_text,
                "ok": vr.ok,
                "error": vr.error,
                "used_vars": list(vr.used_vars),
            })
        return success_response(
            data={"ok": not any_error, "rules": results},
            msg="校验完成" if not any_error else "存在语法错误",
        )
    except Exception as exc:
        return error_response(f"校验失败: {exc}")


@bp.route("/strategy/llm_generate_expr", methods=["POST"])
@require_auth
def quant_strategy_llm_generate_expr(user, password):
    """调大模型把自然语言描述生成 expr。不入库；不需要 admin。"""
    del password
    try:
        data = get_request_data() or {}
        description = str(data.get("description") or "").strip()
        indicator_keys = data.get("indicator_keys") or []
        if not isinstance(indicator_keys, list):
            indicator_keys = []
        model = str(data.get("model") or "gpt-5.6-luna").strip() or "gpt-5.6-luna"
        result = generate_expr_from_description(
            username=user,
            description=description,
            indicator_keys=[str(k) for k in indicator_keys],
            model=model,
        )
        if "error" in result:
            return success_response(data=result, msg=result["error"])
        return success_response(data=result, msg="大模型生成成功")
    except Exception as exc:
        return error_response(f"LLM 生成失败: {exc}")


@bp.route("/strategy/dry_run", methods=["POST"])
@require_auth
def quant_strategy_dry_run(user, password):
    """不落库试算：按 symbol 跑日线 evaluate_series，返回逐日结果。

    body: {rule_config, symbol, start_date, end_date, adjust_flag?}
    返回 {rule_config, symbol, bars: [...], results: [{date, passed, score, signal_type,
           reasons, rule_results: [{id, label, passed, value}]}], meta: {...}}
    """
    del user, password
    try:
        data = get_request_data() or {}
        cfg = data.get("rule_config") or {}
        symbol_raw = str(data.get("symbol") or "").strip()
        start_date = str(data.get("start_date") or "").strip()
        end_date = str(data.get("end_date") or "").strip()
        adjust_flag = str(data.get("adjust_flag", "qfq")).strip() or "qfq"
        if not isinstance(cfg, dict):
            return error_response("rule_config 必须是 JSON 对象")
        if not symbol_raw or not start_date or not end_date:
            return error_response("symbol / start_date / end_date 均不能为空")
        symbol = normalize_symbol(symbol_raw)

        # fetch_daily_bars 返回的是 dict；evaluate_series 用 getattr 取字段，把 dict 套成简易对象
        from datetime import date as _date, datetime as _datetime

        class _Bar(dict):
            def __getattr__(self, item):
                value = self.get(item)
                if value is None:
                    return None
                # trade_date / trade_datetime 字段 to_dict() 序列化时是 ISO 字符串，
                # evaluate_series 后续会调 .isoformat() / .fromisoformat()，需要 date/datetime 对象。
                if item in ("trade_date",) and isinstance(value, str):
                    try:
                        return _date.fromisoformat(value)
                    except ValueError:
                        return value
                if item == "trade_datetime" and isinstance(value, str):
                    try:
                        return _datetime.fromisoformat(value.replace(" ", "T"))
                    except ValueError:
                        return value
                return value

        raw_bars = fetch_daily_bars(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            adjust_flag=adjust_flag,
        )
        bars_desc = [_Bar(b) for b in raw_bars]
        results_raw = evaluate_series(cfg, bars_desc)

        # 序列化 bars 与 results；挑出命中点
        bars_out = []
        results_out = []
        passed_dates = []
        for bar, r in zip(bars_desc, results_raw):
            bars_out.append({
                "trade_date": bar.trade_date.isoformat() if getattr(bar, "trade_date", None) else None,
                "open_price": getattr(bar, "open_price", None),
                "high_price": getattr(bar, "high_price", None),
                "low_price": getattr(bar, "low_price", None),
                "close_price": getattr(bar, "close_price", None),
                "volume": getattr(bar, "volume", None),
                "amount": getattr(bar, "amount", None),
                "pct_change": getattr(bar, "pct_change", None),
                "turnover_rate": getattr(bar, "turnover_rate", None),
            })
            rule_results = []
            for ev in (r.get("metrics") or {}).get("rules") or []:
                rule_results.append({
                    "id": ev.get("id") or "",
                    "label": ev.get("label") or "",
                    "passed": bool(ev.get("passed")),
                    "value": (ev.get("metrics") or {}).get("value"),
                })
            results_out.append({
                "date": r.get("metrics", {}).get("trade_date") or (bar.trade_date.isoformat() if bar.trade_date else None),
                "passed": bool(r.get("passed")),
                "score": float(r.get("score") or 0),
                "signal_type": r.get("signal_type"),
                "reasons": r.get("reasons") or [],
                "rule_results": rule_results,
            })
            if r.get("passed"):
                passed_dates.append(
                    getattr(bar, "trade_date", None).isoformat()
                    if getattr(bar, "trade_date", None) else None
                )

        return success_response(
            data={
                "rule_config": cfg,
                "symbol": symbol,
                "start_date": start_date,
                "end_date": end_date,
                "bars": bars_out,
                "results": results_out,
                "passed_dates": passed_dates,
                "meta": {
                    "bars_count": len(bars_desc),
                    "passed_count": len(passed_dates),
                    "adjust_flag": adjust_flag,
                },
            },
            msg=f"试算完成，{len(passed_dates)} 个命中 / {len(bars_desc)} 个交易日",
        )
    except Exception as exc:
        return error_response(f"试算失败: {exc}")

