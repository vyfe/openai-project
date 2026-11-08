"""角色与授权矩阵测试（对应开发任务书 §8.3 的 A01–A07、U01–U06）。

覆盖：
- 8 个业务角色子集 + 管理员 + 停用账号 + 匿名在各模块接口上的准入；
- login / refresh / auth/me 返回一致的账号快照；
- 撤权后旧 access 不恢复权限、refresh 不恢复权限；
- 注册固定只授予聊天，携带 role/roles 直接 400；
- 用户管理接口的 roles 契约、成员筛选、兼容旧客户端、最后管理员保护、软删除。
"""
import pytest

from model.entities import User, UserRole
from service.permission_service import (
    ROLE_ADMIN,
    ROLE_CHAT,
    ROLE_QUANT,
    ROLE_SOUND,
    normalize_roles,
    RoleValidationError,
)

pytestmark = pytest.mark.api

BASE = "/never_guess_my_usage"

#: 三个业务角色的全部 8 个子集
ROLE_SUBSETS = [
    [],
    [ROLE_CHAT],
    [ROLE_QUANT],
    [ROLE_SOUND],
    [ROLE_CHAT, ROLE_QUANT],
    [ROLE_CHAT, ROLE_SOUND],
    [ROLE_QUANT, ROLE_SOUND],
    [ROLE_CHAT, ROLE_QUANT, ROLE_SOUND],
]


class RoleClient:
    """以指定账号的凭据调用接口。"""

    def __init__(self, client, username, password="test123"):
        self._client = client
        self.username = username
        self.password = password

    def _auth(self, payload):
        payload = dict(payload or {})
        payload["user"] = self.username
        payload["password"] = self.password
        return payload

    def get(self, url, **kwargs):
        params = dict(kwargs.pop("params", {}) or {})
        params.update({"user": self.username, "password": self.password})
        return self._client.get(url, query_string=params, **kwargs)

    def post(self, url, **kwargs):
        kwargs["json"] = self._auth(kwargs.pop("json", None))
        return self._client.post(url, **kwargs)


def make_user(seed_user_factory, username, roles, is_active=True):
    return seed_user_factory(username, roles, is_active=is_active)


def login(client, username, password="test123"):
    return client.post(f"{BASE}/login", json={"user": username, "password": password})


# ---------------------------------------------------------------------------
# 角色规范化
# ---------------------------------------------------------------------------

class TestRoleNormalization:
    def test_orders_business_roles(self):
        assert normalize_roles(["quant", "chat"]) == ["chat", "quant"]

    def test_admin_absorbs_other_roles(self):
        assert normalize_roles(["admin", "quant"]) == ["admin"]

    def test_deduplicates(self):
        assert normalize_roles(["chat", "chat"]) == ["chat"]

    def test_rejects_unknown_role(self):
        with pytest.raises(RoleValidationError):
            normalize_roles(["chat", "wizard"])

    def test_rejects_non_array(self):
        with pytest.raises(RoleValidationError):
            normalize_roles("chat")

    def test_rejects_empty(self):
        with pytest.raises(RoleValidationError):
            normalize_roles([])


# ---------------------------------------------------------------------------
# A01 当前授权快照
# ---------------------------------------------------------------------------

class TestAccountSnapshot:
    def test_login_returns_roles(self, app, seed_user_factory):
        make_user(seed_user_factory, "snap_user", [ROLE_CHAT, ROLE_QUANT])
        with app.test_client() as client:
            response = login(client, "snap_user")
        payload = response.get_json()
        assert payload["success"] is True
        assert payload["data"]["roles"] == ["chat", "quant"]
        assert payload["data"]["role"] == "user"
        assert payload["data"]["user_id"]

    def test_auth_me_matches_login(self, app, seed_user_factory):
        make_user(seed_user_factory, "me_user", [ROLE_SOUND])
        with app.test_client() as client:
            login_payload = login(client, "me_user").get_json()["data"]
            me = RoleClient(client, "me_user").get(f"{BASE}/auth/me").get_json()
        assert me["success"] is True
        assert me["data"]["roles"] == login_payload["roles"]
        assert me["data"]["user_id"] == login_payload["user_id"]
        assert "password" not in me["data"]
        assert "api_key" not in me["data"]

    def test_refresh_returns_current_roles(self, app, seed_user_factory):
        make_user(seed_user_factory, "refresh_user", [ROLE_CHAT])
        with app.test_client() as client:
            data = login(client, "refresh_user").get_json()["data"]
            response = client.post(f"{BASE}/token/refresh", json={"refresh_token": data["refresh_token"]})
        payload = response.get_json()
        assert payload["success"] is True
        assert payload["data"]["roles"] == ["chat"]

    def test_local_role_tampering_does_not_grant_permission(self, app, seed_user_factory):
        """本地篡改 token 里的旧角色不能恢复已撤销的权限。"""
        make_user(seed_user_factory, "tamper_user", [ROLE_CHAT])
        with app.test_client() as client:
            data = login(client, "tamper_user").get_json()["data"]
            # 客户端把 token 里的旧 role 改成 admin 也无效：授权只读数据库角色。
            tampered = client.get(
                f"{BASE}/quant/dashboard/overview",
                query_string={"user": "tamper_user", "password": "test123"},
                headers={"Authorization": f"Bearer {data['access_token']}"},
            )
            chat = RoleClient(client, "tamper_user").post(f"{BASE}/split_his", json={})
        assert tampered.status_code == 403
        assert chat.status_code == 200


# ---------------------------------------------------------------------------
# A03–A05 模块准入矩阵
# ---------------------------------------------------------------------------

class TestModuleAccessMatrix:
    @pytest.mark.parametrize("roles", ROLE_SUBSETS)
    def test_chat_endpoints_follow_chat_role(self, app, seed_user_factory, roles):
        username = f"chat_{'_'.join(roles) or 'none'}"
        make_user(seed_user_factory, username, roles)
        with app.test_client() as client:
            response = RoleClient(client, username).post(f"{BASE}/split_his", json={})
        if ROLE_CHAT in roles:
            assert response.status_code == 200
        else:
            assert response.status_code == 403
            assert response.get_json()["error_type"] == "PERMISSION_DENIED"

    @pytest.mark.parametrize("roles", ROLE_SUBSETS)
    def test_quant_endpoints_follow_quant_role(self, app, seed_user_factory, roles):
        username = f"quant_{'_'.join(roles) or 'none'}"
        make_user(seed_user_factory, username, roles)
        with app.test_client() as client:
            response = RoleClient(client, username).get(f"{BASE}/quant/positions/summary")
        if ROLE_QUANT in roles:
            assert response.status_code == 200
        else:
            assert response.status_code == 403

    @pytest.mark.parametrize("roles", ROLE_SUBSETS)
    def test_sound_endpoints_follow_sound_role(self, app, seed_user_factory, roles):
        username = f"sound_{'_'.join(roles) or 'none'}"
        make_user(seed_user_factory, username, roles)
        with app.test_client() as client:
            response = RoleClient(client, username).get(f"{BASE}/voice/state")
        if ROLE_SOUND in roles:
            assert response.status_code == 200
        else:
            assert response.status_code == 403

    def test_admin_endpoints_reject_business_users(self, app, seed_user_factory):
        make_user(seed_user_factory, "biz_user", [ROLE_CHAT, ROLE_QUANT])
        with app.test_client() as client:
            response = RoleClient(client, "biz_user").get(f"{BASE}/user/list")
        assert response.status_code == 403

    def test_admin_endpoints_accept_admin(self, app, seed_admin_user):
        with app.test_client() as client:
            response = RoleClient(client, "test_admin").get(f"{BASE}/user/list")
        assert response.status_code == 200

    def test_anonymous_is_unauthenticated(self, app):
        with app.test_client() as client:
            response = client.get(f"{BASE}/quant/dashboard/overview")
        assert response.status_code == 401
        assert response.get_json()["error_type"] == "UNAUTHENTICATED"

    def test_inactive_account_cannot_authenticate(self, app, seed_user_factory):
        make_user(seed_user_factory, "inactive_user", [ROLE_CHAT], is_active=False)
        with app.test_client() as client:
            response = login(client, "inactive_user")
        assert response.get_json()["success"] is False

    def test_generic_personal_endpoints_need_no_business_role(self, app, seed_user_factory):
        """个人设置类接口只要求已登录，不要求聊天角色。"""
        make_user(seed_user_factory, "quant_only", [ROLE_QUANT])
        with app.test_client() as client:
            response = RoleClient(client, "quant_only").post(f"{BASE}/browser_conf/get", json={})
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# A02 撤权 / 停用
# ---------------------------------------------------------------------------

class TestRevocation:
    def test_revoked_role_returns_403_not_401(self, app, seed_user_factory):
        make_user(seed_user_factory, "revoke_user", [ROLE_CHAT, ROLE_QUANT])
        with app.test_client() as client:
            login(client, "revoke_user")
            user = User.get(User.username == "revoke_user")
            UserRole.delete().where(UserRole.user_id == user.id, UserRole.role == ROLE_QUANT).execute()
            response = RoleClient(client, "revoke_user").get(f"{BASE}/quant/dashboard/overview")
        assert response.status_code == 403

    def test_refresh_does_not_restore_revoked_role(self, app, seed_user_factory):
        make_user(seed_user_factory, "revoke_refresh", [ROLE_CHAT, ROLE_QUANT])
        with app.test_client() as client:
            data = login(client, "revoke_refresh").get_json()["data"]
            user = User.get(User.username == "revoke_refresh")
            UserRole.delete().where(UserRole.user_id == user.id, UserRole.role == ROLE_QUANT).execute()
            response = client.post(f"{BASE}/token/refresh", json={"refresh_token": data["refresh_token"]})
        payload = response.get_json()
        assert payload["success"] is True
        assert ROLE_QUANT not in payload["data"]["roles"]

    def test_deactivated_account_access_is_401(self, app, seed_user_factory):
        make_user(seed_user_factory, "deactivate_user", [ROLE_CHAT])
        with app.test_client() as client:
            login(client, "deactivate_user")
            user = User.get(User.username == "deactivate_user")
            user.is_active = False
            user.save()
            response = RoleClient(client, "deactivate_user").post(f"{BASE}/split_his", json={})
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# A06/A07 错误协议与凭据
# ---------------------------------------------------------------------------

class TestErrorProtocol:
    def test_explicit_invalid_bearer_returns_401(self, app, seed_user_factory):
        """显式携带无效 bearer 时返回 401，不切换到请求体里的另一账号身份。"""
        make_user(seed_user_factory, "bearer_user", [ROLE_CHAT])
        with app.test_client() as client:
            response = client.post(
                f"{BASE}/split_his",
                json={"user": "bearer_user", "password": "test123"},
                headers={"Authorization": "Bearer invalid-token"},
            )
        assert response.status_code == 401
        assert response.get_json()["error_type"] == "UNAUTHENTICATED"

    def test_missing_credential_returns_401(self, app):
        with app.test_client() as client:
            response = client.post(f"{BASE}/split_his", json={})
        assert response.status_code == 401

    def test_cross_user_private_resource_returns_404(self, app, seed_user_factory):
        """跨用户私有资源统一返回 404，避免暴露资源存在性。"""
        from service.quant import ops_service
        from quant.entities import QuantOperationRecord

        owner = make_user(seed_user_factory, "owner_a", [ROLE_QUANT])
        other = make_user(seed_user_factory, "owner_b", [ROLE_QUANT])
        record = QuantOperationRecord.create(
            owner_user_id=owner.id,
            symbol="000001.SZ",
            action="buy",
            status="draft",
            trade_date="2026-01-05",
            created_by=owner.username,
        )
        with app.test_client() as client:
            response = RoleClient(client, other.username).get(f"{BASE}/quant/operations/get/{record.id}")
        assert response.status_code == 404
        assert response.get_json()["error_type"] == "RESOURCE_NOT_FOUND"
        assert ops_service is not None


# ---------------------------------------------------------------------------
# U01–U06 用户管理
# ---------------------------------------------------------------------------

class TestUserManagement:
    def test_list_returns_roles_and_compat_role(self, app, seed_admin_user, seed_user_factory):
        make_user(seed_user_factory, "combo_user", [ROLE_CHAT, ROLE_QUANT])
        with app.test_client() as client:
            response = RoleClient(client, "test_admin").get(f"{BASE}/user/list")
        payload = response.get_json()
        assert payload["success"] is True
        items = payload["data"]["items"]
        combo = next(item for item in items if item["username"] == "combo_user")
        assert combo["roles"] == ["chat", "quant"]
        assert combo["role"] == "user"

    def test_role_filter_matches_membership(self, app, seed_admin_user, seed_user_factory):
        make_user(seed_user_factory, "single_quant", [ROLE_QUANT])
        make_user(seed_user_factory, "combo_quant", [ROLE_CHAT, ROLE_QUANT])
        with app.test_client() as client:
            response = RoleClient(client, "test_admin").get(f"{BASE}/user/list", params={"role": "quant"})
        items = response.get_json()["data"]["items"]
        usernames = {item["username"] for item in items}
        assert {"single_quant", "combo_quant"} <= usernames

    def test_create_with_roles(self, app, seed_admin_user):
        with app.test_client() as client:
            response = RoleClient(client, "test_admin").post(
                f"{BASE}/user/create",
                json={"username": "created_user", "new_password": "test123", "roles": ["quant", "sound"]},
            )
        payload = response.get_json()
        assert payload["success"] is True
        assert payload["data"]["roles"] == ["quant", "sound"]

    def test_create_rejects_unknown_role(self, app, seed_admin_user):
        with app.test_client() as client:
            response = RoleClient(client, "test_admin").post(
                f"{BASE}/user/create",
                json={"username": "bad_role_user", "new_password": "test123", "roles": ["wizard"]},
            )
        assert response.status_code == 400
        assert not User.select().where(User.username == "bad_role_user").exists()

    def test_update_replaces_roles_atomically(self, app, seed_admin_user, seed_user_factory):
        make_user(seed_user_factory, "updatable", [ROLE_CHAT, ROLE_QUANT])
        user = User.get(User.username == "updatable")
        with app.test_client() as client:
            response = RoleClient(client, "test_admin").post(
                f"{BASE}/user/update", json={"id": user.id, "roles": ["sound"]}
            )
        payload = response.get_json()
        assert payload["success"] is True
        assert payload["data"]["roles"] == ["sound"]
        stored = [row.role for row in UserRole.select().where(UserRole.user_id == user.id)]
        assert stored == ["sound"]

    def test_update_without_roles_keeps_combination(self, app, seed_admin_user, seed_user_factory):
        """旧客户端只提交兼容 role 且未变化时，保留原组合角色。"""
        make_user(seed_user_factory, "legacy_keep", [ROLE_CHAT, ROLE_QUANT])
        user = User.get(User.username == "legacy_keep")
        with app.test_client() as client:
            response = RoleClient(client, "test_admin").post(
                f"{BASE}/user/update", json={"id": user.id, "username": "legacy_keep", "role": "user"}
            )
        payload = response.get_json()
        assert payload["success"] is True
        assert payload["data"]["roles"] == ["chat", "quant"]

    def test_update_legacy_promotion_to_admin(self, app, seed_admin_user, seed_user_factory):
        make_user(seed_user_factory, "legacy_promote", [ROLE_CHAT])
        user = User.get(User.username == "legacy_promote")
        with app.test_client() as client:
            response = RoleClient(client, "test_admin").post(
                f"{BASE}/user/update", json={"id": user.id, "role": "admin"}
            )
        assert response.get_json()["data"]["roles"] == ["admin"]

    def test_update_legacy_demotion_to_user(self, app, seed_admin_user, seed_user_factory):
        make_user(seed_user_factory, "legacy_demote", [ROLE_ADMIN])
        user = User.get(User.username == "legacy_demote")
        with app.test_client() as client:
            response = RoleClient(client, "test_admin").post(
                f"{BASE}/user/update", json={"id": user.id, "role": "user"}
            )
        assert response.get_json()["data"]["roles"] == ["chat"]

    def test_update_conflicting_roles_and_role_returns_400(self, app, seed_admin_user, seed_user_factory):
        """roles 与兼容 role 的管理员投影不一致时返回 400，且不部分写入。"""
        make_user(seed_user_factory, "conflict_user", [ROLE_CHAT])
        user = User.get(User.username == "conflict_user")
        with app.test_client() as client:
            response = RoleClient(client, "test_admin").post(
                f"{BASE}/user/update", json={"id": user.id, "roles": ["quant"], "role": "admin"}
            )
        assert response.status_code == 400
        # 冲突时不部分写入
        assert [row.role for row in UserRole.select().where(UserRole.user_id == user.id)] == [ROLE_CHAT]

    def test_last_admin_cannot_be_demoted(self, app, seed_admin_user):
        admin = User.get(User.username == "test_admin")
        with app.test_client() as client:
            response = RoleClient(client, "test_admin").post(
                f"{BASE}/user/update", json={"id": admin.id, "roles": ["chat"]}
            )
        assert response.status_code == 400
        assert UserRole.select().where(UserRole.user_id == admin.id, UserRole.role == ROLE_ADMIN).exists()

    def test_last_admin_cannot_be_deactivated(self, app, seed_admin_user):
        admin = User.get(User.username == "test_admin")
        with app.test_client() as client:
            response = RoleClient(client, "test_admin").post(
                f"{BASE}/user/update", json={"id": admin.id, "is_active": False}
            )
        assert response.status_code == 400
        assert User.get_by_id(admin.id).is_active is True

    def test_last_admin_cannot_be_deleted(self, app, seed_admin_user):
        admin = User.get(User.username == "test_admin")
        with app.test_client() as client:
            response = RoleClient(client, "test_admin").post(f"{BASE}/user/delete", json={"id": admin.id})
        assert response.status_code == 400
        assert User.select().where(User.id == admin.id).exists()

    def test_two_admins_allow_demotion(self, app, seed_admin_user, seed_user_factory):
        make_user(seed_user_factory, "second_admin", [ROLE_ADMIN])
        second = User.get(User.username == "second_admin")
        with app.test_client() as client:
            response = RoleClient(client, "test_admin").post(
                f"{BASE}/user/update", json={"id": second.id, "roles": ["chat"]}
            )
        assert response.status_code == 200

    def test_delete_is_soft_and_keeps_identity(self, app, seed_admin_user, seed_user_factory):
        make_user(seed_user_factory, "soft_delete_user", [ROLE_CHAT])
        user = User.get(User.username == "soft_delete_user")
        with app.test_client() as client:
            response = RoleClient(client, "test_admin").post(f"{BASE}/user/delete", json={"id": user.id})
            assert response.status_code == 200
            # 软删除后凭据立即失效
            denied = RoleClient(client, "soft_delete_user").post(f"{BASE}/split_his", json={})
        assert denied.status_code == 401
        stored = User.get_by_id(user.id)
        assert stored.id == user.id  # 主键保留，资源归属不变
        assert stored.is_active is False
        assert stored.deleted_at is not None


# ---------------------------------------------------------------------------
# 注册
# ---------------------------------------------------------------------------

class TestRegistration:
    def test_register_grants_chat_only(self, app):
        with app.test_client() as client:
            response = client.post(
                f"{BASE}/register", json={"username": "newcomer", "password": "test123"}
            )
        payload = response.get_json()
        assert payload["success"] is True
        assert payload["data"]["roles"] == ["chat"]
        user = User.get(User.username == "newcomer")
        assert [row.role for row in UserRole.select().where(UserRole.user_id == user.id)] == ["chat"]

    def test_register_rejects_role_field(self, app):
        with app.test_client() as client:
            response = client.post(
                f"{BASE}/register",
                json={"username": "sneaky", "password": "test123", "role": "admin"},
            )
        assert response.status_code == 400
        assert not User.select().where(User.username == "sneaky").exists()

    def test_register_rejects_roles_field(self, app):
        with app.test_client() as client:
            response = client.post(
                f"{BASE}/register",
                json={"username": "sneaky2", "password": "test123", "roles": ["admin"]},
            )
        assert response.status_code == 400
        assert not User.select().where(User.username == "sneaky2").exists()
