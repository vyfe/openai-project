"""操作记录状态变更 → 持仓联动同步 单测。"""

from __future__ import annotations

from datetime import date

from quant.entities import QuantOperationRecord, QuantPositionJournal
from service.quant.ops_service import create_operation_record, update_operation_record
from service.quant.position_service import create_position_entry, list_position_summary


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


class TestOperationPriceSync:
    """改价/改量时，持仓流水跟随操作记录。"""

    def test_executed_update_price_syncs_journal(self, seed_admin_user):
        op = _create_op(status="executed")
        assert QuantPositionJournal.select().count() == 1
        original = QuantPositionJournal.get()
        assert original.price == 1688.0

        update_operation_record(op["id"], price=1750.0)

        # 持仓流水价格跟随更新
        assert QuantPositionJournal.select().count() == 1  # 没新增
        refreshed = QuantPositionJournal.get()
        assert refreshed.price == 1750.0
        assert refreshed.quantity == 100  # 没动

    def test_executed_update_quantity_syncs_journal(self, seed_admin_user):
        op = _create_op(status="executed")
        update_operation_record(op["id"], quantity=150)

        refreshed = QuantPositionJournal.get()
        assert refreshed.quantity == 150
        assert refreshed.price == 1688.0

    def test_executed_update_price_and_quantity_syncs_journal(self, seed_admin_user):
        op = _create_op(status="executed")
        update_operation_record(op["id"], price=1700.0, quantity=200)

        refreshed = QuantPositionJournal.get()
        assert refreshed.price == 1700.0
        assert refreshed.quantity == 200

    def test_two_ops_only_sync_own_journal(self, seed_admin_user):
        """两个操作各自独立，按 operation_id 隔离同步。"""
        op_a = _create_op(symbol="600519.SH", status="executed")
        op_b = _create_op(symbol="000001.SZ", status="executed")
        assert QuantPositionJournal.select().count() == 2

        update_operation_record(op_a["id"], price=1800.0)

        # op_a 的流水价格变了，op_b 不动
        entries = {
            e.operation_id: e for e in QuantPositionJournal.select()
        }
        assert entries[op_a["id"]].price == 1800.0
        assert entries[op_b["id"]].price == 1688.0

    def test_draft_update_price_does_not_create_journal(self, seed_admin_user):
        """draft 状态改价不应创建流水。"""
        op = _create_op(status="draft")
        update_operation_record(op["id"], price=1700.0)
        assert QuantPositionJournal.select().count() == 0

    def test_quantity_zero_to_positive_backfills_journal(self, seed_admin_user):
        """已 executed 但之前 quantity=0 跳过计提，改成正数后应补上。"""
        op = create_operation_record(
            symbol="600519.SH",
            trade_date=date(2026, 9, 26),
            created_by="test_admin",
            action="buy",
            status="executed",
            price=1688.0,
            quantity=0,  # _apply_position_change 会跳过
        )
        assert QuantPositionJournal.select().count() == 0

        update_operation_record(op["id"], quantity=100)

        # 补计提：现在应该有一条流水
        assert QuantPositionJournal.select().count() == 1
        entry = QuantPositionJournal.get()
        assert entry.quantity == 100
        assert entry.price == 1688.0
        assert entry.operation_id == op["id"]

    def test_status_and_quantity_update_syncs_before_reversal(self, seed_admin_user):
        op = _create_op(status="executed")

        update_operation_record(op["id"], status="draft", quantity=50, price=1750.0)

        entries = list(QuantPositionJournal.select().where(
            QuantPositionJournal.operation_id == op["id"]
        ))
        assert len(entries) == 2
        assert {entry.quantity for entry in entries} == {50}
        assert {entry.price for entry in entries} == {1750.0}
        assert list_position_summary(created_by="test_admin") == []

    def test_executed_quantity_zero_removes_generated_journal(self, seed_admin_user):
        op = _create_op(status="executed")

        update_operation_record(op["id"], quantity=0)

        assert QuantPositionJournal.select().where(
            QuantPositionJournal.operation_id == op["id"]
        ).count() == 0
        assert list_position_summary(created_by="test_admin") == []

    def test_sync_does_not_modify_another_users_journal(self, seed_admin_user):
        op = _create_op(status="executed")
        other_user_entry = create_position_entry(
            symbol="000001.SZ",
            side="buy",
            quantity=25,
            price=12.0,
            occurred_at="2026-09-26 10:00:00",
            created_by="other_user",
            operation_id=op["id"],
            source="operation_record",
        )

        update_operation_record(op["id"], price=1750.0)

        entry = QuantPositionJournal.get_by_id(other_user_entry["id"])
        assert entry.price == 12.0
        assert entry.quantity == 25
