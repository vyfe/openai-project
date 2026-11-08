"""集中权限服务：角色规范化、有效权限、模块检查、管理员检查与资源归属策略。

授权模型遵循「每请求校验、默认拒绝、资源级检查」（OWASP Authorization Cheat Sheet）。

约定：
- 真实授权的唯一来源是平台库 ``user_role`` 表；``User.role`` 与 token 内嵌的旧角色
  只是兼容投影，永远不能恢复已撤销的权限。
- 角色集合：``chat`` / ``quant`` / ``sound`` 为业务角色，``admin`` 为管理员。
  含 ``admin`` 时规范化为 ``["admin"]``，业务角色不能推导出管理员身份。
"""
from dataclasses import dataclass
from typing import Iterable, Optional

from flask import g

# ---------------------------------------------------------------------------
# 角色常量
# ---------------------------------------------------------------------------

ROLE_CHAT = "chat"
ROLE_QUANT = "quant"
ROLE_SOUND = "sound"
ROLE_ADMIN = "admin"

#: 普通账号角色的固定排序
BUSINESS_ROLE_ORDER = (ROLE_CHAT, ROLE_QUANT, ROLE_SOUND)
#: 全部合法角色
ALL_ROLES = BUSINESS_ROLE_ORDER + (ROLE_ADMIN,)
ROLE_SET = frozenset(ALL_ROLES)

#: 兼容字段 User.role 的取值
COMPAT_ROLE_ADMIN = "admin"
COMPAT_ROLE_USER = "user"

#: 平台迁移关键版本；启动时缺失即阻止业务启动
PLATFORM_MIGRATION_VERSION = "2026-11-08-user-ownership"


class RoleValidationError(ValueError):
    """角色输入非法（未知角色、错误类型、空集合）。"""


# ---------------------------------------------------------------------------
# 规范化
# ---------------------------------------------------------------------------

def normalize_roles(raw: Iterable, *, allow_empty: bool = False) -> list:
    """把任意输入规范化为合法角色列表。

    - 只接受字符串组成的数组；标量、空串、None 视为非法。
    - 未知角色抛 :class:`RoleValidationError`。
    - 含 ``admin`` 时归一为 ``["admin"]``。
    - 普通账号按 ``chat, quant, sound`` 固定顺序返回。
    """
    if raw is None:
        if allow_empty:
            return []
        raise RoleValidationError("角色不能为空")
    if isinstance(raw, (str, bytes)) or not isinstance(raw, (list, tuple, set, frozenset)):
        raise RoleValidationError("角色必须是数组")

    collected = []
    for item in raw:
        if not isinstance(item, str):
            raise RoleValidationError("角色必须是字符串数组")
        role = item.strip()
        if not role:
            raise RoleValidationError("角色不能为空")
        if role not in ROLE_SET:
            raise RoleValidationError(f"未知角色: {role}")
        if role not in collected:
            collected.append(role)

    if ROLE_ADMIN in collected:
        return [ROLE_ADMIN]
    if not collected:
        if allow_empty:
            return []
        raise RoleValidationError("至少需要选择一个角色")
    return [role for role in BUSINESS_ROLE_ORDER if role in collected]


def sort_roles(roles: Iterable) -> list:
    """按固定顺序排列角色，管理员保持单元素。"""
    role_list = list(roles or [])
    if ROLE_ADMIN in role_list:
        return [ROLE_ADMIN]
    return [role for role in BUSINESS_ROLE_ORDER if role in role_list]


def to_compat_role(roles: Iterable) -> str:
    """把角色集合投影为兼容字段 ``role``（admin/user）。"""
    role_list = list(roles or [])
    return COMPAT_ROLE_ADMIN if ROLE_ADMIN in role_list else COMPAT_ROLE_USER


def compat_role_to_roles(raw_role: str) -> list:
    """把旧客户端的单值 role 映射为角色集合。"""
    value = (raw_role or "").strip().lower()
    if value == COMPAT_ROLE_ADMIN:
        return [ROLE_ADMIN]
    if value == COMPAT_ROLE_USER:
        return [ROLE_CHAT]
    raise RoleValidationError(f"未知兼容角色: {raw_role}")


def merge_compat_and_roles(payload_roles, compat_role, existing_roles) -> list:
    """合并新前端 roles 与旧客户端兼容 role。

    - 同时提交 roles 与兼容 role 且二者不一致 → 抛 :class:`RoleValidationError`。
    - 仅提交 roles → 以 roles 为准。
    - 仅提交兼容 role：
      - 与账号当前兼容投影一致 → 保留原组合角色（旧客户端保存普通资料不丢权限）；
      - 明确从 user 升 admin → ``["admin"]``；从 admin 降 user → ``["chat"]``。
    - 两者都未提交 → 保留原组合角色。
    """
    has_roles = payload_roles is not None
    has_compat = compat_role is not None and str(compat_role).strip() != ""

    if has_roles and has_compat:
        normalized = normalize_roles(payload_roles)
        compat_roles = compat_role_to_roles(compat_role)
        if to_compat_role(normalized) != to_compat_role(compat_roles):
            raise RoleValidationError("roles 与兼容 role 不一致")
        return normalized
    if has_roles:
        return normalize_roles(payload_roles)
    if has_compat:
        current_compat = to_compat_role(existing_roles or [])
        if str(compat_role).strip().lower() == current_compat:
            return sort_roles(existing_roles or [])
        return compat_role_to_roles(compat_role)
    return sort_roles(existing_roles or [])


# ---------------------------------------------------------------------------
# 有效权限
# ---------------------------------------------------------------------------

def effective_permissions(roles: Iterable) -> frozenset:
    """把角色集合换算为有效权限（模块名 + admin）。"""
    role_list = list(roles or [])
    if ROLE_ADMIN in role_list:
        return frozenset({ROLE_CHAT, ROLE_QUANT, ROLE_SOUND, ROLE_ADMIN})
    return frozenset(role for role in role_list if role in ROLE_SET)


def is_admin(roles: Iterable) -> bool:
    return ROLE_ADMIN in list(roles or [])


def has_module(roles: Iterable, module: str) -> bool:
    """判断是否具备某业务模块的访问权。"""
    return module in effective_permissions(roles)


def has_any_module(roles: Iterable, modules: Iterable) -> bool:
    permissions = effective_permissions(roles)
    return any(module in permissions for module in modules)


# ---------------------------------------------------------------------------
# 请求上下文
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AuthContext:
    """当前请求的认证主体快照。"""

    user_id: int
    username: str
    roles: tuple
    is_admin: bool

    @property
    def permissions(self) -> frozenset:
        return effective_permissions(self.roles)

    def can_access(self, module: str) -> bool:
        return has_module(self.roles, module)

    def owns(self, owner_user_id) -> bool:
        """资源归属检查：管理员可见全部，普通用户仅限本人资源。"""
        if self.is_admin:
            return True
        if owner_user_id is None:
            return False
        try:
            return int(owner_user_id) == int(self.user_id)
        except (TypeError, ValueError):
            return False

    def to_snapshot(self) -> dict:
        """账号快照，供 login / refresh / auth/me 共用。"""
        return {
            "user_id": self.user_id,
            "username": self.username,
            "roles": list(self.roles),
            "role": to_compat_role(self.roles),
        }


def set_auth_context(context: AuthContext) -> AuthContext:
    g._huiliao_auth_context = context
    return context


def get_auth_context() -> Optional[AuthContext]:
    return getattr(g, "_huiliao_auth_context", None)


def current_auth_context() -> AuthContext:
    """取当前请求的认证主体；缺失说明装饰器未生效，属于编程错误。"""
    context = get_auth_context()
    if context is None:
        raise RuntimeError("当前请求缺少认证上下文")
    return context


def current_user_id() -> int:
    """当前登录用户的稳定主键，用于资源归属赋值。"""
    return current_auth_context().user_id


def clear_auth_context() -> None:
    if hasattr(g, "_huiliao_auth_context"):
        del g._huiliao_auth_context


def build_auth_context(user_obj, roles: Optional[Iterable] = None) -> AuthContext:
    """从 User 记录构造认证上下文；roles 缺省时由调用方从数据库读取。"""
    role_list = sort_roles(roles or [])
    return set_auth_context(
        AuthContext(
            user_id=user_obj.id,
            username=user_obj.username,
            roles=tuple(role_list),
            is_admin=ROLE_ADMIN in role_list,
        )
    )


def active_module_owner(user_id: int, role: str):
    """后台执行同样读取当前账号状态；撤权和软删除立即停止新任务。"""
    from model.entities import User
    from model.repositories.user_repository import get_user_roles
    user = User.get_or_none((User.id == user_id) & (User.is_active == True) & User.deleted_at.is_null(True))
    if user is None or not has_module(get_user_roles(user.id), role):
        return None
    return user
