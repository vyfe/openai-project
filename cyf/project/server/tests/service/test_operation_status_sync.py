"""操作记录状态变更 → 持仓联动同步 单测。"""

from __future__ import annotations

from datetime import date

from quant.entities import QuantOperationRecord, QuantPositionJournal
from service.quant.ops_service import create_operation_record, update_operation_record
from service.quant.position_service import list_position_summary


def _create_op(symbol="600519.SH", action="buy", quantity=100, price=1688.0,
               status="draft", created_by="test_admin"):
    return create_operation_record(
        symbol=symbol,
        trade_date=date(2026, 9, 26),
        created_by=created_by,
        action=action,
        status=status,
        price=price,
        quantity=quantity,
        thesis="test",
    )


class TestOperationStatusSync:
    """状态变更触发持仓流水。"""

    def test_draft_to_executed_creates_position_entry(self, seed_admin_user):
        op = _create_op(status="draft")
        assert QuantPositionJournal.select().count() == 0

        update_operation_record(op["id"], status="executed")

        # 持仓流水应被写入
        entries = list(QuantPositionJournal.select())
        assert len(entries) == 1
        entry = entries[0]
        assert entry.symbol == "600519.SH"
        assert entry.side == "buy"
        assert entry.quantity == 100
        assert entry.price == 1688.0
        assert entry.source == "operation_record"
        assert entry.created_by == "test_admin"
        assert entry.operation_id == op["id"]

    def test_executed_to_draft_creates_reverse_entry(self, seed_admin_user):
        op = _create_op(status="executed")
        # 此时已经有 1 条正向流水
        assert QuantPositionJournal.select().count() == 1

        update_operation_record(op["id"], status="draft")

        # 反向流水写入，net_quantity 应抵消回 0
        summary = list_position_summary(created_by="test_admin")
        # 因为有正向 100 + 反向 sell 100 → 净持仓为 0
        assert all(p["net_quantity"] == 0 for p in summary) or len(summary) == 0

        # 流水应该有 2 条：buy 100 + sell 100
        all_entries = list(QuantPositionJournal.select())
        assert len(all_entries) == 2
        sources = sorted(e.source for e in all_entries)
        assert sources == ["operation_record", "operation_revoked"]

    def test_executed_to_cancelled_creates_reverse_entry(self, seed_admin_user):
        op = _create_op(status="executed")
        update_operation_record(op["id"], status="cancelled")

        # 反向流水
        reverse_entries = list(QuantPositionJournal.select().where(
            QuantPositionJournal.source == "operation_revoked"
        ))
        assert len(reverse_entries) == 1
        assert reverse_entries[0].side == "sell"  # buy 的反向

    def test_draft_to_cancelled_no_position_change(self, seed_admin_user):
        op = _create_op(status="draft")
        update_operation_record(op["id"], status="cancelled")
        assert QuantPositionJournal.select().count() == 0

    def test_watch_action_never_syncs(self, seed_admin_user):
        op = create_operation_record(
            symbol="600519.SH",
            trade_date=date(2026, 9, 26),
            created_by="test_admin",
            action="watch",
            status="draft",
            price=None,
            quantity=None,
        )
        update_operation_record(op["id"], status="executed")
        assert QuantPositionJournal.select().count() == 0

    def test_non_status_update_does_not_sync(self, seed_admin_user):
        op = _create_op(status="draft")
        update_operation_record(op["id"], thesis="改一下备注", price=1700.0)
        assert QuantPositionJournal.select().count() == 0

    def test_unchanged_status_does_not_sync(self, seed_admin_user):
        op = _create_op(status="draft")
        # 同一个状态再赋值不应触发
        update_operation_record(op["id"], status="draft")
        assert QuantPositionJournal.select().count() == 0

    def test_create_with_status_executed_syncs_immediately(self, seed_admin_user):
        """新建时直接 status=executed 也应该立即触发（飞书「已买」场景）。"""
        create_operation_record(
            symbol="600519.SH",
            trade_date=date(2026, 9, 26),
            created_by="test_admin",
            action="buy",
            status="executed",  # 直接是 executed
            price=1688.0,
            quantity=100,
            thesis="飞书已买",
        )
        assert QuantPositionJournal.select().count() == 1
        entry = QuantPositionJournal.select().first()
        assert entry.source == "operation_record"
