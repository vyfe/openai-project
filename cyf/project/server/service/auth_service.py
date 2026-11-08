"""认证与鉴权服务。

授权模型（与 ``doc/huiliao-login-permissions-development-plan.md` §5.2 对齐）：

- access / refresh 仍是随机不透明 token，保存在 ``User.token`` 的 JSON 中；
- 授权只读取平台库 ``user_role``，token 内嵌的旧 ``role`` 仅作兼容投影，
  永远不能恢复已撤销的权限；
- access token 过期不会连带清除仍有效的 refresh token；
- 停用、软删除、改密或显式撤销后，原凭据不能恢复会话；
- 401 表示缺失 / 失效凭据或账号停用；403 表示已认证但缺少模块或操作权限。
"""
import inspect
import secrets
import time
from functools import wraps

from flask import request

from conf.logging_config import set_log_user
from conf.runtime import runtime_state
from dto.common import (
    ERROR_TYPE_PERMISSION_DENIED,
    ERROR_TYPE_UNAUTHENTICATED,
    get_request_data,
)
from model.repositories.user_repository import (
    find_user_by_token,
    get_active_token_count,
    get_user_by_username,
    get_user_roles,
    get_user_token_payload,
    set_user_token_payload,
    verify_user_password,
)
from service.permission_service import (
    ROLE_ADMIN,
    build_auth_context,
    has_module,
    sort_roles,
    to_compat_role,
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


def _has_auth_header() -> bool:
    return bool(request.headers.get("Authorization", "").strip())


# ---------------------------------------------------------------------------
# 错误协议
# ---------------------------------------------------------------------------

def unauthenticated_response(msg="认证失败"):
    return {"success": False, "msg": msg, "error_type": ERROR_TYPE_UNAUTHENTICATED}, 401


def permission_denied_response(msg="权限不足", required_role=None):
    body = {"success": False, "msg": msg, "error_type": ERROR_TYPE_PERMISSION_DENIED}
    if required_role:
        body["required_role"] = required_role
    return body, 403


# ---------------------------------------------------------------------------
# Token 签发与读取
# ---------------------------------------------------------------------------

def _coerce_roles(roles) -> list:
    """把签发入口的 roles 参数规范为角色列表（兼容旧的单值字符串）。"""
    if roles is None:
        return []
    if isinstance(roles, str):
        return sort_roles([roles] if roles in ("admin", "user") else [])
    return sort_roles(roles)


def issue_auth_tokens(username: str, roles) -> dict:
    now_ts = _now_ts()
    role_list = _coerce_roles(roles)
    token_bundle = {
        "access_token": secrets.token_urlsafe(32),
        "access_token_expires_at": now_ts + runtime_state.settings.access_token_ttl_seconds,
        "refresh_token": secrets.token_urlsafe(48),
        "refresh_token_expires_at": now_ts + runtime_state.settings.refresh_token_ttl_seconds,
        "session_id": secrets.token_hex(12),
        # 兼容投影：仅供旧客户端展示，授权一律读取数据库角色。
        "role": to_compat_role(role_list),
    }
    set_user_token_payload(username, token_bundle)
    return token_bundle


def issue_access_token(username: str, roles, session_id: str) -> dict:
    now_ts = _now_ts()
    access_token = secrets.token_urlsafe(32)
    access_expires_at = now_ts + runtime_state.settings.access_token_ttl_seconds
    token_payload = get_user_token_payload(username) or {}
    token_payload.update(
        {
            "access_token": access_token,
            "access_token_expires_at": access_expires_at,
            "session_id": session_id,
            "role": to_compat_role(_coerce_roles(roles)),
        }
    )
    set_user_token_payload(username, token_payload)
    return {"access_token": access_token, "access_token_expires_at": access_expires_at}


def _load_token_subject(token: str, token_type: str) -> tuple[object, dict]:
    """定位 token 对应的 User 与凭据载荷，失败抛 ValueError。

    角色一律从数据库读取，token 内嵌的旧角色不参与授权。
    access 过期时保留仍有效的 refresh；refresh 过期才清空整个凭据。
    """
    if not token:
        raise ValueError("缺少令牌")
    found = find_user_by_token(token, token_type)
    if not found:
        raise ValueError("令牌无效或已过期")
    user_obj, token_payload = found
    expire_key = "access_token_expires_at" if token_type == "access" else "refresh_token_expires_at"
    if int(token_payload.get(expire_key, 0) or 0) <= _now_ts():
        if token_type == "refresh":
            set_user_token_payload(user_obj.username, None)
        raise ValueError("令牌已过期")
    return user_obj, token_payload


def get_token_payload(token: str, token_type: str) -> tuple[bool, str, dict]:
    """读取 token 对应的认证主体快照（兼容旧调用点）。"""
    try:
        user_obj, token_payload = _load_token_subject(token, token_type)
    except ValueError as exc:
        return False, str(exc), {}
    roles = get_user_roles(user_obj.id)
    return True, "", {
        "user_id": user_obj.id,
        "username": user_obj.username,
        "roles": roles,
        "role": to_compat_role(roles),
        "session_id": token_payload.get("session_id", ""),
    }


def revoke_user_tokens(username: str):
    set_user_token_payload(username, None)


def authenticate_request_token(required_role: str = None) -> tuple[bool, str, dict]:
    """兼容旧调用点：按 token 认证，并可选校验模块角色。"""
    token = _extract_bearer_token()
    if not token:
        return False, "缺少访问令牌", {}
    ok, msg, payload = get_token_payload(token, "access")
    if not ok:
        return False, msg, {}
    if required_role and not has_module(payload.get("roles", []), required_role):
        return False, "权限不足", {}
    return True, "", payload


def refresh_access_token(refresh_token: str) -> tuple[bool, str, dict]:
    """用 refresh token 换新 access token，并返回当前账号快照。"""
    try:
        user_obj, token_payload = _load_token_subject(refresh_token, "refresh")
    except ValueError as exc:
        return False, str(exc), {}
    username = user_obj.username
    session_id = token_payload.get("session_id", "")
    current_payload = get_user_token_payload(username) or {}
    if current_payload.get("refresh_token") != refresh_token:
        return False, "刷新令牌已失效，请重新登录", {}
    roles = get_user_roles(user_obj.id)
    new_access = issue_access_token(username, roles, session_id)
    return True, "", {
        **new_access,
        "refresh_token": refresh_token,
        "refresh_token_expires_at": current_payload.get("refresh_token_expires_at"),
        "user_id": user_obj.id,
        "username": username,
        "roles": roles,
        "role": to_compat_role(roles),
    }


def verify_credentials(user, password):
    """校验账号密码，返回 (是否成功, 错误信息, User 或 None)。

    无论走数据库认证还是配置凭据分支，都必须命中平台库中的启用账号，
    以保证角色与停用状态由数据库统一裁决。
    """
    username = str(user or "").strip()
    if not username:
        return False, "用户名不能为空", None
    if runtime_state.use_db_auth:
        success, error_msg, user_obj = verify_user_password(username, password, None)
        if success and user_obj:
            return success, error_msg, user_obj
        return success, error_msg, None
    # 配置凭据分支：账号必须已迁移进平台库，否则无法裁决角色与停用状态。
    user_obj = get_user_by_username(username)
    if not user_obj:
        return False, "用户不存在或未授权", None
    if runtime_state.user_credentials.get(username) != password:
        return False, "密码错误", None
    return True, None, user_obj


# ---------------------------------------------------------------------------
# 认证主体解析
# ---------------------------------------------------------------------------

def _resolve_auth_context():
    """解析当前请求的认证主体，返回 (context, error_response)。

    - 显式携带 Authorization 头：bearer 无效直接 401，不回退到请求体凭据；
    - 未携带 Authorization 头：兼容旧的用户名/密码调用，同样执行角色校验。
    """
    if _has_auth_header():
        token = _extract_bearer_token()
        if not token:
            return None, unauthenticated_response("缺少访问令牌")
        try:
            user_obj, _payload = _load_token_subject(token, "access")
        except ValueError as exc:
            return None, unauthenticated_response(str(exc) or "认证失败")
        context = build_auth_context(user_obj, get_user_roles(user_obj.id))
        return context, None

    data = get_request_data()
    username = str(data.get("user", "")).strip()
    password = str(data.get("password", "")).strip()
    is_valid, error_msg, user_obj = verify_credentials(username, password)
    if not is_valid or user_obj is None:
        return None, unauthenticated_response(error_msg or "认证失败")
    context = build_auth_context(user_obj, get_user_roles(user_obj.id))
    return context, None


def _bind_context(func, context, kwargs):
    """把认证主体注入到处理函数；只注入其签名里显式声明的参数。

    管理端路由多数是无参函数，若无条件注入 ``user`` / ``password`` 会直接 TypeError；
    带 ``**kwargs`` 的包装器同样不注入，避免把参数透传给业务函数。
    """
    try:
        parameters = inspect.signature(func, follow_wrapped=False).parameters
    except (TypeError, ValueError):
        parameters = {}
    if "user" in parameters:
        kwargs["user"] = context.username
    if "password" in parameters:
        kwargs["password"] = ""
    set_log_user(context.username)
    return kwargs


# ---------------------------------------------------------------------------
# 装饰器
# ---------------------------------------------------------------------------

def require_auth(f):
    """已登录即可访问（不要求业务角色），用于个人设置、通知等通用能力。"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.method == "OPTIONS":
            return "", 200
        context, error = _resolve_auth_context()
        if error:
            return error
        return f(*args, **_bind_context(f, context, kwargs))

    return decorated_function


def require_module_auth(*modules):
    """要求具备任一业务模块权限（chat / quant / sound）。管理员天然具备全部模块。"""
    required = tuple(module for module in modules if module)
    if not required:
        raise ValueError("require_module_auth 至少需要一个模块")

    def decorate(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if request.method == "OPTIONS":
                return "", 200
            context, error = _resolve_auth_context()
            if error:
                return error
            if not any(context.can_access(module) for module in required):
                return permission_denied_response("权限不足", required_role=required[0])
            return f(*args, **_bind_context(f, context, kwargs))

        return decorated_function

    return decorate


def require_admin_auth(f):
    """要求管理员身份。"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.method == "OPTIONS":
            return "", 200
        context, error = _resolve_auth_context()
        if error:
            return error
        if not context.is_admin:
            return permission_denied_response("权限不足", required_role=ROLE_ADMIN)
        return f(*args, **_bind_context(f, context, kwargs))

    return decorated_function


def get_active_token_count_snapshot() -> int:
    return get_active_token_count()
