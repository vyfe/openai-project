"""instrument_display_service 单元测试 — 覆盖纯函数 + 临时 DB 写入。

resolve_display_name / bulk_lookup_display_names 是纯逻辑（可用 mock）；
list_instruments_with_display_name / set_custom_name / clear_custom_name
走 peewee model 写库，需要 conftest 提供的 tmp_db_dir / test_settings fixture。
"""
from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from quant.entities import QuantInstrument
from service.quant.instrument_display_service import (
    bulk_lookup_display_names,
    clear_custom_name,
    list_instruments_with_display_name,
    resolve_display_name,
    set_custom_name,
)


# ---------------------------------------------------------------------------
# 纯函数
# ---------------------------------------------------------------------------


class TestResolveDisplayName:
    def test_custom_name_wins(self):
        assert resolve_display_name("000001.SZ", "我的茅台", "贵州茅台") == "我的茅台"

    def test_empty_custom_name_falls_back(self):
        assert resolve_display_name("000001.SZ", "", "贵州茅台") == "贵州茅台"
        assert resolve_display_name("000001.SZ", None, "贵州茅台") == "贵州茅台"

    def test_whitespace_custom_name_falls_back(self):
        assert resolve_display_name("000001.SZ", "   ", "贵州茅台") == "贵州茅台"

    def test_empty_name_returns_empty(self):
        assert resolve_display_name("000001.SZ", None, "") == ""


# ---------------------------------------------------------------------------
# bulk_lookup_display_names 用 mock model 走纯函数路径
# ---------------------------------------------------------------------------


class TestBulkLookupDisplayNames:
    def test_empty_input_returns_empty(self):
        assert bulk_lookup_display_names([]) == {}
        assert bulk_lookup_display_names(None) == {}

    def test_dedup_and_strip(self):
        # 用 SimpleNamespace 避免 MagicMock 属性解析陷阱
        from types import SimpleNamespace
        rows = [
            SimpleNamespace(symbol="000001.SZ", name="平安银行", custom_name=None),
            SimpleNamespace(symbol="600519.SH", name="贵州茅台", custom_name="白酒一哥"),
        ]
        # select(...).where(...) 直接返回 rows iterable
        select_mock = MagicMock(return_value=MagicMock(where=MagicMock(return_value=iter(rows))))
        with __import__("unittest.mock", fromlist=["patch"]).patch.object(
            QuantInstrument, "select", select_mock
        ):
            result = bulk_lookup_display_names(["000001.SZ", "600519.SH", "000001.SZ"])
        assert result == {
            "000001.SZ": "平安银行",
            "600519.SH": "白酒一哥",
        }


# ---------------------------------------------------------------------------
# set_custom_name / clear_custom_name 用 conftest 临时 DB
# ---------------------------------------------------------------------------


@pytest.fixture
def instrument_table(test_settings):
    """用临时 quant_db 注入一条样例 instrument；fixture 自动清理。"""
    QuantInstrument.create_table(safe=True)
    QuantInstrument.create(
        symbol="000001.SZ",
        code="000001",
        exchange="SZ",
        market="A_SHARE",
        name="平安银行",
        source="manual",
        status="active",
    )
    QuantInstrument.create(
        symbol="600519.SH",
        code="600519",
        exchange="SH",
        market="A_SHARE",
        name="贵州茅台",
        source="manual",
        status="active",
    )
    yield
    QuantInstrument.drop_table(safe=True)


class TestSetAndClearCustomName:
    def test_set_then_clear_round_trip(self, instrument_table):
        result = set_custom_name("000001.SZ", "我的平安")
        assert result["custom_name"] == "我的平安"
        assert result["display_name"] == "我的平安"
        # 落库可查
        row = QuantInstrument.get(QuantInstrument.symbol == "000001.SZ")
        assert row.custom_name == "我的平安"
        # 第二次设置覆盖
        result = set_custom_name("000001.SZ", "银行龙头")
        assert result["custom_name"] == "银行龙头"

        # 清空回退到 name
        cleared = clear_custom_name("000001.SZ")
        assert cleared["custom_name"] == ""
        assert cleared["display_name"] == "平安银行"
        row = QuantInstrument.get(QuantInstrument.symbol == "000001.SZ")
        assert row.custom_name is None

    def test_set_with_whitespace_only_clears(self, instrument_table):
        set_custom_name("600519.SH", "白酒一哥")
        # 再传 "   " 应视为清除
        result = set_custom_name("600519.SH", "   ")
        assert result["custom_name"] == ""
        row = QuantInstrument.get(QuantInstrument.symbol == "600519.SH")
        assert row.custom_name is None

    def test_set_nonexistent_raises(self, instrument_table):
        with pytest.raises(ValueError, match="不存在"):
            set_custom_name("999999.SH", "随便")

    def test_updated_at_advances(self, instrument_table):
        first = set_custom_name("000001.SZ", "第一版")
        # 至少等 1ms 让 datetime 变化可见（不强制靠真实 sleep）
        before = datetime.fromisoformat(first["updated_at"])
        result = set_custom_name("000001.SZ", "第二版")
        after = datetime.fromisoformat(result["updated_at"])
        assert after >= before


class TestListInstrumentsWithDisplayName:
    def test_lists_with_display_and_filter(self, instrument_table):
        # 先给 600519 设置 custom_name
        set_custom_name("600519.SH", "白酒一哥")

        # 默认列表（包含所有）
        items = list_instruments_with_display_name(limit=10)
        assert len(items) == 2
        sym_map = {r["symbol"]: r for r in items}
        assert sym_map["000001.SZ"]["display_name"] == "平安银行"
        assert sym_map["600519.SH"]["display_name"] == "白酒一哥"
        assert sym_map["600519.SH"]["custom_name"] == "白酒一哥"

        # only_with_custom 过滤
        only_custom = list_instruments_with_display_name(only_with_custom=True)
        assert len(only_custom) == 1
        assert only_custom[0]["symbol"] == "600519.SH"

        # keyword 命中 custom_name
        keyword_hit = list_instruments_with_display_name(keyword="白酒一哥")
        assert len(keyword_hit) == 1
        assert keyword_hit[0]["symbol"] == "600519.SH"

        # keyword 命中 name
        name_hit = list_instruments_with_display_name(keyword="平安")
        assert len(name_hit) == 1
        assert name_hit[0]["symbol"] == "000001.SZ"

        # keyword 不命中
        miss = list_instruments_with_display_name(keyword="doesnotexist")
        assert miss == []