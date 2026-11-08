"""音色与音乐接口共用的鉴权、错误封装与请求体解析。"""
from functools import wraps

from flask import request
from werkzeug.exceptions import RequestEntityTooLarge

from dto.common import error_response
from service.auth_service import require_module_auth
from service.minimax_client import VoiceError, require
from service.permission_service import ROLE_SOUND, current_auth_context


def minimax_endpoint(service_class, mutating=False, required_role: str = ROLE_SOUND):
    """把服务实例、串行锁和统一错误响应包在业务函数外面。

    ``required_role`` 决定该端点需要的业务角色：个人音色/音乐能力为 ``sound``，
    全局同步、profile 与保活等运维端点传 ``admin``。
    """

    def decorate(func):
        @wraps(func)
        @require_module_auth(required_role)
        def wrapped(*args, **kwargs):
            try:
                service = service_class()
                if mutating:
                    # 同一凭据下的付费操作串行执行，避免并发重复提交。
                    with service.store.locked("operation", blocking=False):
                        result = func(service, *args, **kwargs)
                else:
                    result = func(service, *args, **kwargs)
                return result if current_auth_context().is_admin else _private_result(result)
            except VoiceError as exc:
                return {**error_response(str(exc)), "code": exc.code, "uncertain": exc.uncertain, **({"error_type": "RESOURCE_NOT_FOUND"} if exc.status == 404 else {})}, exc.status
            except RequestEntityTooLarge:
                return error_response("上传请求超过 50 MB，请将每个音频文件控制在 20 MB 以内。"), 413
            except Exception:
                # 不将含凭据的第三方异常或用户录音、正文、歌词写入日志和响应。
                return {**error_response("本地操作未完成。云端操作可能已执行，请先检查记录，避免重复提交。"), "uncertain": True}, 500
        return wrapped
    return decorate


def json_body():
    data = request.get_json(silent=True)
    require(isinstance(data, dict), "请求内容必须是 JSON 对象。")
    return data


def _private_result(value):
    """保留作品可播放状态，普通用户只经认证音频接口读取。"""
    if isinstance(value, dict):
        return {key: None if key == "audio_url" else _private_result(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_private_result(item) for item in value]
    return value
