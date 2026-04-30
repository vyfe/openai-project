import json
import os
import time
from datetime import datetime

import requests
from flask import Blueprint, Response, current_app, jsonify, request

import sqlitelog
from conf.runtime import runtime_state
from dto.auth_dto import LoginRequest, RefreshTokenRequest, RegisterRequest, ResetPasswordRequest
from dto.chat_dto import ChatRequest, ImageChatRequest, StreamCancelRequest, StreamChatRequest
from dto.common import get_request_data
from dto.dialog_dto import DialogContentRequest, DialogDeleteRequest, DialogTitleUpdateRequest
from model.repositories.user_repository import create_user, get_user_browser_conf, get_user_by_username, set_user_browser_conf
from service.auth_service import issue_auth_tokens, refresh_access_token, require_auth, revoke_user_tokens, verify_credentials
from service.chat_service import run_chat_completion
from service.common_service import generate_sse_error
from service.dialog_service import delete_user_dialogs, get_dialog_content, get_recent_dialogs, rename_dialog
from service.image_service import generate_or_edit_image
from service.model_service import get_cached_models, get_grouped_models
from service.notification_service import fetch_notification_count, fetch_notifications
from service.stream_service import cancel_stream_request, stream_chat
from service.system_prompt_service import fetch_system_prompts_grouped
from service.usage_service import get_usage_summary


public_bp = Blueprint("public_routes", __name__, url_prefix="/never_guess_my_usage")


@public_bp.route("/models/grouped", methods=["GET", "POST"])
def get_grouped_models_endpoint():
    try:
        return {"success": True, "grouped_models": get_grouped_models(logger=current_app.logger)}, 200
    except Exception as exc:
        current_app.logger.error(f"获取分组模型列表异常: {exc}")
        return {"success": False, "msg": f"获取分组模型列表失败: {exc}"}, 200


@public_bp.route("/models", methods=["GET", "POST"])
def get_models():
    try:
        return {"success": True, "models": get_cached_models(logger=current_app.logger)}, 200
    except Exception as exc:
        current_app.logger.error(f"获取模型列表异常: {exc}")
        return {"success": False, "msg": f"获取模型列表失败: {exc}"}, 200


@public_bp.route("/test")
def health_check():
    current_app.logger.info(get_request_data())
    try:
        return json.dumps(get_request_data().to_dict()), 200
    except Exception:
        return {"msg": "json no ok"}, 200


@public_bp.route("/login", methods=["POST"])
def login():
    req = LoginRequest.from_data(get_request_data())
    if not req.user:
        return {"success": False, "msg": "用户名不能为空"}, 200
    is_valid, error_msg, user_info = verify_credentials(req.user, req.password)
    if not is_valid:
        return {"success": False, "msg": error_msg}, 200
    token_bundle = issue_auth_tokens(user_info.get("username", req.user), user_info.get("role", "user"))
    return {"success": True, "msg": "登录成功", "data": {**user_info, **token_bundle}}, 200


@public_bp.route("/token/refresh", methods=["POST"])
def refresh_token():
    req = RefreshTokenRequest.from_data(request.get_json(silent=True) or {})
    if not req.refresh_token:
        return {"success": False, "msg": "缺少 refresh_token"}, 401
    ok, msg, token_bundle = refresh_access_token(req.refresh_token)
    if not ok:
        return {"success": False, "msg": msg or "刷新令牌失败"}, 401
    return {"success": True, "msg": "刷新成功", "data": token_bundle}, 200


@public_bp.route("/register", methods=["POST"])
def register():
    try:
        req = RegisterRequest.from_data(get_request_data())
        error = req.validate()
        if error:
            return jsonify({"success": False, "msg": error}), 200
        if sqlitelog.User.select().where(sqlitelog.User.username == req.username).exists():
            return jsonify({"success": False, "msg": "用户名已存在"}), 200
        api_key = req.api_key or runtime_state.settings.default_api_key
        user = create_user(req.username, req.password, api_key if api_key else None)
        return jsonify({"success": True, "msg": "注册成功", "data": {"username": user.username}}), 200
    except Exception as exc:
        current_app.logger.error(f"注册失败: {exc}")
        return jsonify({"success": False, "msg": f"注册失败: {exc}"}), 200


@public_bp.route("/set_info")
def data_check():
    data = get_request_data()
    current_app.logger.info(data)
    try:
        if data.get("param"):
            param = data.get("param").split(",")
            return sqlitelog.message_query(data.get("info"), param), 200
        return sqlitelog.message_query(data.get("info")), 200
    except Exception:
        return {"msg": "json no ok"}, 200


def allowed_file(filename):
    return "." not in filename or filename.rsplit(".", 1)[1].lower() in runtime_state.allowed_extensions


@public_bp.route("/download", methods=["POST"])
def upload():
    if "file" not in request.files:
        return {"msg": "no file"}, 200
    file = request.files["file"]
    if file.filename == "":
        return {"msg": "no filename"}, 200
    if file.content_length > 20 * 1024 * 1024:
        return {"msg": "more than 20M"}, 200
    if file and allowed_file(file.filename):
        filename = str(time.time()) + "-" + file.filename
        file_fullname = os.path.join(runtime_state.settings.upload_dir, filename)
        file.save(file_fullname)
        os.chmod(file_fullname, 0o755)
        return {"content": f":4567/download/{filename}"}, 200
    return {"msg": "文件格式不支持，只支持pdf、通用图片等"}, 200


@public_bp.route("/split", methods=["POST", "GET"])
@require_auth
def dialog(user, password):
    payload = ChatRequest.from_data(get_request_data(as_text=True))
    return run_chat_completion(user, payload, current_app.logger)


@public_bp.route("/split_stream", methods=["POST", "GET"])
@require_auth
def dialog_stream(user, password):
    payload = StreamChatRequest.from_data(get_request_data(as_text=True))
    try:
        return stream_chat(user, payload, current_app.logger)
    except Exception as exc:
        current_app.logger.error(f"流式对话异常: {exc}")
        return Response(
            generate_sse_error(f"流式对话异常: {str(exc)}", "GENERAL_ERROR"),
            mimetype="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "close"},
        )


@public_bp.route("/split_stream_cancel", methods=["POST"])
@require_auth
def dialog_stream_cancel(user, password):
    payload = StreamCancelRequest.from_data(get_request_data(as_text=True))
    if not payload.request_id:
        return {"success": False, "msg": "missing request_id"}, 200
    cancelled = cancel_stream_request(payload.request_id)
    return {"success": cancelled, "msg": "cancelled" if cancelled else "not_found"}, 200


@public_bp.route("/split_pic", methods=["POST"])
@require_auth
def dialog_pic(user, password):
    payload = ImageChatRequest.from_data(get_request_data(as_text=True))
    return generate_or_edit_image(user, payload, current_app.logger)


@public_bp.route("/split_his", methods=["POST"])
@require_auth
def dialog_his(user, password):
    current_app.logger.info(user)
    return {"content": get_recent_dialogs(user)}, 200


@public_bp.route("/split_his_content", methods=["POST"])
@require_auth
def dialog_content(user, password):
    try:
        req = DialogContentRequest.from_data(get_request_data(as_text=True))
        result = get_dialog_content(user, req.dialog_id)
        return {"content": result}, 200
    except Exception:
        return {"msg": "api return content not ok"}, 200


@public_bp.route("/usage", methods=["GET", "POST"])
@require_auth
def get_usage(user, password):
    try:
        return get_usage_summary(user), 200
    except requests.exceptions.RequestException as exc:
        current_app.logger.error(f"获取用量API请求异常: {exc}")
        return {"success": False, "msg": f"API请求失败: {exc}"}, 200


@public_bp.route("/browser_conf/get", methods=["GET", "POST"])
@require_auth
def get_browser_conf(user, password):
    try:
        browser_conf = get_user_browser_conf(user) or ""
        return {"success": True, "data": browser_conf}, 200
    except Exception as exc:
        current_app.logger.error(f"获取浏览器配置失败: {exc}")
        return {"success": False, "msg": f"获取配置失败: {exc}"}, 200


@public_bp.route("/browser_conf/save", methods=["POST"])
@require_auth
def save_browser_conf(user, password):
    try:
        data = request.get_json(silent=True) or request.values
        browser_conf = data.get("browser_conf", "")
        success, msg = set_user_browser_conf(user, browser_conf)
        return {"success": success, "msg": msg}, 200
    except Exception as exc:
        current_app.logger.error(f"保存浏览器配置失败: {exc}")
        return {"success": False, "msg": f"保存配置失败: {exc}"}, 200


@public_bp.route("/split_his_delete", methods=["POST"])
@require_auth
def dialog_delete(user, password):
    req = DialogDeleteRequest.from_data(get_request_data(as_text=True))
    return {"success": True, "deleted_count": delete_user_dialogs(user, req.dialog_ids)}


@public_bp.route("/update_dialog_title", methods=["POST"])
@require_auth
def update_dialog_title(user, password):
    req = DialogTitleUpdateRequest.from_data(get_request_data(as_text=True))
    if req.dialog_id is None or not req.new_title:
        return {"success": False, "msg": "dialog_id 和 new_title 参数不能为空"}, 200
    success = rename_dialog(user, req.dialog_id, req.new_title)
    if success:
        return {"success": True, "msg": "更新成功"}, 200
    return {"success": False, "msg": "更新失败，可能是对话不存在或不属于该用户"}, 200


@public_bp.route("/system_prompt", methods=["GET"])
def system_prompt():
    return {"msg": "api return content not ok"}, 200


@public_bp.route("/system_prompts_by_group", methods=["GET"])
def get_system_prompts_by_group():
    try:
        return {"success": True, "groups": fetch_system_prompts_grouped()}, 200
    except Exception as exc:
        current_app.logger.error(f"获取按组分类的系统提示词失败: {exc}")
        return {"success": False, "msg": f"获取系统提示词失败: {exc}"}, 200


@public_bp.route("/notifications", methods=["GET"])
def get_notifications():
    try:
        page = request.args.get("page", 1, type=int)
        page_size = request.args.get("page_size", 10, type=int)
        status = request.args.get("status", "active", type=str)
        if page < 1:
            page = 1
        if page_size < 1 or page_size > 100:
            page_size = 10
        offset = (page - 1) * page_size
        notifications = fetch_notifications(status=status, limit=page_size, offset=offset)
        total_count = fetch_notification_count(status=status)
        return {
            "success": True,
            "data": {
                "list": notifications,
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total": total_count,
                    "pages": (total_count + page_size - 1) // page_size if total_count > 0 else 1,
                },
            },
        }, 200
    except Exception as exc:
        current_app.logger.error(f"获取通知公告列表失败: {exc}")
        return {"success": False, "msg": f"获取通知公告列表失败: {exc}"}, 200


@public_bp.route("/del_password", methods=["POST"])
@require_auth
def user_reset_password(user, password):
    try:
        req = ResetPasswordRequest.from_data(get_request_data(as_text=True))
        if not req.current_password:
            return jsonify({"success": False, "msg": "当前密码不能为空"})
        if not req.new_password:
            return jsonify({"success": False, "msg": "新密码不能为空"})
        is_valid_current, error_msg, _ = verify_credentials(user, req.current_password)
        if not is_valid_current:
            return jsonify({"success": False, "msg": error_msg or "当前密码不正确"})
        success, msg = sqlitelog.reset_user_password(user, req.new_password)
        if not success:
            return jsonify({"success": False, "msg": msg})
        if req.new_api_key:
            user_obj = get_user_by_username(user)
            if user_obj:
                user_obj.api_key = req.new_api_key
                user_obj.updated_at = datetime.now()
                user_obj.save()
        revoke_user_tokens(user)
        return jsonify({"success": True, "msg": "密码更新成功，请重新登录"})
    except Exception as exc:
        current_app.logger.error(f"重置密码失败: {exc}")
        return jsonify({"success": False, "msg": f"重置密码失败: {exc}"})
