"""量化资源归属策略。

权威归属字段为 ``owner_user_id``（平台库 ``User.id`` 的稳定主键）；
``created_by`` 只作展示与兼容，不再承担鉴权职责。客户端无法通过
``owner_user_id / username / created_by`` 改变身份——归属一律取自认证主体。

跨用户私有资源统一按「不存在」处理，避免暴露资源存在性。
"""
from typing import Optional

from service.permission_service import current_auth_context


class ResourceNotFoundError(LookupError):
    """资源不存在或不属于当前用户；路由层统一返回 404。"""


def current_owner_scope() -> tuple[int, bool]:
    """当前请求的 (owner_user_id, is_admin)。"""
    context = current_auth_context()
    return context.user_id, context.is_admin


def scope_by_owner(query, model, owner_user_id: Optional[int], is_admin: bool):
    """把查询收敛到可见范围：管理员全量，普通用户仅本人。

    ``owner_user_id`` 为 ``None`` 表示系统作用域（内部任务 / 迁移脚本），
    不做过滤；面向用户请求的路由必须显式传入认证主体的用户 ID。
    """
    if is_admin or owner_user_id is None:
        return query
    return query.where(model.owner_user_id == owner_user_id)


def owns_row(row, owner_user_id: Optional[int], is_admin: bool) -> bool:
    """判断一行记录是否属于当前用户。

    ``owner_user_id`` 为 ``None`` 表示系统作用域，同样放行。
    """
    if is_admin or owner_user_id is None:
        return True
    raw_owner = getattr(row, "owner_user_id", None)
    if raw_owner is None:
        # 归属缺失的历史记录默认仅管理员可处理。
        return False
    try:
        return int(raw_owner) == int(owner_user_id)
    except (TypeError, ValueError):
        return False


def assert_owned(row, owner_user_id: Optional[int], is_admin: bool, label: str = "资源"):
    """归属校验失败时抛 :class:`ResourceNotFoundError`。"""
    if not owns_row(row, owner_user_id, is_admin):
        raise ResourceNotFoundError(f"{label}不存在")
    return row


def validate_related_resources(owner_user_id, *, strategy_id=None, run_id=None, signal_id=None, operation_id=None):
    """写入前校验关联资源的所有者及父子关系，管理员也不能制造混合归属。"""
    from quant.entities import QuantOperationRecord, QuantStrategy, QuantStrategyRun, QuantStrategySignal

    def load(model, resource_id):
        if resource_id in (None, ""):
            return None
        row = model.get_or_none(model.id == int(resource_id))
        if row is None:
            raise ResourceNotFoundError("关联资源不存在")
        return row

    operation = load(QuantOperationRecord, operation_id)
    run = load(QuantStrategyRun, run_id)
    signal = load(QuantStrategySignal, signal_id)
    strategy_ids = {int(strategy_id)} if strategy_id not in (None, "") else set()
    for row in (operation, run, signal):
        if row is not None and row.strategy_id is not None:
            strategy_ids.add(row.strategy_id)
    if len(strategy_ids) > 1 or (run is not None and signal is not None and signal.run_id != run.id):
        raise ResourceNotFoundError("关联资源不一致")
    if operation is not None and operation.owner_user_id != owner_user_id:
        raise ResourceNotFoundError("关联资源不存在")
    for strategy_key in strategy_ids:
        strategy = load(QuantStrategy, strategy_key)
        if strategy.owner_user_id != owner_user_id:
            raise ResourceNotFoundError("关联资源不存在")


def require_quant_user(username: str):
    from model.repositories.user_repository import get_user_by_username
    from service.permission_service import active_module_owner, ROLE_QUANT
    user = get_user_by_username(username)
    if user is None or active_module_owner(user.id, ROLE_QUANT) is None:
        raise ValueError("账号未开通量化权限或已停用，请联系管理员")
    return user
