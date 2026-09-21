"""飞书操作登记 MVP 测试。"""

import json
from datetime import date

from quant.entities import QuantImInboundEvent, QuantOperationRecord
from service.quant.binding_service import bind_user
from service.quant.im_operation_service import handle_operation_command
from service.quant.ops_service import create_operation_record


def _create_event(event_id: str, sender_id: str = "feishu_open_1", chat_id: str = "oc_test"):
    return QuantImInboundEvent.create(
        event_id=event_id,
        channel_id=1,
        channel_type="feishu_app",
        message_id=f"msg_{event_id}",
        chat_id=chat_id,
        sender_id=sender_id,
        sender_type="user",
        message_type="text",
        parsed_payload_json=json.dumps({"text": ""}, ensure_ascii=False),
    )


def _parsed(event, sender_id: str = "feishu_open_1", chat_id: str = "oc_test"):
    return {
        "event_id": event.event_id,
        "message_id": event.message_id,
        "chat_id": chat_id,
        "sender_id": sender_id,
    }


class TestFeishuOperationMvp:
    def test_create_confirm_and_store_operation(self, seed_admin_user):
        bind_user("feishu_open_1", "test_admin", "test123")
        pending_event = _create_event("evt_create")
        command, response = handle_operation_command(
            "录入操作 买入 600519.SH 2026-09-18 100 1688.00 | 理由=突破年线 | 状态=已执行 | 标签=观察仓,趋势",
            _parsed(pending_event),
            pending_event.id,
        )

        assert command == "operation_pending"
        assert f"OP-{pending_event.id}" in response
        pending_event = QuantImInboundEvent.get_by_id(pending_event.id)
        assert pending_event.status == "pending_confirmation"

        confirm_event = _create_event("evt_confirm")
        command, response = handle_operation_command(
            f"确认 OP-{pending_event.id}",
            _parsed(confirm_event),
            confirm_event.id,
        )

        assert command == "operation_confirmed"
        assert "操作已登记" in response
        record = QuantOperationRecord.get()
        assert record.created_by == "test_admin"
        assert record.symbol == "600519.SH"
        assert record.action == "buy"
        assert record.quantity == 100
        assert record.to_dict()["meta"].get("source") == "feishu_im"

        pending_event = QuantImInboundEvent.get_by_id(pending_event.id)
        assert pending_event.status == "processed"
        assert json.loads(pending_event.response_payload_json)["operation_id"] == record.id

    def test_confirm_is_scoped_to_sender_and_chat(self, seed_admin_user):
        bind_user("feishu_open_1", "test_admin", "test123")
        pending_event = _create_event("evt_scope")
        handle_operation_command(
            "录入操作 观察 600519.SH 2026-09-18 | 理由=观察趋势",
            _parsed(pending_event),
            pending_event.id,
        )
        confirm_event = _create_event("evt_wrong_confirm", sender_id="feishu_other", chat_id="oc_other")
        command, response = handle_operation_command(
            f"确认 OP-{pending_event.id}",
            _parsed(confirm_event, sender_id="feishu_other", chat_id="oc_other"),
            confirm_event.id,
        )
        assert command == "operation_confirm_error"
        assert "不属于当前" in response
        assert QuantOperationRecord.select().count() == 0

    def test_history_is_limited_to_bound_user_and_supports_date_filter(self, seed_admin_user):
        bind_user("feishu_open_1", "test_admin", "test123")
        create_operation_record(
            symbol="600519.SH",
            trade_date=date.today(),
            action="buy",
            status="executed",
            created_by="test_admin",
            thesis="今天记录",
        )
        create_operation_record(
            symbol="000001.SZ",
            trade_date="2025-01-01",
            action="sell",
            status="executed",
            created_by="test_admin",
            thesis="历史记录",
        )
        create_operation_record(
            symbol="600519.SH",
            trade_date=date.today(),
            action="buy",
            status="executed",
            created_by="another_user",
            thesis="其他用户",
        )

        event = _create_event("evt_history")
        command, response = handle_operation_command("操作历史 今天", _parsed(event), event.id)

        assert command == "operation_history"
        assert "今天记录" in response
        assert "历史记录" not in response
        assert "其他用户" not in response

    def test_unbound_user_cannot_create_or_query(self):
        event = _create_event("evt_unbound", sender_id="unbound")
        command, response = handle_operation_command(
            "录入操作 买入 600519.SH 100 1688",
            _parsed(event, sender_id="unbound"),
            event.id,
        )
        assert command == "operation_create_error"
        assert "尚未绑定" in response
