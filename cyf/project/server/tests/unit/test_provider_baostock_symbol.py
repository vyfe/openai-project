"""baostock provider symbol 拼接回归测试 — 守住"以 0 开头的指数不该被推断成 SZ"。

修复历史：
- 早期 normalize_symbol(code) 强行按 code 前缀推断，000001.SH / 000300.SH 都被打成 SZ
- 修 provider.YfinanceAshareProvider 入口后，再修 provider_baostock.py 内部 _map_rows
- 这个测试守住 _map_rows 内的 symbol 字段必须用上游传下来的 exchange，不会再用 normalize_symbol 推断
"""

from unittest.mock import MagicMock

import pytest

from quant_client.provider_baostock import BaostockAshareProvider


def _make_baostock_response(symbol, timestamps, closes):
    """构造一个 baostock query_history_k_data_plus 真实格式的响应。"""
    rows = []
    for ts, close in zip(timestamps, closes):
        rows.append([
            "2025-01-15", symbol, "3227.1167", "3240.9400", "3160.7550", "3227.1167",
            "3160.7550", "150000000.0", "48600000000.0", "0.5", "0.8",
        ])
    columns = ["date", "code", "open", "high", "low", "close", "preclose", "volume", "amount", "pctChg", "turn"]
    return rows, columns


class TestBaostockSymbolPreservation:
    """_map_rows 输出必须用上游 exchange，不被 normalize_symbol 重新推断。"""

    def test_shanghai_index_returns_sh_not_sz(self):
        provider = BaostockAshareProvider()
        # 000001 以 0 开头，infer_exchange 推断为 SZ；我们传 SH 给 _map_rows
        # 验证结果 symbol/exchange 是 SH
        rows, columns = _make_baostock_response(
            symbol="000001",
            timestamps=[1736899200],
            closes=[3227.12],
        )
        result = provider._map_rows(
            code="000001", exchange="SH", columns=columns, records=rows, adjust_flag="qfq",
        )
        assert result[0]["symbol"] == "000001.SH"
        assert result[0]["code"] == "000001"
        assert result[0]["exchange"] == "SH"

    def test_hs300_index_returns_sh_not_sz(self):
        provider = BaostockAshareProvider()
        rows, columns = _make_baostock_response(
            symbol="000300",
            timestamps=[1736899200],
            closes=[3796.0],
        )
        result = provider._map_rows(
            code="000300", exchange="SH", columns=columns, records=rows, adjust_flag="qfq",
        )
        assert result[0]["symbol"] == "000300.SH"
        assert result[0]["exchange"] == "SH"

    def test_shanghai_stock_returns_sh(self):
        provider = BaostockAshareProvider()
        rows, columns = _make_baostock_response(
            symbol="600519",
            timestamps=[1736899200],
            closes=[1387.0],
        )
        result = provider._map_rows(
            code="600519", exchange="SH", columns=columns, records=rows, adjust_flag="qfq",
        )
        assert result[0]["symbol"] == "600519.SH"
        assert result[0]["exchange"] == "SH"

    def test_shenzhen_stock_returns_sz(self):
        provider = BaostockAshareProvider()
        rows, columns = _make_baostock_response(
            symbol="000002",
            timestamps=[1736899200],
            closes=[10.0],
        )
        result = provider._map_rows(
            code="000002", exchange="SZ", columns=columns, records=rows, adjust_flag="qfq",
        )
        assert result[0]["symbol"] == "000002.SZ"
        assert result[0]["exchange"] == "SZ"