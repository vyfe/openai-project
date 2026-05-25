from flask import Blueprint, request

from dto.common import error_response, get_request_data, parse_json_list, success_response
from service.auth_service import require_admin_auth, require_auth
from service.quant.im_service import (
    create_im_channel,
    delete_im_channel,
    get_im_channel,
    handle_feishu_event_callback,
    list_delivery_records,
    list_inbound_events,
    list_im_channels,
    send_position_summary_to_channel,
    send_report_to_channel,
    send_test_message,
    update_im_channel,
)
from service.quant.memory_service import curate_symbol_memories, list_memory_files, read_symbol_memory


bp = Blueprint("quant_im_memory_routes", __name__, url_prefix="/never_guess_my_usage/quant")


@bp.route("/im/channels", methods=["GET"])
@require_auth
def quant_im_channels(user, password):
    del user, password
    status = str(request.args.get("status", "")).strip() or None
    channel_type = str(request.args.get("channel_type", "")).strip() or None
    return success_response(data=list_im_channels(status=status, channel_type=channel_type))


@bp.route("/im/channel/<int:channel_id>", methods=["GET"])
@require_auth
def quant_im_channel_get(user, password, channel_id):
    del user, password
    try:
        return success_response(data=get_im_channel(channel_id))
    except Exception as exc:
        return error_response(f"获取 IM 通道失败: {exc}")


@bp.route("/im/channel/create", methods=["POST"])
@require_admin_auth
def quant_im_channel_create():
    try:
        data = get_request_data()
        result = create_im_channel(
            name=str(data.get("name", "")).strip(),
            status=str(data.get("status", "active")).strip() or "active",
            config=data.get("config"),
            description=str(data.get("description", "")).strip(),
        )
        return success_response(data=result, msg="IM 通道创建成功")
    except Exception as exc:
        return error_response(f"创建 IM 通道失败: {exc}")


@bp.route("/im/channel/update", methods=["POST"])
@require_admin_auth
def quant_im_channel_update():
    try:
        data = get_request_data()
        channel_id = int(data.get("id"))
        updates = {key: data.get(key) for key in ("name", "status", "description", "config") if key in data}
        result = update_im_channel(channel_id, **updates)
        return success_response(data=result, msg="IM 通道更新成功")
    except Exception as exc:
        return error_response(f"更新 IM 通道失败: {exc}")


@bp.route("/im/channel/delete", methods=["POST"])
@require_admin_auth
def quant_im_channel_delete():
    try:
        data = get_request_data()
        delete_im_channel(int(data.get("id")))
        return success_response(msg="IM 通道删除成功")
    except Exception as exc:
        return error_response(f"删除 IM 通道失败: {exc}")


@bp.route("/im/deliveries", methods=["GET"])
@require_auth
def quant_im_deliveries(user, password):
    del user, password
    report_id = request.args.get("report_id", type=int)
    channel_id = request.args.get("channel_id", type=int)
    status = str(request.args.get("status", "")).strip() or None
    limit = request.args.get("limit", default=100, type=int) or 100
    limit = max(1, min(limit, 300))
    return success_response(data=list_delivery_records(report_id=report_id, channel_id=channel_id, status=status, limit=limit))


@bp.route("/im/inbound_events", methods=["GET"])
@require_auth
def quant_im_inbound_events(user, password):
    del user, password
    channel_id = request.args.get("channel_id", type=int)
    status = str(request.args.get("status", "")).strip() or None
    limit = request.args.get("limit", default=100, type=int) or 100
    limit = max(1, min(limit, 300))
    return success_response(data=list_inbound_events(channel_id=channel_id, status=status, limit=limit))


@bp.route("/im/feishu/events", methods=["POST"])
def quant_im_feishu_events():
    payload, status_code = handle_feishu_event_callback(request.get_data() or b"", request.headers)
    return payload, status_code


@bp.route("/im/send_report", methods=["POST"])
@require_admin_auth
def quant_im_send_report():
    try:
        data = get_request_data()
        report_id = int(data.get("report_id"))
        result = send_report_to_channel(report_id=report_id, channel_id=int(data.get("channel_id")))
        if result.get("status") == "failed":
            return error_response(f"推送报告失败: {result.get('error_message') or '未知错误'}")
        return success_response(data=result, msg="报告推送已执行")
    except Exception as exc:
        return error_response(f"推送报告失败: {exc}")


@bp.route("/im/send_positions", methods=["POST"])
@require_admin_auth
def quant_im_send_positions():
    try:
        data = get_request_data()
        result = send_position_summary_to_channel(
            channel_id=int(data.get("channel_id")),
            strategy_id=int(data.get("strategy_id")) if data.get("strategy_id") not in (None, "") else None,
        )
        if result.get("status") == "failed":
            return error_response(f"推送持仓摘要失败: {result.get('error_message') or '未知错误'}")
        return success_response(data=result, msg="持仓摘要推送已执行")
    except Exception as exc:
        return error_response(f"推送持仓摘要失败: {exc}")


@bp.route("/im/test", methods=["POST"])
@require_admin_auth
def quant_im_test():
    try:
        data = get_request_data()
        result = send_test_message(
            content=str(data.get("content", "")).strip() or "测试消息",
            channel_id=int(data.get("channel_id")),
        )
        return success_response(data=result, msg="测试消息发送成功")
    except Exception as exc:
        return error_response(f"发送测试消息失败: {exc}")


@bp.route("/memory/files", methods=["GET"])
@require_auth
def quant_memory_files(user, password):
    del user, password
    limit = request.args.get("limit", default=100, type=int) or 100
    limit = max(1, min(limit, 300))
    return success_response(data=list_memory_files(limit=limit))


@bp.route("/memory/<symbol>", methods=["GET"])
@require_auth
def quant_memory_get(user, password, symbol):
    del user, password
    try:
        return success_response(data=read_symbol_memory(symbol))
    except Exception as exc:
        return error_response(f"获取记忆文件失败: {exc}")


@bp.route("/memory/curate", methods=["POST"])
@require_admin_auth
def quant_memory_curate():
    try:
        data = get_request_data()
        symbols = parse_json_list(data.get("symbols")) if "symbols" in data else data.get("symbols")
        lookback_days = int(data.get("lookback_days", 120) or 120)
        limit = int(data.get("limit", 50) or 50)
        result = curate_symbol_memories(symbols=symbols, lookback_days=lookback_days, limit=limit)
        return success_response(data=result, msg="记忆梳理完成")
    except Exception as exc:
        return error_response(f"梳理记忆失败: {exc}")

