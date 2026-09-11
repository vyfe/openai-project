import json
import logging

from flask import Blueprint, request

from dto.common import error_response, get_request_data, parse_json_list, success_response
from service.auth_service import require_admin_auth, require_auth
from service.quant.import_service import import_bundle, parse_bundle_bytes
from service.quant.task_dispatch_service import claim_next_task, create_fetch_bars_task, list_tasks, mark_task_failed, mark_task_success, reset_task


bp = Blueprint("quant_client_routes", __name__, url_prefix="/never_guess_my_usage/quant")


@bp.route("/client/tasks/create", methods=["POST"])
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


@bp.route("/client/tasks/list", methods=["GET"])
@require_admin_auth
def quant_client_task_list():
    limit = request.args.get("limit", default=100, type=int) or 100
    limit = max(1, min(limit, 500))
    return success_response(data=list_tasks(limit=limit))


@bp.route("/client/tasks/reset", methods=["POST"])
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


@bp.route("/client/tasks/claim", methods=["POST"])
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


@bp.route("/client/tasks/report", methods=["POST"])
@require_auth
def quant_client_task_report(user, password):
    del user, password
    import_result = None
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

        # 先 import_bundle，成功后再 mark_task_success。
        # 万一 import_bundle 抛异常（解析失败 / SQLite 损坏 / UNIQUE 冲突 / 磁盘满等），
        # 不能让 task 永远卡 leased——否则 _recycle_expired_leases 会回收成 pending，
        # 下个 agent 又 claim 同一个 task_id，无限循环。
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

        task = mark_task_success(task_id=task_id, client_id=client_id, import_batch=import_result, message=message or "客户端上报成功")
        return success_response(data=task, msg="任务上报成功")
    except Exception as exc:
        # 把 task 状态从 leased/pending → failed，避免被 recycle 反复执行。
        # 注意：此时任务可能仍处于 leased（import_bundle 失败时），必须显式标 failed。
        try:
            mark_task_failed(
                task_id=task_id,
                client_id=client_id,
                message=f"服务端处理失败（{type(exc).__name__}）：{exc}",
            )
        except Exception as inner:
            logging.getLogger("quant.client_report").warning(
                "mark_task_failed_after_import_failed_failed task_id=%s err=%s",
                task_id, inner,
            )
        return error_response(f"上报任务结果失败: {exc}")
