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
    """查出所有标记为 ``is_p2p_virtual`` 的通道（不再依赖 name 前缀）。

    name 已经被用户重命名也无所谓——只要 ``config.is_p2p_virtual`` 为真
    就视为虚拟通道。这才是"逻辑上的虚拟通道集合"。
    """
    import json as _json
    result = []
    for ch in QuantImChannel.select():
        try:
            cfg = _json.loads(ch.config_json or "{}")
        except Exception:
            continue
        if cfg.get("is_p2p_virtual") is True:
            result.append(ch)
    return result


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

    def test_rename_then_re_register_does_not_create_duplicate(self):
        """回归用例：用户给虚拟通道重命名后，再次私聊不应重复注册。

        旧实现以 ``name == "p2p:{chat_id}"`` 作为查找键，重命名后这条记录
        对去重逻辑"不可见"，下一次私聊会再 create 一条，导致同一 chat_id
        下出现多条等价 IM 通道记录。修复后查找键改为
        ``config.inbound_chat_id``，重命名不影响去重。
        """
        from service.quant.im_channel_service import update_im_channel

        first = _ensure_p2p_virtual_channel(P2P_CHAT, P2P_SENDER)
        assert first is not None
        original_id = first["id"]

        # 用户在 UI 上把 name 改了
        renamed = update_im_channel(original_id, name="我的私聊通道")
        assert renamed["name"] == "我的私聊通道"
        assert renamed["id"] == original_id

        # 再次私聊：应命中已有记录，而不是 create 一条新的
        second = _ensure_p2p_virtual_channel(P2P_CHAT, P2P_SENDER)
        assert second is not None
        assert second["id"] == original_id
        assert second["name"] == "我的私聊通道"
        # DB 里只有一条虚拟通道
        assert len(_p2p_virtual_channels()) == 1

    def test_sender_id_change_is_synced_back(self):
        """回归用例：同一 chat_id 下 sender_id 变化应被回写到 receive_id。

        旧实现命中已存在记录时直接 return，receive_id 会停留在第一次注册时
        的旧值，导致 reply 发到错误的飞书账号。
        """
        new_sender = "ou_test_p2p_sender_changed"
        first = _ensure_p2p_virtual_channel(P2P_CHAT, P2P_SENDER)
        assert first["config"]["receive_id"] == P2P_SENDER

        # 同 chat_id，新 sender_id 到达
        second = _ensure_p2p_virtual_channel(P2P_CHAT, new_sender)
        assert second is not None
        assert second["id"] == first["id"]
        # 关键断言：receive_id 必须已更新为新 sender_id
        assert second["config"]["receive_id"] == new_sender
        assert second["config"]["receive_id_type"] == "open_id"
        # DB 里仍只有一条记录
        assert len(_p2p_virtual_channels()) == 1

    def test_rename_and_sender_id_change_combined(self):
        """组合回归：重命名 + sender_id 变化同时发生，仍只命中一条记录且 sender_id 已更新。"""
        from service.quant.im_channel_service import update_im_channel

        first = _ensure_p2p_virtual_channel(P2P_CHAT, P2P_SENDER)
        assert first is not None
        update_im_channel(first["id"], name="量化助手私聊")

        new_sender = "ou_test_p2p_sender_combo"
        second = _ensure_p2p_virtual_channel(P2P_CHAT, new_sender)
        assert second is not None
        assert second["id"] == first["id"]
        assert second["name"] == "量化助手私聊"
        assert second["config"]["receive_id"] == new_sender
        assert len(_p2p_virtual_channels()) == 1


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