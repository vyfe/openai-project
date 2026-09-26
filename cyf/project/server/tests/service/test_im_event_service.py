"""im_event_service 私聊准入与虚拟通道单测。"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from quant.entities import QuantImChannel, QuantImInboundEvent
from service.quant.binding_service import bind_user, get_username_by_feishu
from service.quant.im_event_service import (
    _ensure_p2p_virtual_channel,
    _p2p_bind_guide_text,
    _resolve_p2p_access,
    _on_im_message_receive,
)


P2P_SENDER = "ou_test_p2p_sender_001"
P2P_CHAT = "oc_test_p2p_chat_001"


def _parsed(text, *, sender_id=P2P_SENDER, chat_id=P2P_CHAT, chat_type="p2p", message_id="om_test_msg_001"):
    return {
        "event_id": f"evt_{message_id}",
        "message_id": message_id,
        "chat_id": chat_id,
        "chat_type": chat_type,
        "sender_id": sender_id,
        "sender_type": "user",
        "message_type": "text",
        "mentions": [],
        "text": text,
    }


def _p2p_virtual_channels():
    return list(
        QuantImChannel.select().where(
            QuantImChannel.name.startswith("p2p:")
        )
    )


def _build_sdk_data(message_id, chat_id, chat_type, text, sender_open_id):
    """构造 im_event_service 期望的 SDK 对象结构（用 MagicMock 避免嵌套 class 作用域问题）。"""
    data = MagicMock()
    data.header.event_id = f"evt_{message_id}"
    data.event.message.message_id = message_id
    data.event.message.chat_id = chat_id
    data.event.message.chat_type = chat_type
    data.event.message.message_type = "text"
    data.event.message.content = json.dumps({"text": text})
    data.event.message.mentions = []
    data.event.sender.sender_id.open_id = sender_open_id
    data.event.sender.sender_id.user_id = ""
    data.event.sender.sender_id.union_id = ""
    data.event.sender.sender_type = "user"
    return data


class TestEnsureP2pVirtualChannel:
    def test_first_call_creates_channel(self):
        channel = _ensure_p2p_virtual_channel(P2P_CHAT, P2P_SENDER)
        assert channel is not None
        assert channel["name"] == f"p2p:{P2P_CHAT}"
        assert channel["status"] == "active"
        assert channel["config"]["inbound_chat_id"] == P2P_CHAT
        assert channel["config"]["receive_id"] == P2P_SENDER
        assert channel["config"]["receive_id_type"] == "open_id"
        assert channel["config"]["is_p2p_virtual"] is True
        assert len(_p2p_virtual_channels()) == 1

    def test_second_call_is_idempotent(self):
        first = _ensure_p2p_virtual_channel(P2P_CHAT, P2P_SENDER)
        second = _ensure_p2p_virtual_channel(P2P_CHAT, P2P_SENDER)
        assert first is not None and second is not None
        assert first["id"] == second["id"]
        assert len(_p2p_virtual_channels()) == 1

    def test_empty_chat_or_sender_returns_none(self):
        assert _ensure_p2p_virtual_channel("", P2P_SENDER) is None
        assert _ensure_p2p_virtual_channel(P2P_CHAT, "") is None


class TestResolveP2pAccess:
    def test_bind_cmd_is_allowed_even_when_unbound(self):
        parsed = _parsed("/bind admin pwd123")
        channel, reason = _resolve_p2p_access(parsed)
        assert reason == "bind_cmd"
        assert channel is not None
        assert channel["name"] == f"p2p:{P2P_CHAT}"

    def test_unbind_whoami_also_count_as_bind_cmd(self):
        for text in ("/unbind", "/whoami", "/BIND admin pwd"):
            parsed = _parsed(text)
            channel, reason = _resolve_p2p_access(parsed)
            assert reason == "bind_cmd", text

    def test_unbound_user_gets_none_with_guide_reason(self):
        parsed = _parsed("帮助")
        channel, reason = _resolve_p2p_access(parsed)
        assert channel is None
        assert reason == "unbound_guide"
        assert _p2p_virtual_channels() == []

    def test_bound_user_gets_channel_and_auto_registers(self, seed_admin_user):
        bind_user(P2P_SENDER, "test_admin", "test123")
        parsed = _parsed("帮助")
        channel, reason = _resolve_p2p_access(parsed)
        assert reason == "bound_user"
        assert channel is not None
        assert any(c.name == f"p2p:{P2P_CHAT}" for c in _p2p_virtual_channels())

    def test_missing_chat_id_returns_no_chat_id(self):
        parsed = _parsed("帮助", chat_id="")
        channel, reason = _resolve_p2p_access(parsed)
        assert channel is None
        assert reason == "no_chat_id"


class TestP2pBindGuideText:
    def test_contains_bind_command_example(self):
        text = _p2p_bind_guide_text()
        assert "/bind" in text
        assert "用户名" in text
        assert "密码" in text
        assert "admin mypassword123" in text
        # 引导文案应该简短（< 300 字符），具体命令让用户主动发「帮助」查看
        assert len(text) < 300, f"bind guide too long: {len(text)} chars"

    def test_guides_to_help_command(self):
        """bind 引导文案应该引导用户绑定后查看「帮助」，不在引导里堆砌命令说明。"""
        text = _p2p_bind_guide_text()
        assert "帮助" in text


class TestOnImMessageReceivePrivateUnbound:
    """未绑定用户发任意非 /bind 命令 → 收到引导。"""

    def test_unbound_user_gets_guide_via_reply(self, seed_admin_user):
        with patch(
            "service.quant.im_event_service._reply_feishu_text",
            return_value={"message_type": "text", "request_payload": {}, "response_payload": {"code": 0}},
        ) as mock_reply:
            data = _build_sdk_data(
                message_id="om_guide_001",
                chat_id=P2P_CHAT,
                chat_type="p2p",
                text="帮助",
                sender_open_id=P2P_SENDER,
            )
            _on_im_message_receive(data)

            assert mock_reply.call_count == 1
            args, _ = mock_reply.call_args
            assert args[0] == "om_guide_001"
            assert "/bind" in args[1]
            assert "admin mypassword123" in args[1]

            record = QuantImInboundEvent.select().order_by(
                QuantImInboundEvent.id.desc()
            ).first()
            assert record.command == "p2p_unbound_guide"
            assert record.status == "processed"
            assert record.chat_id == P2P_CHAT
            assert record.sender_id == P2P_SENDER


class TestOnImMessageReceivePrivateBound:
    """已绑定用户发帮助 → 收到命令列表。"""

    def test_bound_user_help_returns_help_text(self, seed_admin_user):
        bind_user(P2P_SENDER, "test_admin", "test123")
        _ensure_p2p_virtual_channel(P2P_CHAT, P2P_SENDER)

        with patch(
            "service.quant.im_event_service._reply_feishu_text",
            return_value={"message_type": "text", "request_payload": {}, "response_payload": {"code": 0}},
        ) as mock_reply:
            data = _build_sdk_data(
                message_id="om_bound_001",
                chat_id=P2P_CHAT,
                chat_type="p2p",
                text="帮助",
                sender_open_id=P2P_SENDER,
            )
            _on_im_message_receive(data)

            assert mock_reply.call_count == 1
            args, _ = mock_reply.call_args
            # 新版帮助文案的关键字（精简版）
            assert "量化助手" in args[1]
            assert "股票" in args[1]
            assert "代码" in args[1]
            assert "直接入库" in args[1]
            assert "无需二次确认" in args[1] or "登记交易" in args[1]

            record = QuantImInboundEvent.select().order_by(
                QuantImInboundEvent.id.desc()
            ).first()
            assert record.command == "help"
            assert record.status == "processed"


class TestOnImMessageReceivePrivateBindCmd:
    """未绑定用户发 /bind → 走 bind 命令（绑定成功 + 返回绑定成功文案）。"""

    def test_bind_cmd_before_any_binding(self, seed_admin_user):
        with patch(
            "service.quant.im_event_service._reply_feishu_text",
            return_value={"message_type": "text", "request_payload": {}, "response_payload": {"code": 0}},
        ) as mock_reply:
            data = _build_sdk_data(
                message_id="om_bind_001",
                chat_id=P2P_CHAT,
                chat_type="p2p",
                text="/bind test_admin test123",
                sender_open_id=P2P_SENDER,
            )
            _on_im_message_receive(data)

            assert mock_reply.call_count == 1
            args, _ = mock_reply.call_args
            assert "已绑定慧聊用户" in args[1]

            assert get_username_by_feishu(P2P_SENDER) == "test_admin"

            assert any(
                c.name == f"p2p:{P2P_CHAT}"
                for c in QuantImChannel.select().where(QuantImChannel.name.startswith("p2p:"))
            )

            record = QuantImInboundEvent.select().order_by(
                QuantImInboundEvent.id.desc()
            ).first()
            assert record.command == "bind_success"
            assert record.status == "processed"



class TestFeishuHelpTextExtended:
    """帮助文案字段说明完整性。"""

    def test_help_lists_all_columns_meaning(self):
        from service.quant.im_event_service import _feishu_help_text
        text = _feishu_help_text()
        # 必须列出每个字段含义
        for keyword in ("动作", "股票", "数量", "价格", "备注", "日期"):
            assert keyword in text, f"help missing field keyword: {keyword}"

    def test_help_explains_instrument_modes(self):
        """帮助文案必须说明股票列支持「代码」和「股票名」两种模式。"""
        from service.quant.im_event_service import _feishu_help_text
        text = _feishu_help_text()
        assert "代码" in text
        assert "股票名" in text or "名称" in text

    def test_help_lists_operation_extensions(self):
        """帮助文案必须列出操作登记的扩展字段。"""
        from service.quant.im_event_service import _feishu_help_text
        text = _feishu_help_text()
        # 新版用「备注」「状态」「标签」（去掉了「理由=」「结果=」前缀写法）
        for keyword in ("备注", "状态", "标签"):
            assert keyword in text, f"help missing extension keyword: {keyword}"

    def test_help_explains_direct_storage(self):
        """帮助文案必须明确说明直接入库、无需二次确认。"""
        from service.quant.im_event_service import _feishu_help_text
        text = _feishu_help_text()
        # 新版明确说直接入库 + 无需二次确认
        assert "直接入库" in text
        assert "无需二次确认" in text
        # 不能有「OP-」（已废弃）
        assert "OP-" not in text or "OP" not in text  # 仅作为历史提及可以

    def test_help_contains_basic_command_keywords(self):
        """帮助文案必须包含基础命令关键词。"""
        from service.quant.im_event_service import _feishu_help_text
        text = _feishu_help_text()
        # 买/卖 是核心动作，必须出现
        assert "买" in text
        assert "卖" in text
        # 持仓 / 报告 / 帮助 基础命令
        assert "持仓" in text
        assert "报告" in text