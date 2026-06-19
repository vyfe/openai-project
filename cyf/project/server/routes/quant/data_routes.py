import json

from flask import Blueprint, request

from dto.common import error_response, get_request_data, parse_json_list, success_response
from service.quant.dashboard_service import get_dashboard_overview
from service.quant.import_service import fetch_import_batches, import_bundle, parse_bundle_bytes
from service.quant.position_service import enqueue_position_backfill_task
from service.quant.provider_factory import list_supported_providers
from service.quant.query_service import fetch_daily_bars
from service.quant.symbol_search_service import search_symbols_fallback
from service.auth_service import require_admin_auth, require_auth


bp = Blueprint("quant_data_routes", __name__, url_prefix="/never_guess_my_usage/quant")


@bp.route("/dashboard/overview", methods=["GET"])
@require_auth
def quant_dashboard_overview(user, password):
    del user, password
    return success_response(data=get_dashboard_overview())


@bp.route("/providers", methods=["GET"])
@require_auth
def quant_providers(user, password):
    del user, password
    return success_response(data={"market": "A_SHARE", "providers": list_supported_providers()})


@bp.route("/data/import", methods=["POST"])
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


@bp.route("/data/import_batches", methods=["GET"])
@require_admin_auth
def quant_import_batches():
    limit = request.args.get("limit", default=20, type=int) or 20
    limit = max(1, min(limit, 200))
    return success_response(data=fetch_import_batches(limit=limit))


@bp.route("/data/backfill", methods=["POST"])
@require_auth
def quant_data_backfill(user, password):
    del password
    try:
        data = get_request_data()
        symbols = parse_json_list(data.get("symbols"))
        if not symbols:
            raw_symbols = str(data.get("symbols_text", "")).strip()
            if raw_symbols:
                symbols = [item.strip() for item in raw_symbols.split(",") if item.strip()]
        if not symbols:
            return error_response("symbols 不能为空")

        result = enqueue_position_backfill_task(
            symbols=symbols,
            created_by=user,
            lookback_days=int(data.get("lookback_days", 730) or 730),
            provider=str(data.get("provider", "auto")).strip() or "auto",
            adjust_flag=str(data.get("adjust_flag", "qfq")).strip() or "qfq",
            lease_seconds=int(data.get("lease_seconds", 600) or 600),
            note=str(data.get("note", "")).strip(),
        )
        return success_response(data=result, msg="历史补数任务已创建")
    except Exception as exc:
        return error_response(f"创建历史补数任务失败: {exc}")


@bp.route("/data/daily_bars", methods=["GET"])
@require_auth
def quant_daily_bars(user, password):
    try:
        symbol = str(request.args.get("symbol", "")).strip()
        if not symbol:
            return error_response("symbol 不能为空")
        start_date = str(request.args.get("start_date", "")).strip() or None
        end_date = str(request.args.get("end_date", "")).strip() or None
        limit = request.args.get("limit", default=200, type=int) or 200
        limit = max(1, min(limit, 5000))
        return success_response(data=fetch_daily_bars(symbol=symbol, start_date=start_date, end_date=end_date, limit=limit))
    except Exception as exc:
        return error_response(f"查询日线失败: {exc}")
