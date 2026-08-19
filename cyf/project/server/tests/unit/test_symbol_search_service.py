"""symbol_search_service 集成测试 — 覆盖东财返回数据解析、白名单过滤、MarketType 推断。"""

import json
from unittest.mock import patch

import pytest

from service.quant.symbol_search_service import (
    _infer_market,
    search_symbols,
    search_symbols_fallback,
    _to_symbol,
    ACCEPTED_SECURITY_TYPES,
)


class TestInferMarket:
    """_infer_market 优先用东财 MarketType，否则按 code 前缀兜底。"""

    def test_market_type_sh(self):
        assert _infer_market("000300", "1") == "SH"

    def test_market_type_sz(self):
        assert _infer_market("399001", "2") == "SZ"

    def test_market_type_bj(self):
        assert _infer_market("830946", "_TB") == "BJ"

    def test_market_type_empty_falls_back_to_prefix(self):
        assert _infer_market("600519", "") == "SH"
        assert _infer_market("000001", "") == "SZ"

    def test_prefix_fallback_when_market_type_unknown(self):
        # 不认识的 market_type 不应该拦截，落到 prefix 推断
        assert _infer_market("600000", "999") == "SH"

    def test_code_only_prefix(self):
        # 兼容旧用法：不传 market_type
        assert _infer_market("600519") == "SH"
        assert _infer_market("000001") == "SZ"
        assert _infer_market("430047") == "BJ"


class TestToSymbol:
    def test_format(self):
        assert _to_symbol("600519", "SH") == "600519.SH"

    def test_empty_market(self):
        assert _to_symbol("600519", "") == "600519"


class TestAcceptedSecurityTypes:
    """白名单应包含科创板与指数。"""

    def test_includes_star_market(self):
        assert "科创板" in ACCEPTED_SECURITY_TYPES

    def test_includes_index(self):
        assert "指数" in ACCEPTED_SECURITY_TYPES

    def test_includes_main_board(self):
        assert "沪A" in ACCEPTED_SECURITY_TYPES
        assert "深A" in ACCEPTED_SECURITY_TYPES
        assert "京A" in ACCEPTED_SECURITY_TYPES


def _mock_eastmoney_response(payload: dict):
    """构造一个 (status, bytes) 元组，模拟 urllib.urlopen 上下文管理器返回值。"""

    class _FakeResp:
        def __init__(self, payload_bytes):
            self._payload_bytes = payload_bytes

        def read(self):
            return self._payload_bytes

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    return _FakeResp(json.dumps(payload).encode("utf-8"))


def _patch_urlopen(payload):
    return patch(
        "urllib.request.urlopen",
        return_value=_mock_eastmoney_response(payload),
    )


class TestSearchSymbols:
    """search_symbols — 主流程：过滤白名单 + 推断 market。"""

    def test_includes_index(self):
        """沪深300 这种指数必须能搜出来，且归到 SH（不是按 code 前缀推断成 SZ）。"""
        payload = {
            "QuotationCodeTable": {
                "Data": [
                    {"Code": "000300", "Name": "沪深300", "SecurityTypeName": "指数", "MarketType": "1"},
                ]
            }
        }
        with _patch_urlopen(payload):
            results = search_symbols("000300", limit=10)
        assert len(results) == 1
        assert results[0]["code"] == "000300"
        assert results[0]["name"] == "沪深300"
        assert results[0]["market"] == "SH"
        assert results[0]["symbol"] == "000300.SH"
        assert results[0]["type"] == "指数"

    def test_includes_star_market(self):
        """科创板（688xxx）必须能搜出来，归到 SH。"""
        payload = {
            "QuotationCodeTable": {
                "Data": [
                    {"Code": "688825", "Name": "长鑫科技", "SecurityTypeName": "科创板", "MarketType": "1"},
                    {"Code": "688836", "Name": "N宇树-W", "SecurityTypeName": "科创板", "MarketType": "1"},
                ]
            }
        }
        with _patch_urlopen(payload):
            results = search_symbols("6888", limit=10)
        assert {r["code"] for r in results} == {"688825", "688836"}
        for r in results:
            assert r["market"] == "SH"
            assert r["symbol"].endswith(".SH")
            assert r["type"] == "科创板"

    def test_filters_out_fund_and_others(self):
        """基金 / 韩股 / 港股等不在白名单的应该被过滤。"""
        payload = {
            "QuotationCodeTable": {
                "Data": [
                    {"Code": "000300", "Name": "沪深300", "SecurityTypeName": "指数", "MarketType": "1"},
                    {"Code": "000300", "Name": "德邦德利货币A", "SecurityTypeName": "基金", "MarketType": "6"},
                    {"Code": "000300", "Name": "DHAutoNex", "SecurityTypeName": "韩股", "MarketType": "_KRX"},
                    {"Code": "600519", "Name": "贵州茅台", "SecurityTypeName": "沪A", "MarketType": "1"},
                ]
            }
        }
        with _patch_urlopen(payload):
            results = search_symbols("000300", limit=10)
        names = [r["name"] for r in results]
        assert "沪深300" in names
        assert "贵州茅台" in names
        assert "德邦德利货币A" not in names
        assert "DHAutoNex" not in names

    def test_main_board_a_share_still_works(self):
        payload = {
            "QuotationCodeTable": {
                "Data": [
                    {"Code": "600519", "Name": "贵州茅台", "SecurityTypeName": "沪A", "MarketType": "1"},
                    {"Code": "000001", "Name": "平安银行", "SecurityTypeName": "深A", "MarketType": "2"},
                ]
            }
        }
        with _patch_urlopen(payload):
            results = search_symbols("test", limit=10)
        assert len(results) == 2
        markets = {r["code"]: r["market"] for r in results}
        assert markets["600519"] == "SH"
        assert markets["000001"] == "SZ"

    def test_empty_keyword_returns_empty(self):
        assert search_symbols("") == []
        assert search_symbols("   ") == []


class TestSearchSymbolsFallback:
    """本地 fallback：网络异常时使用 quant_instrument 表查询。"""

    def test_fallback_to_local(self):
        from quant.entities import QuantInstrument
        from datetime import datetime

        # 插入测试数据
        QuantInstrument.insert({
            "symbol": "000001.SZ",
            "code": "000001",
            "exchange": "SZ",
            "market": "A_SHARE",
            "name": "平安银行",
            "source": "manual",
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        }).on_conflict_ignore().execute()

        with patch(
            "service.quant.symbol_search_service.search_symbols",
            side_effect=RuntimeError("网络异常"),
        ):
            results = search_symbols_fallback("平安银行", limit=10)
        assert len(results) >= 1
        assert any(r["code"] == "000001" for r in results)