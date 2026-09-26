"""channel → 绑定用户反查单测。"""

from __future__ import annotations

import json
from datetime import datetime

from quant.entities import QuantImChannel
from service.quant.binding_service import bind_user
from service.quant.channel_user_resolver import resolve_channel_user


def _create_channel(name, receive_id, receive_id_type="open_id"):
    now = datetime.now()
    return QuantImChannel.create(
        name=name,
        channel_type="feishu_app",
        status="active",
        config_json=json.dumps({
            "inbound_chat_id": "oc_test_chat",
            "receive_id": receive_id,
            "receive_id_type": receive_id_type,
        }, ensure_ascii=False),
        mention_list_json="[]",
        description="test",
        created_at=now,
        updated_at=now,
    )


class TestResolveChannelUser:
    def test_p2p_channel_with_bound_user_returns_username(self, seed_admin_user):
        bind_user("ou_p2p_user_001", "test_admin", "test123")
        channel = _create_channel("p2p:oc_test_chat", receive_id="ou_p2p_user_001")
        result = resolve_channel_user(channel.id)
        assert result is not None
        assert result["username"] == "test_admin"
        assert result["open_id"] == "ou_p2p_user_001"
        assert result["channel_id"] == channel.id

    def test_p2p_channel_without_binding_returns_none(self, seed_admin_user):
        channel = _create_channel("p2p:oc_no_binding", receive_id="ou_orphan")
        assert resolve_channel_user(channel.id) is None

    def test_group_channel_no_user_mapping_returns_none(self, seed_admin_user):
        # 群 channel：receive_id_type=chat_id，没有 user 关联
        channel = _create_channel(
            "group:oc_group_chat",
            receive_id="oc_group_chat_id",
            receive_id_type="chat_id",
        )
        assert resolve_channel_user(channel.id) is None

    def test_invalid_channel_id_returns_none(self):
        assert resolve_channel_user(99999) is None

    def test_missing_receive_id_returns_none(self, seed_admin_user):
        # receive_id 为空字符串
        channel = _create_channel("p2p:oc_empty", receive_id="")
        assert resolve_channel_user(channel.id) is None

    def test_corrupted_config_json_returns_none(self, seed_admin_user):
        # config_json 损坏也不应报错
        from datetime import datetime as _dt
        ch = QuantImChannel.create(
            name="p2p:oc_corrupt",
            channel_type="feishu_app",
            status="active",
            config_json="not-a-json",
            mention_list_json="[]",
            description="test",
            created_at=_dt.now(),
            updated_at=_dt.now(),
        )
        assert resolve_channel_user(ch.id) is None
