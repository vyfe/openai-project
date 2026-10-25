"""音色与音乐接口共用的鉴权、错误封装与请求体解析。"""
from functools import wraps

from flask import request
from werkzeug.exceptions import RequestEntityTooLarge

from dto.common import error_response
from service.auth_service import require_admin_auth
from service.minimax_client import VoiceError, require


def minimax_endpoint(service_class, mutating=False):
    """把服务实例、串行锁和统一错误响应包在业务函数外面。"""

    def decorate(func):
        @wraps(func)
        @require_admin_auth
        def wrapped(*args, **kwargs):
            try:
                service = service_class()
                if mutating:
                    # 同一凭据下的付费操作串行执行，避免并发重复提交。
                    with service.store.locked("operation", blocking=False):
                        return func(service, *args, **kwargs)
                return func(service, *args, **kwargs)
            except VoiceError as exc:
                return {**error_response(str(exc)), "code": exc.code, "uncertain": exc.uncertain}, exc.status
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
