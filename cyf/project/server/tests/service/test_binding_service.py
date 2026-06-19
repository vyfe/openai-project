"""binding_service 集成测试 — 验证飞书用户绑定逻辑。"""

import pytest

from service.quant.binding_service import (
    bind_user,
    unbind_user,
    get_binding,
    get_username_by_feishu,
    get_feishu_id_by_username,
    list_all_bindings,
)


class TestBindUser:
    """测试绑定飞书用户到慧聊用户。"""

    def test_bind_success(self, seed_admin_user):
        result = bind_user("feishu_open_123", "test_admin", "test123")
        assert result["feishu_open_id"] == "feishu_open_123"
        assert result["username"] == "test_admin"

    def test_bind_empty_open_id_raises(self):
        with pytest.raises(ValueError, match="不能为空"):
            bind_user("", "test_admin", "test123")

    def test_bind_empty_username_raises(self):
        with pytest.raises(ValueError, match="不能为空"):
            bind_user("feishu_open_123", "", "test123")

    def test_bind_user_not_found(self, seed_admin_user):
        with pytest.raises(ValueError, match="慧聊用户不存在"):
            bind_user("feishu_open_123", "nonexistent", "pass")

    def test_bind_wrong_password(self, seed_admin_user):
        with pytest.raises(ValueError, match="密码错误"):
            bind_user("feishu_open_123", "test_admin", "wrong_password")

    def test_bind_rebind_updates_username(self, seed_admin_user):
        """重复绑定同一 open_id 时更新 username。"""
        bind_user("feishu_open_123", "test_admin", "test123")
        result = bind_user("feishu_open_123", "test_admin", "test123")
        assert result["username"] == "test_admin"
        # 确认只有一条绑定记录
        all_bindings = list_all_bindings()
        feishu_ids = [b["feishu_open_id"] for b in all_bindings]
        assert feishu_ids.count("feishu_open_123") == 1


class TestUnbindUser:
    """测试解绑。"""

    def test_unbind_existing(self, seed_admin_user):
        bind_user("feishu_open_456", "test_admin", "test123")
        result = unbind_user("feishu_open_456")
        assert result is True
        assert get_binding("feishu_open_456") is None

    def test_unbind_nonexistent(self):
        result = unbind_user("nonexistent_id")
        assert result is False


class TestGetBinding:
    """测试查询绑定关系。"""

    def test_get_existing(self, seed_admin_user):
        bind_user("feishu_open_789", "test_admin", "test123")
        result = get_binding("feishu_open_789")
        assert result is not None
        assert result["username"] == "test_admin"

    def test_get_nonexistent(self):
        result = get_binding("nonexistent_id")
        assert result is None


class TestCrossLookup:
    """测试双向查询。"""

    def test_get_username_by_feishu(self, seed_admin_user):
        bind_user("feishu_open_abc", "test_admin", "test123")
        assert get_username_by_feishu("feishu_open_abc") == "test_admin"

    def test_get_username_by_feishu_not_found(self):
        assert get_username_by_feishu("nonexistent") is None

    def test_get_feishu_id_by_username(self, seed_admin_user):
        bind_user("feishu_open_abc", "test_admin", "test123")
        assert get_feishu_id_by_username("test_admin") == "feishu_open_abc"

    def test_get_feishu_id_by_username_not_found(self):
        assert get_feishu_id_by_username("nonexistent") is None


class TestListAllBindings:
    """测试列出所有绑定。"""

    def test_empty(self):
        result = list_all_bindings()
        assert result == []

    def test_after_bind(self, seed_admin_user):
        bind_user("feishu_open_1", "test_admin", "test123")
        result = list_all_bindings()
        assert len(result) == 1
