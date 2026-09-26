"""飞书操作登记 MVP 测试（位置化解析 + 直接入库版）。"""

from __future__ import annotations

import json

from quant.entities import QuantImInboundEvent, QuantOperationRecord
from service.quant.binding_service import bind_user
from service.quant.im_operation_service import handle_operation_command


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


class TestFeishuOperationDirectCreate:
    """位置化命令直接入库，无二次确认。"""

    def test_basic_buy_with_compact_date(self, seed_admin_user, seed_test_instruments):
        bind_user("feishu_open_1", "test_admin", "test123")
        event = _create_event("evt_basic")
        command, response = handle_operation_command(
            "买,600519.SH,20260926,100,1688,突破年线",
            _parsed(event), event.id,
        )
        assert command == "operation_created"
        assert "已登记操作" in response
        assert "600519.SH" in response
        assert "记录 ID" in response

        # 记录已直接落库
        op = QuantOperationRecord.select().order_by(QuantOperationRecord.id.desc()).first()
        assert op.symbol == "600519.SH"
        assert op.action == "buy"
        assert op.quantity == 100
        assert op.price == 1688.0
        assert str(op.trade_date) == "2026-09-26"

    def test_sell_with_status_and_tags(self, seed_admin_user, seed_test_instruments):
        bind_user("feishu_open_sell", "test_admin", "test123")
        event = _create_event("evt_sell")
        command, response = handle_operation_command(
            "卖,002837,200,12,20260920,止损,已执行,趋势仓/观察仓",
            _parsed(event, sender_id="feishu_open_sell"), event.id,
        )
        assert command == "operation_created"
        op = QuantOperationRecord.get(
            (QuantOperationRecord.symbol == "002837.SZ") & (QuantOperationRecord.action == "sell")
        )
        assert op.status == "executed"
        import json as _json
        tag_list = _json.loads(op.tags_json)
        assert "趋势仓" in tag_list
        assert "观察仓" in tag_list
        assert op.thesis == "止损"

    def test_short_format_without_date_uses_today(self, seed_admin_user, seed_test_instruments):
        """不带日期 → 默认今天，且仍直接入库。"""
        bind_user("feishu_open_short", "test_admin", "test123")
        event = _create_event("evt_short")
        command, response = handle_operation_command(
            "买,600519,100,1688,突破年线",
            _parsed(event, sender_id="feishu_open_short"), event.id,
        )
        assert command == "operation_created"
        op = QuantOperationRecord.select().order_by(QuantOperationRecord.id.desc()).first()
        from datetime import date
        assert str(op.trade_date) == date.today().isoformat()


class TestDeprecatedCommands:
    """已废弃的二次确认命令——明确提示用户。"""

    def test_confirm_op_returns_deprecated_notice(self, seed_admin_user):
        bind_user("feishu_open_dep", "test_admin", "test123")
        event = _create_event("evt_dep_confirm")
        command, response = handle_operation_command(
            "确认 OP-99",
            _parsed(event, sender_id="feishu_open_dep"), event.id,
        )
        assert command == "operation_deprecated"
        assert "直接入库" in response

    def test_cancel_op_returns_deprecated_notice(self, seed_admin_user):
        bind_user("feishu_open_dep2", "test_admin", "test123")
        event = _create_event("evt_dep_cancel")
        command, response = handle_operation_command(
            "取消 OP-99",
            _parsed(event, sender_id="feishu_open_dep2"), event.id,
        )
        assert command == "operation_deprecated"
        assert "没有待确认项" in response


class TestHistoryQuery:
    """操作历史查询（保留）。"""

    def test_history_lists_only_bound_users_records(self, seed_admin_user, seed_test_instruments):
        bind_user("feishu_open_hist", "test_admin", "test123")
        # 录入 2 条
        for i, text in enumerate([
            "买,600519.SH,20260920,100,1688,第一条",
            "卖,002837.SZ,20260921,200,12,第二条",
        ]):
            ev = _create_event(f"evt_hist_{i}", sender_id="feishu_open_hist")
            handle_operation_command(text, _parsed(ev, sender_id="feishu_open_hist"), ev.id)

        # 查询
        ev = _create_event("evt_hist_q", sender_id="feishu_open_hist")
        command, response = handle_operation_command(
            "操作历史",
            _parsed(ev, sender_id="feishu_open_hist"), ev.id,
        )
        assert command == "operation_history"
        assert "600519.SH" in response
        assert "002837.SZ" in response
        assert "第一条" in response
        assert "第二条" in response

    def test_history_supports_compact_date_filter(self, seed_admin_user, seed_test_instruments):
        bind_user("feishu_open_date_f", "test_admin", "test123")
        ev = _create_event("evt_date_f", sender_id="feishu_open_date_f")
        handle_operation_command(
            "买,600519.SH,20260920,100,1688,过滤测试",
            _parsed(ev, sender_id="feishu_open_date_f"), ev.id,
        )
        ev2 = _create_event("evt_date_f2", sender_id="feishu_open_date_f")
        command, response = handle_operation_command(
            "操作历史 20260920",
            _parsed(ev2, sender_id="feishu_open_date_f"), ev2.id,
        )
        assert command == "operation_history"
        assert "600519.SH" in response

    def test_history_returns_only_own_records(self, seed_admin_user, seed_test_instruments):
        """操作历史只返回当前绑定用户录入的记录。"""
        bind_user("feishu_open_own", "test_admin", "test123")
        # 录入 2 条
        for i, text in enumerate([
            "买,600519.SH,20260920,100,1688,第一条",
            "卖,002837.SZ,20260921,200,12,第二条",
        ]):
            ev = _create_event(f"evt_own_{i}", sender_id="feishu_open_own")
            handle_operation_command(text, _parsed(ev, sender_id="feishu_open_own"), ev.id)
        # 查询
        ev_q = _create_event("evt_own_q", sender_id="feishu_open_own")
        _, response = handle_operation_command(
            "操作历史",
            _parsed(ev_q, sender_id="feishu_open_own"), ev_q.id,
        )
        assert "第一条" in response
        assert "第二条" in response
        assert response.count("#") == 2  # 恰好 2 条


class TestSeparatorStyles:
    """多种分隔符都能解析。"""

    def test_english_comma(self, seed_admin_user, seed_test_instruments):
        bind_user("feishu_open_en", "test_admin", "test123")
        event = _create_event("evt_en", sender_id="feishu_open_en")
        cmd, _ = handle_operation_command(
            "买,600519.SH,20260926,100,1688,突破年线",
            _parsed(event, sender_id="feishu_open_en"), event.id,
        )
        assert cmd == "operation_created"

    def test_chinese_comma(self, seed_admin_user, seed_test_instruments):
        bind_user("feishu_open_cn", "test_admin", "test123")
        event = _create_event("evt_cn", sender_id="feishu_open_cn")
        cmd, _ = handle_operation_command(
            "买，600519.SH，20260926，100，1688，突破年线",
            _parsed(event, sender_id="feishu_open_cn"), event.id,
        )
        assert cmd == "operation_created"

    def test_space(self, seed_admin_user, seed_test_instruments):
        bind_user("feishu_open_sp", "test_admin", "test123")
        event = _create_event("evt_sp", sender_id="feishu_open_sp")
        cmd, _ = handle_operation_command(
            "买 600519.SH 20260926 100 1688 突破年线",
            _parsed(event, sender_id="feishu_open_sp"), event.id,
        )
        assert cmd == "operation_created"


class TestInstrumentPoolEnforcement:
    """股票池校验。"""

    def test_unknown_symbol_is_rejected(self, seed_admin_user, seed_test_instruments):
        bind_user("feishu_open_pool", "test_admin", "test123")
        event = _create_event("evt_pool", sender_id="feishu_open_pool")
        command, response = handle_operation_command(
            "买,999999.SZ,20260926,100,10,测试",
            _parsed(event, sender_id="feishu_open_pool"), event.id,
        )
        assert command == "operation_create_error"
        assert "股票池" in response

    def test_name_resolves_to_symbol(self, seed_admin_user, seed_test_instruments):
        bind_user("feishu_open_name", "test_admin", "test123")
        event = _create_event("evt_name", sender_id="feishu_open_name")
        cmd, response = handle_operation_command(
            "买,贵州茅台,20260926,100,1688,name",
            _parsed(event, sender_id="feishu_open_name"), event.id,
        )
        assert cmd == "operation_created"
        assert "600519.SH" in response

    def test_bare_code_auto_suffix(self, seed_admin_user, seed_test_instruments):
        bind_user("feishu_open_code", "test_admin", "test123")
        event = _create_event("evt_code", sender_id="feishu_open_code")
        cmd, response = handle_operation_command(
            "买,600519,20260926,100,1688,bare",
            _parsed(event, sender_id="feishu_open_code"), event.id,
        )
        assert cmd == "operation_created"
        assert "600519.SH" in response


class TestUnboundUser:
    def test_unbound_user_cannot_create(self, seed_admin_user, seed_test_instruments):
        event = _create_event("evt_unbound", sender_id="unbound_user")
        command, response = handle_operation_command(
            "买,600519.SH,20260926,100,1688,test",
            _parsed(event, sender_id="unbound_user"), event.id,
        )
        assert command == "operation_create_error"
        assert "尚未绑定" in response


class TestDetailCommandRemoved:
    """操作详情命令已移除——返回 None 让上层 fallback。"""

    def test_detail_command_returns_none(self, seed_admin_user):
        bind_user("feishu_open_no_detail", "test_admin", "test123")
        event = _create_event("evt_no_detail", sender_id="feishu_open_no_detail")
        # 操作详情 应该被识别成"操作 历史"前一项（"操作"）+ "详情"被忽略？
        # 实际上 _starts_with(_HISTORY_PREFIXES) 中"操作记录"包含了"操作"，
        # 但"操作详情"没有匹配的 _HISTORY_PREFIXES，所以应该返回 None
        result = handle_operation_command(
            "操作详情 1",
            _parsed(event, sender_id="feishu_open_no_detail"), event.id,
        )
        assert result is None


class TestAlreadyPrefixAutoStatus:
    """动作前缀加「已」= 自动状态为「已执行」。"""

    def test_already_buy_sets_status_executed(self, seed_admin_user, seed_test_instruments):
        bind_user("feishu_open_already", "test_admin", "test123")
        event = _create_event("evt_already_buy", sender_id="feishu_open_already")
        command, _ = handle_operation_command(
            "已买,贵州茅台,100,1688,突破年线",
            _parsed(event, sender_id="feishu_open_already"), event.id,
        )
        assert command == "operation_created"
        from quant.entities import QuantOperationRecord
        op = QuantOperationRecord.select().order_by(QuantOperationRecord.id.desc()).first()
        assert op.action == "buy"
        assert op.status == "executed"
        assert op.symbol == "600519.SH"

    def test_already_sell_with_compact_date(self, seed_admin_user, seed_test_instruments):
        bind_user("feishu_open_already_s", "test_admin", "test123")
        event = _create_event("evt_already_s", sender_id="feishu_open_already_s")
        command, _ = handle_operation_command(
            "已卖,002837,20260920,200,12,止损",
            _parsed(event, sender_id="feishu_open_already_s"), event.id,
        )
        assert command == "operation_created"
        from quant.entities import QuantOperationRecord
        op = QuantOperationRecord.select().order_by(QuantOperationRecord.id.desc()).first()
        assert op.action == "sell"
        assert op.status == "executed"
        assert str(op.trade_date) == "2026-09-20"

    def test_already_buy_default_status_draft_without_prefix(self, seed_admin_user, seed_test_instruments):
        """对照组：「买」（无「已」前缀）默认 status=draft。"""
        bind_user("feishu_open_plain", "test_admin", "test123")
        event = _create_event("evt_plain", sender_id="feishu_open_plain")
        handle_operation_command(
            "买,600519,100,1688,test",
            _parsed(event, sender_id="feishu_open_plain"), event.id,
        )
        from quant.entities import QuantOperationRecord
        op = QuantOperationRecord.select().order_by(QuantOperationRecord.id.desc()).first()
        assert op.status == "draft"

    def test_explicit_status_overrides_already_prefix(self, seed_admin_user, seed_test_instruments):
        """显式指定状态会覆盖「已X」自动标记。"""
        bind_user("feishu_open_override", "test_admin", "test123")
        event = _create_event("evt_override", sender_id="feishu_open_override")
        handle_operation_command(
            "已买,600519,100,1688,test,已结束",
            _parsed(event, sender_id="feishu_open_override"), event.id,
        )
        from quant.entities import QuantOperationRecord
        op = QuantOperationRecord.select().order_by(QuantOperationRecord.id.desc()).first()
        assert op.status == "closed"  # 显式已结束 覆盖 已X 自动的已执行

    def test_already_add_and_reduce_aliases(self, seed_admin_user, seed_test_instruments):
        """已加仓、已减仓 都能识别为 executed。"""
        bind_user("feishu_open_aliases", "test_admin", "test123")
        for cmd in ["已加仓,600519,50,1700,加", "已减仓,002837,50,11,减"]:
            ev = _create_event(f"evt_alias_{cmd[:6]}", sender_id="feishu_open_aliases")
            result = handle_operation_command(
                cmd, _parsed(ev, sender_id="feishu_open_aliases"), ev.id,
            )
            assert result[0] == "operation_created", cmd
        from quant.entities import QuantOperationRecord
        ops = list(QuantOperationRecord.select().order_by(QuantOperationRecord.id.desc()).limit(2))
        status_map = {op.action: op.status for op in ops}
        assert status_map.get("add") == "executed"
        assert status_map.get("reduce") == "executed"
