"""平台库权限迁移：旧单值 ``User.role`` → ``user_role`` 成员关系。

迁移要点（对齐开发任务书 §5.6 第 3 步）：

- 旧 ``role=user`` 一次性回填 ``chat``，旧 ``role=admin`` 回填 ``admin``；
- 回填与「完成标记」写在同一个事务里，失败即整体回滚；
- 重复执行 / 重启不会补回已撤销的权限：只处理「完全没有角色行」的账号，
  已经拥有角色行的账号一律不动；
- 禁用账号保留角色但仍然禁用。

未知旧角色不猜测授权，直接阻止迁移并报告。
"""
from datetime import datetime

from model.db import db
from model.entities import PlatformSchemaMigration, User, UserRole
from service.permission_service import PLATFORM_MIGRATION_VERSION, ROLE_ADMIN, ROLE_CHAT

#: 旧单值角色到新角色的映射
LEGACY_ROLE_MAPPING = {
    "user": ROLE_CHAT,
    "admin": ROLE_ADMIN,
}


class PermissionMigrationError(RuntimeError):
    """迁移版本缺失或回填失败；阻止业务启动。"""


def is_applied() -> bool:
    """迁移版本是否已记录。"""
    try:
        return PlatformSchemaMigration.select().where(
            PlatformSchemaMigration.version == PLATFORM_MIGRATION_VERSION
        ).exists()
    except Exception:
        return False


def collect_legacy_backfill() -> list:
    """列出需要回填的账号：(user_id, legacy_role)。"""
    legacy_user_ids = {row.user_id for row in UserRole.select(UserRole.user_id)}
    pending = []
    for user in User.select():
        if user.id in legacy_user_ids:
            continue
        legacy_role = (user.role or "").strip().lower()
        if legacy_role not in LEGACY_ROLE_MAPPING:
            raise PermissionMigrationError(
                f"账号 {user.username}(id={user.id}) 的旧角色 {legacy_role!r} 无法识别，"
                "请先人工确认后再迁移；系统不会猜测授权。"
            )
        pending.append((user.id, LEGACY_ROLE_MAPPING[legacy_role]))
    return pending


def apply_backfill() -> dict:
    """执行回填并记录迁移版本（同一事务）。"""
    with db.atomic("IMMEDIATE"):
        if is_applied():
            return {"version": PLATFORM_MIGRATION_VERSION, "backfilled": 0}
        pending = collect_legacy_backfill()
        for user_id, role in pending:
            UserRole.create(user_id=user_id, role=role)
            # 同步兼容字段：管理员投影为 admin，其余投影为 user。
            User.update(role="admin" if role == ROLE_ADMIN else "user").where(User.id == user_id).execute()
        PlatformSchemaMigration.create(
            version=PLATFORM_MIGRATION_VERSION,
            applied_at=datetime.now(),
            note="旧 role=user→chat / role=admin→admin 回填",
        )
    return {"version": PLATFORM_MIGRATION_VERSION, "backfilled": len(pending)}


def ensure_applied() -> dict:
    """启动只检查迁移版本；旧库必须显式备份迁移，不能在启动时写库。"""
    if is_applied():
        return {"version": PLATFORM_MIGRATION_VERSION, "backfilled": 0, "applied": False}
    raise PermissionMigrationError("缺少平台权限迁移版本，请先运行 platform_permissions_migrate.py")
