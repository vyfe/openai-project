import json

from openai import APIError, AuthenticationError, RateLimitError

from model.repositories.log_repository import set_log
from service.host_service import blacklist_host


def handle_api_exception(exc, logger, user=None, model=None, dialog_content=None, url_index=None):
    logger.error(f"API请求异常: {str(exc)}, 类型: {type(exc).__name__}")
    if user and model:
        error_msg = f"API Error: {str(exc)}"
        set_log(user, 0, model, json.dumps({"error": error_msg, "content": dialog_content or ""}))
    if url_index is not None:
        blacklist_host(url_index, logger=logger)
    if isinstance(exc, AuthenticationError):
        error_details = getattr(exc, "body", {}) or {}
        error_message = error_details.get("message", str(exc)) if isinstance(error_details, dict) else str(exc)
        if "网段" in error_message or "ip" in error_message.lower() or "whitelist" in error_message.lower():
            return {
                "success": False,
                "msg": "API密钥访问受限：当前IP不在白名单中，请联系管理员或更换API服务",
                "error_type": "IP_RESTRICTION",
            }
        return {"success": False, "msg": f"认证失败: {error_message}", "error_type": "AUTHENTICATION_ERROR"}
    if isinstance(exc, RateLimitError):
        return {"success": False, "msg": "请求频率超限，请稍后再试", "error_type": "RATE_LIMIT_ERROR"}
    if isinstance(exc, APIError):
        error_details = getattr(exc, "body", {}) or {}
        error_message = error_details.get("message", str(exc)) if isinstance(error_details, dict) else str(exc)
        return {"success": False, "msg": f"API错误: {error_message}", "error_type": "API_ERROR"}
    return {"success": False, "msg": f"请求失败: {str(exc)}", "error_type": "GENERAL_ERROR"}


def generate_sse_error(error_msg, error_type="GENERAL_ERROR"):
    error_response = {
        "success": False,
        "msg": error_msg,
        "done": True,
        "error": {
            "success": False,
            "msg": error_msg,
            "error_type": error_type,
        },
    }
    yield f"data: {json.dumps(error_response)}\n\n"
