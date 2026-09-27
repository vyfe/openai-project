"""im_channel_service 集成测试 — 覆盖历史遗留字段 schema 不一致 bug。

历史教训：quant_im_channel 表有 webhook_url TEXT NOT NULL 列（来源不明，可能手工
ALTER 添加），但 Python QuantImChannel entity 没声明，导致 create_im_channel 100%
抛 NOT NULL constraint failed。本次测试断言：entity 修复后 create_im_channel 不传
webhook_url 也能成功，且 to_dict 把它返回。
"""
from __future__ import annotations

import pytest

from quant.entities import QuantImChannel
from service.quant.im_channel_service import create_im_channel, get_im_channel, update_im_channel


class TestCreateImChannelWebhookUrlRegression:
    """防止 entity/DB schema 不一致回归。"""

    def test_create_without_webhook_url_succeeds(self):
        """create_im_channel 不传 webhook_url 也能成功（entity 应有 default=''）。"""
        record = create_im_channel(
            name="regression-test-channel",
            config={"receive_id": "oc_test_xxx", "receive_id_type": "chat_id"},
        )
        try:
            assert record["name"] == "regression-test-channel"
            assert record["webhook_url"] == ""
            # 真实落库也能取出来
            stored = QuantImChannel.get_by_id(record["id"])
            assert stored.webhook_url == ""
        finally:
            # 清理（conftest 通常会清，但显式删避免名字冲突）
            QuantImChannel.delete().where(QuantImChannel.name == "regression-test-channel").execute()

    def test_to_dict_includes_webhook_url(self):
        """to_dict 返回 webhook_url 字段，让前端 / 上层 API 保持稳定。"""
        record = create_im_channel(
            name="to-dict-channel",
            config={"receive_id": "oc_test_yyy", "receive_id_type": "chat_id"},
        )
        try:
            assert "webhook_url" in record
            assert record["webhook_url"] == ""
            # 二次读取（get_im_channel 走 to_dict 路径）也保持一致
            refetched = get_im_channel(record["id"])
            assert "webhook_url" in refetched
            assert refetched["webhook_url"] == ""
        finally:
            QuantImChannel.delete().where(QuantImChannel.name == "to-dict-channel").execute()

    def test_update_preserves_webhook_url(self):
        """update_im_channel 不应误清 webhook_url（保持 '' 不变）。"""
        record = create_im_channel(
            name="update-channel",
            config={"receive_id": "oc_test_zzz", "receive_id_type": "chat_id"},
        )
        try:
            update_im_channel(record["id"], description="更新后描述")
            refetched = get_im_channel(record["id"])
            assert refetched["webhook_url"] == ""
            assert refetched["description"] == "更新后描述"
        finally:
            QuantImChannel.delete().where(QuantImChannel.name == "update-channel").execute()


class TestUpdateImChannelPreservesFlags:
    """回归用例：前端 save 路径会触发 normalize_feishu_config（白名单归一化）。

    历史上 update_im_channel 走 normalize 后会丢掉 ``is_p2p_virtual`` 等系统标记，
    导致 _ensure_p2p_virtual_channel 下次私聊时识别不到，重复创建。
    修复后 update 路径会在规范化后 merge 回去。
    """

    def test_update_preserves_p2p_virtual_flag_after_rename(self):
        """模拟前端 save：改名 + 传全套 config（payload 不含 is_p2p_virtual），
        必须保留 is_p2p_virtual=True。"""
        from quant.entities import QuantImChannel
        from service.quant.im_event_service import _ensure_p2p_virtual_channel

        CHAT, SENDER = "oc_preserve_flag_chat", "ou_preserve_flag_sender"
        # 1) 自动注册虚拟通道（is_p2p_virtual=True 由 _ensure_p2p_virtual_channel 写入）
        original = _ensure_p2p_virtual_channel(CHAT, SENDER)
        try:
            assert original["config"]["is_p2p_virtual"] is True

            # 2) 模拟前端 save：用户改了 name，传了完整的 config（注意：没有 is_p2p_virtual）
            frontend_payload_config = {
                "receive_id_type": "open_id",
                "receive_id": SENDER,
                "inbound_chat_id": CHAT,
                "reply_in_thread": False,
            }
            updated = update_im_channel(
                original["id"],
                name="我的私聊通道",
                status="active",
                config=frontend_payload_config,
                description="改名测试",
            )

            # 3) 关键断言：is_p2p_virtual 标志必须被保留
            assert updated["config"]["is_p2p_virtual"] is True, (
                "前端 update 后 is_p2p_virtual 被清，下一次私聊 _find_by_chat_id 会漏判"
            )
            assert updated["name"] == "我的私聊通道"

            # 4) 端到端验证：再触发一次 _ensure_p2p_virtual_channel，应命中已存在记录
            second = _ensure_p2p_virtual_channel(CHAT, SENDER)
            assert second["id"] == original["id"], "标志被丢导致重复创建"
        finally:
            QuantImChannel.delete().where(QuantImChannel.name == original["name"]).execute()
            QuantImChannel.delete().where(QuantImChannel.name == "我的私聊通道").execute()

    def test_update_preserves_underscore_flag_fields(self):
        """以 ``_`` 开头的字段也应被保留（_CONFIG_PRESERVED_FLAG_KEYS 规则）。"""
        from quant.entities import QuantImChannel

        record = create_im_channel(
            name="underscore-flag-channel",
            config={"receive_id": "oc_test_under", "receive_id_type": "chat_id"},
        )
        try:
            # 直接往 DB 写一个以下划线开头的元字段
            from quant.entities import QuantImChannel as Q
            db_row = Q.get_by_id(record["id"])
            import json as _json
            cfg = _json.loads(db_row.config_json or "{}")
            cfg["_internal_marker"] = "kept"
            cfg["is_p2p_virtual"] = True
            db_row.config_json = _json.dumps(cfg, ensure_ascii=False)
            db_row.save()

            # update 时只传前端常规字段
            updated = update_im_channel(
                record["id"],
                description="带下划线字段测试",
            )
            assert updated["config"]["is_p2p_virtual"] is True
            assert updated["config"]["_internal_marker"] == "kept"
        finally:
            QuantImChannel.delete().where(QuantImChannel.name == "underscore-flag-channel").execute()

    def test_update_without_p2p_flag_does_not_inject_it(self):
        """对于普通通道（DB 本来就没 is_p2p_virtual），update 不应主动注入假标志。"""
        from quant.entities import QuantImChannel

        record = create_im_channel(
            name="plain-channel",
            config={"receive_id": "oc_test_plain", "receive_id_type": "chat_id"},
        )
        try:
            updated = update_im_channel(
                record["id"],
                name="plain-channel-renamed",
                config={"receive_id": "oc_test_plain", "receive_id_type": "chat_id"},
            )
            # 普通通道不应被注入 is_p2p_virtual
            assert updated["config"].get("is_p2p_virtual") is None or updated["config"].get("is_p2p_virtual") is False
        finally:
            QuantImChannel.delete().where(QuantImChannel.name.startswith("plain-channel")).execute()