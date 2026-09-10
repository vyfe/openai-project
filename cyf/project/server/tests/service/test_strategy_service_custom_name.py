"""strategy_service.list_available_symbols 单元测试 — 暴露 display_name。

/quant/symbols 路由走 list_available_symbols；之前只返回 name（不返回 custom_name / display_name），
导致前端策略池 + 数据中心管理 UI 显示不出来用户已设置的别名。
"""
from __future__ import annotations

import pytest

from service.quant.strategy_service import list_available_symbols


@pytest.fixture
def instrument_table(test_settings):
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
    QuantInstrument.create(
        symbol="888888.SH", code="888888", exchange="SH", market="A_SHARE",
        name="已下线", source="manual", status="deleted", custom_name="忽略",
    )
    yield
    QuantInstrument.drop_table(safe=True)


class TestListAvailableSymbolsExposesCustomName:
    def test_returns_custom_name_and_display_name(self, instrument_table):
        results = list_available_symbols(limit=10)
        sym_map = {r["symbol"]: r for r in results}
        assert "600519.SH" in sym_map
        # 关键：name 仍是原 name；custom_name 是用户自定义；前端可按需展示
        assert sym_map["600519.SH"]["name"] == "贵州茅台"
        assert sym_map["600519.SH"]["custom_name"] == "白酒一哥"
        assert sym_map["600519.SH"]["display_name"] == "白酒一哥"

    def test_no_custom_name_falls_back(self, instrument_table):
        results = list_available_symbols(limit=10)
        sym_map = {r["symbol"]: r for r in results}
        # custom_name 为空 → display_name 回退到 name
        assert sym_map["000001.SZ"]["custom_name"] == ""
        assert sym_map["000001.SZ"]["display_name"] == "平安银行"

    def test_status_deleted_excluded(self, instrument_table):
        results = list_available_symbols(limit=10)
        # 888888.SH 状态为 deleted，应被过滤
        assert all(r["symbol"] != "888888.SH" for r in results)

    def test_keyword_hits_custom_name(self, instrument_table):
        """搜"白酒一哥"应能命中 600519.SH（之前只会按 name 匹配）。"""
        results = list_available_symbols(limit=10, keyword="白酒一哥")
        assert len(results) == 1
        assert results[0]["symbol"] == "600519.SH"
        assert results[0]["display_name"] == "白酒一哥"

    def test_keyword_hits_name(self, instrument_table):
        results = list_available_symbols(limit=10, keyword="茅台")
        assert len(results) == 1
        assert results[0]["symbol"] == "600519.SH"

    def test_keyword_hits_code(self, instrument_table):
        results = list_available_symbols(limit=10, keyword="000001")
        assert len(results) == 1
        assert results[0]["symbol"] == "000001.SZ"

    def test_keyword_no_match(self, instrument_table):
        results = list_available_symbols(limit=10, keyword="不存在的标的")
        assert results == []