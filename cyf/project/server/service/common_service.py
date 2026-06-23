import json

from openai import APIError, AuthenticationError, RateLimitError

from model.repositories.log_repository import set_log
from service.host_service import blacklist_host


def _handle_anthropic_exception(exc, logger):
    """处理 Anthropic SDK 异常，返回错误响应字典或 None（交给后续处理）。"""
    try:
        import anthropic
    except ImportError:
        return None

    if isinstance(exc, anthropic.AuthenticationError):
        return {"success": False, "msg": f"Claude认证失败: {exc.message}", "error_type": "AUTHENTICATION_ERROR"}
    if isinstance(exc, anthropic.RateLimitError):
        return {"success": False, "msg": "Claude请求频率超限，请稍后再试", "error_type": "RATE_LIMIT_ERROR"}
    if isinstance(exc, anthropic.BadRequestError):
        return {"success": False, "msg": f"Claude请求参数错误: {exc.message}", "error_type": "BAD_REQUEST_ERROR"}
    if isinstance(exc, anthropic.PermissionDeniedError):
        return {"success": False, "msg": f"Claude权限不足: {exc.message}", "error_type": "PERMISSION_ERROR"}
    if isinstance(exc, anthropic.NotFoundError):
        return {"success": False, "msg": f"Claude模型或端点不存在: {exc.message}", "error_type": "NOT_FOUND_ERROR"}
    if isinstance(exc, anthropic.APIStatusError):
        if exc.status_code and exc.status_code >= 500:
            return {"success": False, "msg": f"Claude服务器错误({exc.status_code}): {exc.message}", "error_type": "API_ERROR"}
        return {"success": False, "msg": f"Claude API错误: {exc.message}", "error_type": "API_ERROR"}
    if isinstance(exc, anthropic.APIConnectionError):
        return {"success": False, "msg": "Claude网络连接失败，请检查网络", "error_type": "CONNECTION_ERROR"}
    return None  # 不是 Anthropic 异常，交给后续处理


def handle_api_exception(exc, logger, user=None, model=None, dialog_content=None, url_index=None):
    logger.error(f"API请求异常: {str(exc)}, 类型: {type(exc).__name__}")
    if user and model:
        error_msg = f"API Error: {str(exc)}"
        set_log(user, 0, model, json.dumps({"error": error_msg, "content": dialog_content or ""}))
    if url_index is not None:
        blacklist_host(url_index, logger=logger)

    # Anthropic 异常处理（优先级高于 OpenAI，因为调用方可能同时依赖两个 SDK）
    anthropic_result = _handle_anthropic_exception(exc, logger)
    if anthropic_result is not None:
        return anthropic_result

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
