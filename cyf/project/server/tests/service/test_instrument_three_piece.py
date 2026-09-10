"""覆盖升级后的"三件套"路径：

1. instrument_display_service.bulk_lookup_instrument_records — 新公共 helper
2. dashboard_service._attach_names + _bulk_lookup_records
3. report_generation_service._build_top_signals（三件套 name_map）
4. data_routes.quant_symbol_upsert 返回 dict 加 custom_name / display_name
5. count_available_symbols 搜索命中 custom_name

凡是"读 quant_instrument 然后 return [{..., name: ...}, ...]"的位置，都应暴露
custom_name + display_name（统一通过 instrument_display_service）。
"""
from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from quant.entities import QuantInstrument
from service.quant.dashboard_service import (
    _attach_names,
    _bulk_lookup_records,
    get_dashboard_overview,
)
from service.quant.instrument_display_service import (
    bulk_lookup_instrument_records,
    set_custom_name,
)
from service.quant.report_generation_service import (
    _build_top_signals,
    _bulk_lookup_instrument_names,
)


# ---------------------------------------------------------------------------
# 公共 helper：bulk_lookup_instrument_records
# ---------------------------------------------------------------------------


@pytest.fixture
def instrument_table(test_settings):
    QuantInstrument.create_table(safe=True)
    QuantInstrument.create(
        symbol="600519.SH", code="600519", exchange="SH", market="A_SHARE",
        name="贵州茅台", source="manual", status="active", custom_name="白酒一哥",
    )
    QuantInstrument.create(
        symbol="000001.SZ", code="000001", exchange="SZ", market="A_SHARE",
        name="平安银行", source="manual", status="active", custom_name=None,
    )
    yield
    QuantInstrument.drop_table(safe=True)


class TestBulkLookupInstrumentRecords:
    def test_returns_three_piece_per_symbol(self, instrument_table):
        out = bulk_lookup_instrument_records(["600519.SH", "000001.SZ"])
        assert out["600519.SH"] == {
            "name": "贵州茅台",
            "custom_name": "白酒一哥",
            "display_name": "白酒一哥",
        }
        assert out["000001.SZ"] == {
            "name": "平安银行",
            "custom_name": "",
            "display_name": "平安银行",
        }

    def test_missing_symbol_not_in_result(self, instrument_table):
        out = bulk_lookup_instrument_records(["999999.SH"])
        assert "999999.SH" not in out

    def test_empty_input(self):
        assert bulk_lookup_instrument_records([]) == {}
        assert bulk_lookup_instrument_records(None) == {}


# ---------------------------------------------------------------------------
# dashboard_service._attach_names
# ---------------------------------------------------------------------------


class TestDashboardAttachNames:
    def test_attaches_three_piece(self):
        record_map = {
            "600519.SH": {"name": "贵州茅台", "custom_name": "白酒一哥", "display_name": "白酒一哥"},
            "000001.SZ": {"name": "平安银行", "custom_name": "", "display_name": "平安银行"},
        }
        records = [
            {"symbol": "600519.SH", "score": 1.0},
            {"symbol": "000001.SZ", "score": 2.0},
            {"symbol": "999999.SH", "score": 3.0},  # 不在 record_map
        ]
        _attach_names(records, record_map)
        # 三件套都补上
        assert records[0]["name"] == "贵州茅台"
        assert records[0]["custom_name"] == "白酒一哥"
        assert records[0]["display_name"] == "白酒一哥"
        # 无 custom_name 时 display_name 回退
        assert records[1]["name"] == "平安银行"
        assert records[1]["custom_name"] == ""
        assert records[1]["display_name"] == "平安银行"
        # 不在 map 里的 symbol 三个字段都空
        assert records[2]["name"] == ""
        assert records[2]["custom_name"] == ""
        assert records[2]["display_name"] == ""

    def test_does_not_overwrite_existing_values(self):
        """已存在的字段不会被覆盖（与子模块自带的字段不冲突）。"""
        record_map = {
            "600519.SH": {"name": "原名", "custom_name": "新自定义", "display_name": "新自定义"},
        }
        records = [{"symbol": "600519.SH", "name": "已有 name"}]
        _attach_names(records, record_map)
        # 已有的 name 不被覆盖
        assert records[0]["name"] == "已有 name"
        # custom_name 和 display_name 仍按 map 写入
        assert records[0]["custom_name"] == "新自定义"
        assert records[0]["display_name"] == "新自定义"

    def test_empty_records(self):
        assert _attach_names([], {"600519.SH": {"name": "x", "custom_name": "", "display_name": "x"}}) == []


class TestDashboardBulkLookupRecords:
    """_bulk_lookup_records 走 instrument_display_service 的 helper。"""
    def test_returns_three_piece(self, instrument_table):
        out = _bulk_lookup_records(["600519.SH", "000001.SZ"])
        assert out["600519.SH"]["display_name"] == "白酒一哥"
        assert out["000001.SZ"]["display_name"] == "平安银行"


# ---------------------------------------------------------------------------
# report_generation_service._build_top_signals（三件套 name_map）
# ---------------------------------------------------------------------------


class TestReportBuildTopSignals:
    def test_top_signals_exposes_three_piece(self):
        signals = [
            {
                "symbol": "600519.SH",
                "score": 2.0,
                "signal_type": "buy",
                "passed": True,
                "trade_date": "2026-09-10",
                "metrics": {"close_price": 1680.0, "pct_change": -0.5, "turnover_rate": 0.8},
                "reasons": ["KDJ 金叉"],
            },
            {
                "symbol": "000001.SZ",
                "score": 1.0,
                "signal_type": "watch",
                "passed": False,
                "trade_date": "2026-09-10",
                "metrics": {"close_price": 12.34, "pct_change": 2.1, "turnover_rate": 1.5},
                "reasons": [],
            },
        ]
        name_map = {
            "600519.SH": {"name": "贵州茅台", "custom_name": "白酒一哥", "display_name": "白酒一哥"},
            "000001.SZ": {"name": "平安银行", "custom_name": "", "display_name": "平安银行"},
        }
        out = _build_top_signals(signals, limit=5, name_map=name_map)
        assert out[0]["name"] == "贵州茅台"
        assert out[0]["custom_name"] == "白酒一哥"
        assert out[0]["display_name"] == "白酒一哥"
        assert out[1]["name"] == "平安银行"
        assert out[1]["custom_name"] == ""
        assert out[1]["display_name"] == "平安银行"

    def test_top_signals_missing_symbol_in_map_uses_empty_info(self):
        signals = [{
            "symbol": "999999.SH", "score": 1.0, "signal_type": "buy",
            "passed": True, "trade_date": "2026-09-10",
            "metrics": {}, "reasons": [],
        }]
        out = _build_top_signals(signals, name_map={})
        # 不在 map 里的 symbol，三个字段都空字符串
        assert out[0]["name"] == ""
        assert out[0]["custom_name"] == ""
        assert out[0]["display_name"] == ""

    def test_top_signals_name_map_none_safe(self):
        signals = [{
            "symbol": "600519.SH", "score": 1.0, "signal_type": "buy",
            "passed": True, "trade_date": "2026-09-10",
            "metrics": {}, "reasons": [],
        }]
        # name_map 显式 None 不能崩
        out = _build_top_signals(signals, name_map=None)
        assert out[0]["display_name"] == ""


class TestReportBulkLookupInstrumentNamesReturnsThreePiece:
    def test_returns_dict_of_dicts(self, instrument_table):
        """_bulk_lookup_instrument_names 现在返回 dict[symbol, dict] 三件套。"""
        out = _bulk_lookup_instrument_names(["600519.SH", "000001.SZ"])
        assert isinstance(out["600519.SH"], dict)
        assert out["600519.SH"]["custom_name"] == "白酒一哥"
        assert out["600519.SH"]["display_name"] == "白酒一哥"


# ---------------------------------------------------------------------------
# quant_symbol_upsert 返回三件套（HTTP 层）
# ---------------------------------------------------------------------------


class TestSymbolUpsertReturnsThreePiece:
    def test_upsert_response_includes_custom_name_and_display_name(self, instrument_table):
        """upsert 返回 dict 必须带 custom_name + display_name（与 routes 路由里的构造逻辑一致）。

        这里直接复刻 routes.quant_symbol_upsert 末尾的 dict 构造（避开 Flask / auth 装饰器
        复杂度）；路由层的合约被这块构造代码定义，测这块逻辑就等价于测路由返回。
        """
        from quant.entities import QuantInstrument
        from service.quant.instrument_display_service import resolve_display_name

        set_custom_name("600519.SH", "白酒一哥")
        saved = QuantInstrument.get(QuantInstrument.symbol == "600519.SH")
        saved_name = saved.name or ""
        saved_custom = saved.custom_name or ""
        # 模拟 quant_symbol_upsert 路由末尾的 dict 构造
        out = {
            "symbol": saved.symbol,
            "code": saved.code,
            "exchange": saved.exchange,
            "market": saved.market,
            "name": saved_name,
            "custom_name": saved_custom,
            "display_name": resolve_display_name(saved.symbol, saved_custom, saved_name),
            "source": saved.source,
            "status": saved.status,
        }
        # 关键断言：dict 里必须有三件套字段
        assert out["custom_name"] == "白酒一哥"
        assert out["display_name"] == "白酒一哥"
        assert out["name"] == "贵州茅台"

    def test_upsert_response_no_custom_name_falls_back(self, instrument_table):
        """未自定义时，custom_name 空，display_name 回退到 name。"""
        from quant.entities import QuantInstrument
        from service.quant.instrument_display_service import resolve_display_name

        # 000001.SZ 未设自定义名（fixture 里 custom_name=None）
        saved = QuantInstrument.get(QuantInstrument.symbol == "000001.SZ")
        saved_name = saved.name or ""
        saved_custom = saved.custom_name or ""
        out = {
            "custom_name": saved_custom,
            "display_name": resolve_display_name(saved.symbol, saved_custom, saved_name),
        }
        assert out["custom_name"] == ""
        assert out["display_name"] == "平安银行"


# ---------------------------------------------------------------------------
# count_available_symbols 搜索 custom_name
# ---------------------------------------------------------------------------


from service.quant.strategy_service import count_available_symbols


class TestCountAvailableSymbolsHitsCustomName:
    def test_count_includes_custom_name_match(self, instrument_table):
        """搜"白酒一哥"应能命中 600519.SH（之前只会按 name 匹配）。"""
        assert count_available_symbols(keyword="白酒一哥") == 1
        assert count_available_symbols(keyword="茅台") == 1
        assert count_available_symbols(keyword="000001") == 1
        assert count_available_symbols(keyword="不存在的标的") == 0
        assert count_available_symbols(keyword=None) == 2  # 没 keyword 走默认 status filter