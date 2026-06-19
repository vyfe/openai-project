"""position_service 集成测试 — 验证持仓流水 CRUD 和汇总逻辑。"""

from datetime import datetime

import pytest

from service.quant.position_service import (
    create_position_entry,
    list_position_journal,
    list_position_summary,
    update_position_entry,
    delete_position_entry,
    get_position_entry,
)


def _make_entry(symbol="000001.SZ", side="buy", quantity=100, price=12.0, occurred_at="2025-01-15 10:00:00", created_by="test_admin", **kwargs):
    return dict(
        symbol=symbol,
        side=side,
        quantity=quantity,
        price=price,
        occurred_at=occurred_at,
        created_by=created_by,
        **kwargs,
    )


class TestCreatePositionEntry:
    """测试创建持仓流水。"""

    def test_create_buy(self):
        result = create_position_entry(**_make_entry())
        assert result["id"] > 0
        assert result["symbol"] == "000001.SZ"
        assert result["side"] == "buy"
        assert result["quantity"] == 100

    def test_create_sell(self):
        result = create_position_entry(**_make_entry(side="sell"))
        assert result["side"] == "sell"

    def test_quantity_zero_raises(self):
        with pytest.raises(ValueError, match="必须大于 0"):
            create_position_entry(**_make_entry(quantity=0))

    def test_quantity_negative_raises(self):
        with pytest.raises(ValueError, match="必须大于 0"):
            create_position_entry(**_make_entry(quantity=-10))

    def test_invalid_side_raises(self):
        with pytest.raises(ValueError, match="仅支持 buy / sell"):
            create_position_entry(**_make_entry(side="hold"))

    def test_normalizes_symbol(self):
        result = create_position_entry(**_make_entry(symbol="000001"))
        assert result["symbol"] == "000001.SZ"

    def test_occurred_at_empty_raises(self):
        with pytest.raises(ValueError, match="不能为空"):
            create_position_entry(**_make_entry(occurred_at=""))


class TestListPositionJournal:
    """测试列出持仓流水。"""

    def test_empty_list(self):
        result = list_position_journal()
        assert result == []

    def test_filter_by_created_by(self):
        create_position_entry(**_make_entry(created_by="user_a"))
        create_position_entry(**_make_entry(created_by="user_b"))
        result = list_position_journal(created_by="user_a")
        assert len(result) == 1
        assert result[0]["created_by"] == "user_a"

    def test_filter_by_symbol(self):
        create_position_entry(**_make_entry(symbol="000001.SZ"))
        create_position_entry(**_make_entry(symbol="600519.SH"))
        result = list_position_journal(symbol="000001.SZ")
        assert len(result) == 1


class TestPositionSummary:
    """测试持仓汇总计算。"""

    def test_buy_summary(self, seed_daily_bars):
        create_position_entry(**_make_entry(quantity=100, price=10.0))
        summary = list_position_summary()
        assert len(summary) == 1
        assert summary[0]["net_quantity"] == 100
        assert summary[0]["avg_cost"] == 10.0

    def test_buy_and_sell_net_quantity(self, seed_daily_bars):
        create_position_entry(**_make_entry(quantity=200, price=10.0, occurred_at="2025-01-15 10:00:00"))
        create_position_entry(**_make_entry(side="sell", quantity=50, price=11.0, occurred_at="2025-01-16 10:00:00"))
        summary = list_position_summary()
        assert summary[0]["net_quantity"] == 150

    def test_sell_all_no_position(self, seed_daily_bars):
        create_position_entry(**_make_entry(quantity=100, price=10.0, occurred_at="2025-01-15 10:00:00"))
        create_position_entry(**_make_entry(side="sell", quantity=100, price=11.0, occurred_at="2025-01-16 10:00:00"))
        summary = list_position_summary()
        assert len(summary) == 0  # 净持仓<=0 不显示

    def test_position_limit_5_stocks(self):
        """同一用户最多持有 5 只不同股票。"""
        for i, code in enumerate(["000001", "000002", "000003", "000004", "000005"]):
            create_position_entry(**_make_entry(symbol=code, created_by="limit_user"))

        with pytest.raises(ValueError, match="持仓已达上限"):
            create_position_entry(**_make_entry(symbol="600519", created_by="limit_user"))


class TestUpdatePositionEntry:
    """测试更新持仓流水。"""

    def test_update_price(self):
        entry = create_position_entry(**_make_entry())
        result = update_position_entry(entry["id"], price=15.0)
        assert result["price"] == 15.0

    def test_update_quantity_invalid_raises(self):
        entry = create_position_entry(**_make_entry())
        with pytest.raises(ValueError, match="必须大于 0"):
            update_position_entry(entry["id"], quantity=0)


class TestDeletePositionEntry:
    """测试删除持仓流水。"""

    def test_delete(self):
        entry = create_position_entry(**_make_entry())
        delete_position_entry(entry["id"])
        result = list_position_journal()
        assert len(result) == 0
