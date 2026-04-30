import secrets
import time
from functools import wraps

from flask import request

from conf.runtime import runtime_state
from dto.common import get_request_data
from model.repositories.user_repository import (
    find_user_by_token,
    get_active_token_count,
    get_user_by_username,
    get_user_token_payload,
    set_user_token_payload,
    verify_user_password,
)


def _now_ts() -> int:
    return int(time.time())


def _extract_bearer_token() -> str:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header:
        return ""
    prefix = "bearer "
    if auth_header.lower().startswith(prefix):
        return auth_header[len(prefix):].strip()
    return ""


def issue_auth_tokens(username: str, role: str) -> dict:
    now_ts = _now_ts()
    token_bundle = {
        "access_token": secrets.token_urlsafe(32),
        "access_token_expires_at": now_ts + runtime_state.settings.access_token_ttl_seconds,
        "refresh_token": secrets.token_urlsafe(48),
        "refresh_token_expires_at": now_ts + runtime_state.settings.refresh_token_ttl_seconds,
        "session_id": secrets.token_hex(12),
        "role": role,
    }
    set_user_token_payload(username, token_bundle)
    return token_bundle


def issue_access_token(username: str, role: str, session_id: str) -> dict:
    now_ts = _now_ts()
    access_token = secrets.token_urlsafe(32)
    access_expires_at = now_ts + runtime_state.settings.access_token_ttl_seconds
    token_payload = get_user_token_payload(username) or {}
    token_payload.update(
        {
            "access_token": access_token,
            "access_token_expires_at": access_expires_at,
            "session_id": session_id,
            "role": role,
        }
    )
    set_user_token_payload(username, token_payload)
    return {"access_token": access_token, "access_token_expires_at": access_expires_at}


def get_token_payload(token: str, token_type: str) -> tuple[bool, str, dict]:
    if not token:
        return False, "缺少令牌", {}
    found = find_user_by_token(token, token_type)
    if not found:
        return False, "令牌无效或已过期", {}
    user_obj, token_payload = found
    expire_key = "access_token_expires_at" if token_type == "access" else "refresh_token_expires_at"
    if int(token_payload.get(expire_key, 0) or 0) <= _now_ts():
        set_user_token_payload(user_obj.username, None)
        return False, "令牌已过期", {}
    return True, "", {
        "username": user_obj.username,
        "role": token_payload.get("role", user_obj.role),
        "session_id": token_payload.get("session_id", ""),
    }


def revoke_user_tokens(username: str):
    set_user_token_payload(username, None)


def authenticate_request_token(required_role: str = None) -> tuple[bool, str, dict]:
    token = _extract_bearer_token()
    if not token:
        return False, "缺少访问令牌", {}
    ok, msg, payload = get_token_payload(token, "access")
    if not ok:
        return False, msg, {}
    if required_role and payload.get("role") != required_role:
        return False, "权限不足", {}
    return True, "", payload


def refresh_access_token(refresh_token: str) -> tuple[bool, str, dict]:
    ok, msg, payload = get_token_payload(refresh_token, "refresh")
    if not ok:
        return False, msg, {}
    username = payload.get("username")
    role = payload.get("role")
    session_id = payload.get("session_id")
    if not username:
        return False, "刷新令牌无效", {}
    user_obj = get_user_by_username(username)
    if not user_obj:
        revoke_user_tokens(username)
        return False, "用户不存在或已禁用", {}
    current_payload = get_user_token_payload(username) or {}
    if current_payload.get("refresh_token") != refresh_token:
        return False, "刷新令牌已失效，请重新登录", {}
    new_access = issue_access_token(username, role or user_obj.role, session_id)
    return True, "", {
        **new_access,
        "refresh_token": refresh_token,
        "refresh_token_expires_at": current_payload.get("refresh_token_expires_at"),
    }


def verify_credentials(user, password):
    if runtime_state.use_db_auth:
        success, error_msg, user_obj = verify_user_password(user, password, None)
        if success and user_obj:
            return success, error_msg, {"username": user_obj.username, "role": user_obj.role}
        return success, error_msg, None
    if not user or user not in runtime_state.user_credentials:
        return False, "用户不存在或未授权", None
    if runtime_state.user_credentials[user] != password:
        return False, "密码错误", None
    return True, None, {"username": user, "role": "admin"}


def require_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.method == "OPTIONS":
            return "", 200
        token_ok, token_msg, token_payload = authenticate_request_token()
        if token_ok:
            kwargs["user"] = token_payload.get("username", "")
            kwargs["password"] = ""
            return f(*args, **kwargs)
        data = get_request_data()
        user = str(data.get("user", "")).strip()
        password = str(data.get("password", "")).strip()
        is_valid, error_msg, _ = verify_credentials(user, password)
        if not is_valid:
            return {"success": False, "msg": error_msg or token_msg or "认证失败"}, 401
        kwargs["user"] = user
        kwargs["password"] = password
        return f(*args, **kwargs)

    return decorated_function


def require_admin_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.method == "OPTIONS":
            return "", 200
        ok, msg, payload = authenticate_request_token(required_role="admin")
        if ok:
            return f(*args, **kwargs)
        data = get_request_data()
        user = str(data.get("user", "")).strip()
        password = str(data.get("password", "")).strip()
        success, error_msg, _ = verify_user_password(user, password, "admin")
        if not success:
            return {"success": False, "msg": error_msg or msg or "认证失败"}, 401
        return f(*args, **kwargs)

    return decorated_function


def get_active_token_count_snapshot() -> int:
    return get_active_token_count()
