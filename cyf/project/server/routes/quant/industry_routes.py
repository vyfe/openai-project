import json

from flask import Blueprint, request

from dto.common import error_response, get_request_data, parse_json_list, success_response
from service.auth_service import require_admin_auth, require_auth
from service.quant.industry_service import (
    collect_industry,
    create_or_update_industry_board,
    ensure_default_industry_boards,
    get_industry_dashboard,
    list_industry_boards,
    list_industry_news,
    list_research_reports,
    render_industry_daily_markdown,
)


bp = Blueprint("quant_industry_routes", __name__, url_prefix="/never_guess_my_usage/quant")


@bp.route("/industry/boards", methods=["GET"])
@require_auth
def quant_industry_boards(user, password):
    del user, password
    status = str(request.args.get("status", "")).strip() or None
    return success_response(data=list_industry_boards(status=status))


@bp.route("/industry/defaults", methods=["POST"])
@require_auth
def quant_industry_defaults(user, password):
    del user, password
    return success_response(data=ensure_default_industry_boards(), msg="默认行业板块已初始化")


@bp.route("/industry/board/save", methods=["POST"])
@require_admin_auth
def quant_industry_board_save():
    try:
        data = get_request_data()
        keywords = parse_json_list(data.get("keywords"))
        symbols = data.get("symbols") or []
        if isinstance(symbols, str):
            symbols = json.loads(symbols)
        result = create_or_update_industry_board(
            board_key=str(data.get("board_key", "")).strip(),
            name=str(data.get("name", "")).strip(),
            description=str(data.get("description", "")).strip(),
            keywords=keywords,
            symbols=symbols,
            status=str(data.get("status", "active")).strip() or "active",
        )
        return success_response(data=result, msg="行业板块已保存")
    except Exception as exc:
        return error_response(f"保存行业板块失败: {exc}")


@bp.route("/industry/collect", methods=["POST"])
@require_auth
def quant_industry_collect(user, password):
    del user, password
    try:
        data = get_request_data()
        targets = parse_json_list(data.get("targets"))
        result = collect_industry(
            board_id=int(data.get("board_id")) if data.get("board_id") else None,
            board_key=str(data.get("board_key", "")).strip(),
            targets=targets or None,
        )
        code = 200 if not result.get("errors") else 200
        return success_response(data=result, msg="行业数据采集完成"), code
    except Exception as exc:
        return error_response(f"行业数据采集失败: {exc}")


@bp.route("/industry/dashboard", methods=["GET"])
@require_auth
def quant_industry_dashboard(user, password):
    del user, password
    try:
        board_id = request.args.get("board_id", type=int)
        board_key = str(request.args.get("board_key", "")).strip()
        days = request.args.get("days", default=90, type=int) or 90
        return success_response(data=get_industry_dashboard(board_id=board_id, board_key=board_key, days=days))
    except Exception as exc:
        return error_response(f"获取行业看板失败: {exc}")


@bp.route("/industry/news", methods=["GET"])
@require_auth
def quant_industry_news(user, password):
    del user, password
    board_id = request.args.get("board_id", type=int)
    symbol = str(request.args.get("symbol", "")).strip()
    limit = request.args.get("limit", default=100, type=int) or 100
    return success_response(data=list_industry_news(board_id=board_id, symbol=symbol, limit=limit))


@bp.route("/industry/research_reports", methods=["GET"])
@require_auth
def quant_industry_research_reports(user, password):
    del user, password
    board_id = request.args.get("board_id", type=int)
    symbol = str(request.args.get("symbol", "")).strip()
    limit = request.args.get("limit", default=100, type=int) or 100
    return success_response(data=list_research_reports(board_id=board_id, symbol=symbol, limit=limit))


@bp.route("/industry/report/preview", methods=["GET"])
@require_auth
def quant_industry_report_preview(user, password):
    del user, password
    try:
        board_id = request.args.get("board_id", type=int)
        board_key = str(request.args.get("board_key", "")).strip()
        return success_response(data={"markdown": render_industry_daily_markdown(board_id=board_id, board_key=board_key)})
    except Exception as exc:
        return error_response(f"生成行业报告预览失败: {exc}")
