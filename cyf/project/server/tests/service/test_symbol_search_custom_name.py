"""symbol_search_service._local_search / _attach_custom_name 单元测试。

公共股票下拉搜索（/quant/symbols/search）应当在结果里暴露 custom_name + display_name，
供前端策略池 el-select 展示。
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from service.quant import symbol_search_service as sss


@pytest.fixture
def instrument_table(test_settings):
    """临时 quant_instrument 表 + 两条样例（含一条已自定义）。"""
    from quant.entities import QuantInstrument
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


class TestLocalSearchExposesCustomName:
    def test_keyword_hits_name(self, instrument_table):
        results = sss._local_search("茅台", limit=10)
        assert len(results) == 1
        assert results[0]["symbol"] == "600519.SH"
        assert results[0]["name"] == "贵州茅台"
        assert results[0]["custom_name"] == "白酒一哥"
        # display_name 必须非空且等于 custom_name（custom_name 优先）
        assert results[0]["display_name"] == "白酒一哥"

    def test_keyword_hits_custom_name(self, instrument_table):
        """关键：搜"白酒一哥"也能命中 600519（因为加了 custom_name 模糊匹配）。"""
        results = sss._local_search("白酒一哥", limit=10)
        assert len(results) == 1
        assert results[0]["symbol"] == "600519.SH"
        assert results[0]["display_name"] == "白酒一哥"

    def test_keyword_hits_code(self, instrument_table):
        results = sss._local_search("000001", limit=10)
        assert len(results) == 1
        assert results[0]["symbol"] == "000001.SZ"
        # custom_name 为空 → display_name 回退到 name
        assert results[0]["custom_name"] == ""
        assert results[0]["display_name"] == "平安银行"

    def test_empty_keyword_returns_empty(self, instrument_table):
        assert sss._local_search("", limit=10) == []
        assert sss._local_search("   ", limit=10) == []

    def test_no_match_returns_empty(self, instrument_table):
        assert sss._local_search("不存在的标的xyz", limit=10) == []


class TestAttachCustomNameRemoteFallback:
    """远端 search_symbols 失败时走 _local_search（已经测过）；成功路径由 _attach_custom_name
    把 quant_instrument 表里的 custom_name 反查补齐。"""

    def test_remote_results_get_custom_name_attached(self, instrument_table):
        # 模拟东财返回的远端结果（没有 custom_name 字段）
        remote = [
            {"symbol": "600519.SH", "code": "600519", "name": "贵州茅台", "market": "SH",
             "type": "沪A", "exchange": "SH"},
            {"symbol": "000001.SZ", "code": "000001", "name": "平安银行", "market": "SZ",
             "type": "深A", "exchange": "SZ"},
        ]
        with patch.object(sss, "search_symbols", return_value=remote):
            results = sss.search_symbols_fallback("茅台", limit=10)
        # 远端成功时不做后置过滤（按设计）：两条都被补 custom_name
        assert len(results) == 2
        sym_map = {r["symbol"]: r for r in results}
        # 600519 自定义了 → custom_name 与 display_name 都是"白酒一哥"
        assert sym_map["600519.SH"]["custom_name"] == "白酒一哥"
        assert sym_map["600519.SH"]["display_name"] == "白酒一哥"
        # 000001 未自定义 → custom_name 空，display_name 回退到 name
        assert sym_map["000001.SZ"]["custom_name"] == ""
        assert sym_map["000001.SZ"]["display_name"] == "平安银行"

    def test_remote_results_unknown_symbol_keeps_name(self, instrument_table):
        # 远端有的 symbol 但 quant_instrument 表里没有 → custom_name 空，display_name = 原 name
        remote = [
            {"symbol": "999999.SH", "code": "999999", "name": "未知标的", "market": "SH",
             "type": "沪A", "exchange": "SH"},
        ]
        with patch.object(sss, "search_symbols", return_value=remote):
            results = sss.search_symbols_fallback("999999", limit=10)
        assert results[0]["custom_name"] == ""
        assert results[0]["display_name"] == "未知标的"

    def test_falls_back_to_local_on_remote_failure(self, instrument_table):
        # 远端抛异常 → 走 _local_search（覆盖 keyword 命中 custom_name 场景）
        with patch.object(sss, "search_symbols", side_effect=RuntimeError("东财挂了")):
            results = sss.search_symbols_fallback("白酒一哥", limit=10)
        assert len(results) == 1
        assert results[0]["symbol"] == "600519.SH"
        assert results[0]["display_name"] == "白酒一哥"


class TestAttachCustomNameDirect:
    """直接测 _attach_custom_name，确保批量 IO 而不是逐条查询。"""

    def test_empty_items_pass_through(self):
        assert sss._attach_custom_name([]) == []

    def test_no_symbol_items_pass_through(self):
        items = [{"code": "x", "name": "y"}]
        assert sss._attach_custom_name(items) == items

    def test_batch_query_used(self, instrument_table):
        """调用期间 QuantInstrument.select 只调用一次（不是 N 次）。"""
        remote = [
            {"symbol": "600519.SH", "code": "600519", "name": "贵州茅台", "market": "SH",
             "type": "沪A", "exchange": "SH"},
            {"symbol": "000001.SZ", "code": "000001", "name": "平安银行", "market": "SZ",
             "type": "深A", "exchange": "SZ"},
        ]
        from quant.entities import QuantInstrument
        with patch.object(QuantInstrument, "select") as mock_select:
            # select(symbol, name, custom_name).where(symbol.in_(...))
            mock_qs = MagicMock()
            mock_qs.where.return_value = mock_qs
            mock_qs.iterator.return_value = iter([
                SimpleNamespace(symbol="600519.SH", name="贵州茅台", custom_name="白酒一哥"),
                SimpleNamespace(symbol="000001.SZ", name="平安银行", custom_name=None),
            ])
            mock_select.return_value = mock_qs
            results = sss._attach_custom_name(remote)
        # select 只调一次
        assert mock_select.call_count == 1
        # 两结果都被补上
        assert {r["symbol"] for r in results} == {"600519.SH", "000001.SZ"}
        assert results[0]["display_name"] in ("白酒一哥", "贵州茅台")