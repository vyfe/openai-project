from flask import Blueprint, request

from dto.common import error_response, get_request_data, parse_json_list, success_response
from service.auth_service import require_admin_auth, require_auth
from service.quant.backtest_service import delete_backtest_run, get_backtest_run, list_backtest_runs, run_backtest
from service.quant.ops_service import (
    create_operation_record,
    delete_operation_record,
    get_operation_record,
    list_operation_records,
    update_operation_record,
)
from service.quant.position_service import create_position_entry, delete_position_entry, get_position_entry, list_position_journal, list_position_summary, update_position_entry


bp = Blueprint("quant_trade_routes", __name__, url_prefix="/never_guess_my_usage/quant")


@bp.route("/positions/summary", methods=["GET"])
@require_auth
def quant_positions_summary(user, password):
    del password
    strategy_id = request.args.get("strategy_id", type=int)
    return success_response(data=list_position_summary(strategy_id=strategy_id, created_by=user))


@bp.route("/positions/journal", methods=["GET"])
@require_auth
def quant_positions_journal(user, password):
    del password
    strategy_id = request.args.get("strategy_id", type=int)
    symbol = str(request.args.get("symbol", "")).strip() or None
    source = str(request.args.get("source", "")).strip() or None
    limit = request.args.get("limit", default=100, type=int) or 100
    limit = max(1, min(limit, 500))
    return success_response(data=list_position_journal(strategy_id=strategy_id, symbol=symbol, source=source, created_by=user, limit=limit))


@bp.route("/positions/journal/<int:entry_id>", methods=["GET"])
@require_auth
def quant_position_get(user, password, entry_id):
    del user, password
    try:
        return success_response(data=get_position_entry(entry_id))
    except Exception as exc:
        return error_response(f"获取持仓流水失败: {exc}")


@bp.route("/positions/create", methods=["POST"])
@require_auth
def quant_position_create(user, password):
    del password
    try:
        data = get_request_data()
        result = create_position_entry(
            strategy_id=data.get("strategy_id"),
            run_id=data.get("run_id"),
            operation_id=data.get("operation_id"),
            symbol=str(data.get("symbol", "")).strip(),
            side=str(data.get("side", "buy")).strip() or "buy",
            price=data.get("price"),
            quantity=data.get("quantity"),
            occurred_at=data.get("occurred_at"),
            source=str(data.get("source", "manual")).strip() or "manual",
            reason=str(data.get("reason", "")).strip(),
            remark=str(data.get("remark", "")).strip(),
            created_by=user,
        )
        return success_response(data=result, msg="持仓流水创建成功")
    except Exception as exc:
        return error_response(f"创建持仓流水失败: {exc}")


@bp.route("/positions/update", methods=["POST"])
@require_auth
def quant_position_update(user, password):
    del user, password
    try:
        data = get_request_data()
        entry_id = int(data.get("id"))
        updates = {key: data.get(key) for key in ("strategy_id", "run_id", "operation_id", "symbol", "side", "price", "quantity", "occurred_at", "source", "reason", "remark") if key in data}
        return success_response(data=update_position_entry(entry_id, **updates), msg="持仓流水更新成功")
    except Exception as exc:
        return error_response(f"更新持仓流水失败: {exc}")


@bp.route("/positions/delete", methods=["POST"])
@require_auth
def quant_position_delete(user, password):
    del user, password
    try:
        data = get_request_data()
        delete_position_entry(int(data.get("id")))
        return success_response(msg="持仓流水删除成功")
    except Exception as exc:
        return error_response(f"删除持仓流水失败: {exc}")


@bp.route("/operations/list", methods=["GET"])
@require_auth
def quant_operations_list(user, password):
    del user, password
    strategy_id = request.args.get("strategy_id", type=int)
    symbol = str(request.args.get("symbol", "")).strip() or None
    status = str(request.args.get("status", "")).strip() or None
    limit = request.args.get("limit", default=100, type=int) or 100
    limit = max(1, min(limit, 500))
    return success_response(data=list_operation_records(strategy_id=strategy_id, symbol=symbol, status=status, limit=limit))


@bp.route("/operations/get/<int:record_id>", methods=["GET"])
@require_auth
def quant_operations_get(user, password, record_id):
    del user, password
    try:
        return success_response(data=get_operation_record(record_id))
    except Exception as exc:
        return error_response(f"获取操作记录失败: {exc}")


@bp.route("/operations/create", methods=["POST"])
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


@bp.route("/operations/update", methods=["POST"])
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


@bp.route("/operations/delete", methods=["POST"])
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


@bp.route("/backtest/list", methods=["GET"])
@require_auth
def quant_backtest_list(user, password):
    del user, password
    strategy_id = request.args.get("strategy_id", type=int)
    status = str(request.args.get("status", "")).strip() or None
    limit = request.args.get("limit", default=30, type=int) or 30
    limit = max(1, min(limit, 200))
    return success_response(data=list_backtest_runs(strategy_id=strategy_id, status=status, limit=limit))


@bp.route("/backtest/get/<int:backtest_id>", methods=["GET"])
@require_auth
def quant_backtest_get(user, password, backtest_id):
    del user, password
    try:
        return success_response(data=get_backtest_run(backtest_id))
    except Exception as exc:
        return error_response(f"获取回测结果失败: {exc}")


@bp.route("/backtest/run", methods=["POST"])
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


@bp.route("/backtest/delete", methods=["POST"])
@require_admin_auth
def quant_backtest_delete():
    try:
        data = get_request_data()
        backtest_id = int(data.get("id"))
        delete_backtest_run(backtest_id)
        return success_response(msg="回测记录删除成功")
    except Exception as exc:
        return error_response(f"删除回测记录失败: {exc}")
