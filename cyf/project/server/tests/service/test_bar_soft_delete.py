"""删除股票池时 K 线级联软删除 + 查询过滤 — 单测覆盖。

- soft_delete_instrument / batch_soft_delete_instruments 同时把 QuantDailyBar / QuantMinuteBar
  的 status 改为 'deleted'（单次 update IN 一批）。
- query_service.fetch_*_bars 默认只返回 status='active'；include_deleted=True 可看全量。
"""
from __future__ import annotations

from datetime import date, datetime

import pytest

from quant.entities import QuantDailyBar, QuantInstrument, QuantMinuteBar
from service.quant.strategy_service import (
    batch_soft_delete_instruments,
    soft_delete_instrument,
)
from service.quant.query_service import (
    fetch_daily_bars,
    fetch_minute_bars,
    fetch_weekly_bars,
)


@pytest.fixture
def bar_table(test_settings):
    """临时 DB：1 条 instrument + 若干 daily / minute bar。"""
    QuantInstrument.create_table(safe=True)
    QuantDailyBar.create_table(safe=True)
    QuantMinuteBar.create_table(safe=True)

    QuantInstrument.create(
        symbol="600519.SH", code="600519", exchange="SH", market="A_SHARE",
        name="贵州茅台", source="manual", status="active", custom_name=None,
    )
    QuantInstrument.create(
        symbol="000001.SZ", code="000001", exchange="SZ", market="A_SHARE",
        name="平安银行", source="manual", status="active", custom_name=None,
    )

    for symbol in ("600519.SH", "000001.SZ"):
        for i in range(3):
            QuantDailyBar.create(
                symbol=symbol, code=symbol[:6], exchange=symbol[-2:],
                trade_date=date(2026, 9, 1 + i),
                adjust_flag="qfq",
                open_price=100.0 + i, high_price=110.0 + i, low_price=90.0 + i,
                close_price=105.0 + i, volume=1000 + i,
            )
            QuantMinuteBar.create(
                symbol=symbol, code=symbol[:6], exchange=symbol[-2:],
                trade_datetime=datetime(2026, 9, 1 + i, 9, 30 + i),
                trade_date=date(2026, 9, 1 + i),
                interval="5m", adjust_flag="qfq",
                open_price=100.0 + i, high_price=110.0 + i, low_price=90.0 + i,
                close_price=105.0 + i, volume=10 + i,
            )
    yield
    QuantMinuteBar.drop_table(safe=True)
    QuantDailyBar.drop_table(safe=True)
    QuantInstrument.drop_table(safe=True)


class TestSoftDeleteCascade:
    def test_soft_delete_single_cascades_to_daily_and_minute(self, bar_table):
        assert soft_delete_instrument("600519.SH") is True
        # instrument 状态
        inst = QuantInstrument.get(QuantInstrument.symbol == "600519.SH")
        assert inst.status == "deleted"
        # daily bar 全部级联
        daily = QuantDailyBar.select().where(
            QuantDailyBar.symbol == "600519.SH"
        )
        assert all(r.status == "deleted" for r in daily)
        assert daily.count() == 3
        # minute bar 全部级联
        minute = QuantMinuteBar.select().where(
            QuantMinuteBar.symbol == "600519.SH"
        )
        assert all(r.status == "deleted" for r in minute)
        assert minute.count() == 3
        # 另一个 symbol 不受影响
        other = QuantInstrument.get(QuantInstrument.symbol == "000001.SZ")
        assert other.status == "active"

    def test_soft_delete_already_deleted_returns_false(self, bar_table):
        assert soft_delete_instrument("600519.SH") is True
        # 第二次删：status 已为 deleted，update 影响 0 行
        assert soft_delete_instrument("600519.SH") is False

    def test_batch_soft_delete_cascades_with_counts(self, bar_table):
        result = batch_soft_delete_instruments(["600519.SH", "000001.SZ"])
        assert sorted(result["deleted"]) == ["000001.SZ", "600519.SH"]
        assert result["missing"] == []
        assert result["cascade"]["daily"] == 6
        assert result["cascade"]["minute"] == 6
        # 两表都变 deleted
        assert QuantDailyBar.select().where(
            QuantDailyBar.status == "deleted"
        ).count() == 6
        assert QuantMinuteBar.select().where(
            QuantMinuteBar.status == "deleted"
        ).count() == 6

    def test_batch_partial_missing(self, bar_table):
        """不在 active 集合的 symbol 应在 missing 列表里。"""
        # 先把 600519 标 deleted
        soft_delete_instrument("600519.SH")
        result = batch_soft_delete_instruments(["600519.SH", "000001.SZ", "888888.SH"])
        # 600519 已 deleted → missing；000001 active → deleted；888888 不存在 → missing
        assert sorted(result["deleted"]) == ["000001.SZ"]
        assert sorted(result["missing"]) == ["600519.SH", "888888.SH"]
        # 000001 的 bar 被级联（3 daily + 3 minute），600519 已 deleted 不会被重复改
        # （cascade 只作用于 deleted list 里的 symbol）
        assert result["cascade"]["daily"] == 3
        assert result["cascade"]["minute"] == 3


class TestQueryFiltersDeleted:
    def test_fetch_daily_bars_default_excludes_deleted(self, bar_table):
        # 先删 600519
        soft_delete_instrument("600519.SH")
        # 默认查询：应只返回 000001 的 3 根
        rows = fetch_daily_bars(symbol="600519.SH")
        assert rows == []
        rows2 = fetch_daily_bars(symbol="000001.SZ")
        assert len(rows2) == 3

    def test_fetch_daily_bars_include_deleted(self, bar_table):
        soft_delete_instrument("600519.SH")
        # include_deleted=True 看全量
        rows = fetch_daily_bars(symbol="600519.SH", include_deleted=True)
        assert len(rows) == 3
        # 每根的 status 应该是 'deleted'
        assert all(r["status"] == "deleted" for r in rows)

    def test_fetch_minute_bars_default_excludes_deleted(self, bar_table):
        soft_delete_instrument("600519.SH")
        rows = fetch_minute_bars(symbol="600519.SH", interval="5m")
        assert rows == []
        rows2 = fetch_minute_bars(symbol="000001.SZ", interval="5m")
        assert len(rows2) == 3

    def test_fetch_minute_bars_include_deleted(self, bar_table):
        soft_delete_instrument("600519.SH")
        rows = fetch_minute_bars(symbol="600519.SH", interval="5m", include_deleted=True)
        assert len(rows) == 3
        assert all(r["status"] == "deleted" for r in rows)

    def test_fetch_weekly_bars_default_excludes_deleted(self, bar_table):
        soft_delete_instrument("600519.SH")
        rows = fetch_weekly_bars(symbol="600519.SH")
        assert rows == []
        rows2 = fetch_weekly_bars(symbol="000001.SZ")
        # 周线按 ISO 周聚合，3 根日线都在同一周，合成 1 根周线
        assert len(rows2) == 1

    def test_fetch_weekly_bars_include_deleted(self, bar_table):
        soft_delete_instrument("600519.SH")
        rows = fetch_weekly_bars(symbol="600519.SH", include_deleted=True)
        # 同一 ISO 周合成 1 根
        assert len(rows) == 1