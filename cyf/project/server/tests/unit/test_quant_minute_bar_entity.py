"""QuantMinuteBar entity 元数据/字段测试。

覆盖点：
1. Meta.table_name = "quant_minute_bar"
2. 唯一键含 DateTimeField（trade_datetime）而非 DateField（trade_date）
3. interval 与 adjust_flag 在索引里
4. to_dict() 包含 trade_datetime / trade_date / interval
5. 已通过 QUANT_MODELS 注册，可被 create_tables 建表
"""

from datetime import date, datetime

import pytest

from quant.entities import QUANT_MODELS, QuantMinuteBar
from quant.db import quant_db


class TestQuantMinuteBarMeta:
    def test_table_name(self):
        assert QuantMinuteBar._meta.table_name == "quant_minute_bar"  # type: ignore[attr-defined]

    def test_in_quant_models(self):
        assert QuantMinuteBar in QUANT_MODELS

    def test_unique_index_includes_datetime_interval_adjust_flag(self):
        indexes = QuantMinuteBar._meta.indexes  # type: ignore[attr-defined]
        assert indexes, "必须有唯一索引"
        # peewee: indexes 是 [(columns_tuple, unique_bool), ...]
        cols, unique = indexes[0]
        assert unique is True, "唯一索引必须为 True"
        col_names = list(cols)
        assert "symbol" in col_names
        assert "trade_datetime" in col_names
        assert "interval" in col_names
        assert "adjust_flag" in col_names
        # 不能复用日线的 DateField 唯一键
        assert "trade_date" not in col_names

    def test_to_dict_contains_minute_specific_fields(self):
        bar = QuantMinuteBar(
            symbol="600519.SH",
            code="600519",
            exchange="SH",
            trade_datetime=datetime(2024, 1, 2, 9, 35, 0),
            trade_date=date(2024, 1, 2),
            interval="5m",
            adjust_flag="qfq",
            open_price=1700.0, high_price=1702.0, low_price=1699.0, close_price=1701.0,
            volume=1000.0, amount=1701000.0,
            source="baostock",
            source_run_id="abc123",
            data_source_version="v1",
        )
        d = bar.to_dict()
        assert d["trade_datetime"] == "2024-01-02T09:35:00"
        assert d["trade_date"] == "2024-01-02"
        assert d["interval"] == "5m"
        assert d["adjust_flag"] == "qfq"
        assert d["open_price"] == 1700.0
        assert d["close_price"] == 1701.0
        assert d["source"] == "baostock"
        assert d["source_run_id"] == "abc123"

    def test_to_dict_handles_none_datetime(self):
        bar = QuantMinuteBar(
            symbol="x.SH", code="x", exchange="SH",
            trade_datetime=None, trade_date=None,
        )
        d = bar.to_dict()
        assert d["trade_datetime"] is None
        assert d["trade_date"] is None


class TestQuantMinuteBarAutoCreate:
    """验证 init_quant_db(QUANT_MODELS) 能建出 quant_minute_bar 表。"""

    def test_table_creation_safe(self, test_db):
        """conftest.py 的 autouse fixture 已用 QUANT_MODELS 建表，验证 quant_minute_bar 已存在。"""
        _, quant_db = test_db
        tables = set(quant_db.get_tables())
        assert "quant_minute_bar" in tables

    def test_required_columns_present(self, test_db):
        _, quant_db = test_db
        columns = {col.name for col in quant_db.get_columns("quant_minute_bar")}
        expected = {
            "id", "symbol", "code", "exchange",
            "trade_datetime", "trade_date", "interval", "adjust_flag",
            "open_price", "high_price", "low_price", "close_price",
            "volume", "amount", "source", "source_run_id",
            "data_source_version", "created_at", "updated_at",
        }
        missing = expected - columns
        assert not missing, f"分时 bar 缺少字段: {missing}"