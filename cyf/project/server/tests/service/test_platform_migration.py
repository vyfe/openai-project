"""平台权限迁移幂等性与回填规则测试（对应开发任务书 §8.4 的 M01–M03）。"""
import pytest

from model.entities import PlatformSchemaMigration, User, UserRole
from service.permission_service import ROLE_ADMIN, ROLE_CHAT, PLATFORM_MIGRATION_VERSION
from service.platform_migration import (
    PermissionMigrationError,
    apply_backfill,
    collect_legacy_backfill,
    ensure_applied,
    is_applied,
)

pytestmark = pytest.mark.service


def _create_legacy_user(username, role, is_active=True):
    password_hash, salt = User.hash_password("test123")
    return User.create(
        username=username,
        password_hash=password_hash,
        salt=salt,
        role=role,
        is_active=is_active,
    )


class TestPlatformMigration:
    def test_backfills_legacy_roles(self):
        _create_legacy_user("legacy_user", "user")
        _create_legacy_user("legacy_admin", "admin")
        _create_legacy_user("legacy_disabled", "user", is_active=False)

        pending = collect_legacy_backfill()
        assert sorted(item[1] for item in pending) == [ROLE_ADMIN, ROLE_CHAT, ROLE_CHAT]

        result = apply_backfill()
        assert result["backfilled"] == 3
        assert is_applied() is True

        legacy = User.get(User.username == "legacy_user")
        assert [row.role for row in UserRole.select().where(UserRole.user_id == legacy.id)] == [ROLE_CHAT]
        admin = User.get(User.username == "legacy_admin")
        assert [row.role for row in UserRole.select().where(UserRole.user_id == admin.id)] == [ROLE_ADMIN]
        # 禁用账号保留角色但仍然禁用
        disabled = User.get(User.username == "legacy_disabled")
        assert disabled.is_active is False
        assert [row.role for row in UserRole.select().where(UserRole.user_id == disabled.id)] == [ROLE_CHAT]

    def test_is_idempotent_and_does_not_restore_revoked_roles(self):
        _create_legacy_user("idem_user", "user")
        apply_backfill()

        user = User.get(User.username == "idem_user")
        UserRole.delete().where(UserRole.user_id == user.id, UserRole.role == ROLE_CHAT).execute()
        UserRole.create(user_id=user.id, role=ROLE_CHAT)
        # 撤销 quant 后重复迁移不应补回
        UserRole.delete().where(UserRole.user_id == user.id).execute()
        UserRole.create(user_id=user.id, role=ROLE_CHAT)

        result = ensure_applied()
        assert result["backfilled"] == 0
        assert [row.role for row in UserRole.select().where(UserRole.user_id == user.id)] == [ROLE_CHAT]

    def test_unknown_legacy_role_blocks_migration(self):
        _create_legacy_user("weird_user", "superuser")
        with pytest.raises(PermissionMigrationError):
            collect_legacy_backfill()

    def test_version_marker_recorded(self):
        apply_backfill()
        marker = PlatformSchemaMigration.get(PlatformSchemaMigration.version == PLATFORM_MIGRATION_VERSION)
        assert marker is not None

    def test_ensure_applied_is_noop_when_already_applied(self):
        _create_legacy_user("noop_user", "user")
        apply_backfill()
        result = ensure_applied()
        assert result["applied"] is False
        assert result["backfilled"] == 0
