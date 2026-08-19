"""Provider per-symbol 容错集成测试 — 验证单个 symbol 失败不影响其他 symbol 的结果。

每个 provider 都应在 fetch_daily_bars 内部捕获 per-symbol 异常、记录日志、继续处理后续 symbol。
"""

from unittest.mock import patch

import pytest

from quant_client.provider_baostock import BaostockAshareProvider
from quant_client.provider_tencent import TencentAshareProvider
from quant_client.provider_sina import SinaAshareProvider


def _fake_record(symbol: str, code: str, exchange: str, source: str = "test", trade_date: str = "2025-01-15") -> dict:
    return {
        "symbol": symbol,
        "code": code,
        "exchange": exchange,
        "trade_date": trade_date,
        "adjust_flag": "qfq",
        "open_price": 10.0,
        "high_price": 11.0,
        "low_price": 9.5,
        "close_price": 10.5,
        "preclose_price": 10.0,
        "volume": 1000.0,
        "amount": 10500.0,
        "turnover_rate": 1.5,
        "pct_change": 5.0,
        "change": 0.5,
        "amplitude_pct": 1.5,
        "source": source,
        "data_source_version": "v1",
    }


class TestTencentPartialFailure:
    """tencent provider：单个 symbol 失败不影响其他。"""

    def test_partial_failure_keeps_successful_records(self):
        provider = TencentAshareProvider()

        def fake_fetch(self, raw_symbol, start_date, end_date, adjust_flag):
            if "000300" in raw_symbol:
                raise RuntimeError(f"tencent 假装没 000300")
            return [_fake_record(raw_symbol, raw_symbol.split(".")[0], "SH" if raw_symbol.endswith(".SH") else "SZ")]

        with patch.object(TencentAshareProvider, "_fetch_one_symbol", autospec=True, side_effect=fake_fetch):
            records = provider.fetch_daily_bars(
                symbols=["600519.SH", "000300.SH", "000001.SZ"],
                start_date="2025-01-10",
                end_date="2025-01-15",
                adjust_flag="qfq",
            )
        # 失败的 000300 不影响其他成功的
        assert {r["code"] for r in records} == {"600519", "000001"}
        assert "000300" not in [r["code"] for r in records]

    def test_all_failure_returns_empty(self):
        provider = TencentAshareProvider()

        def fake_fetch(self, raw_symbol, start_date, end_date, adjust_flag):
            raise RuntimeError("全部失败")

        with patch.object(TencentAshareProvider, "_fetch_one_symbol", autospec=True, side_effect=fake_fetch):
            records = provider.fetch_daily_bars(
                symbols=["600519.SH", "000300.SH"],
                start_date="2025-01-10",
                end_date="2025-01-15",
                adjust_flag="qfq",
            )
        assert records == []


class TestSinaPartialFailure:
    """sina provider：单 symbol 失败不影响其他。"""

    def test_partial_failure_keeps_successful_records(self):
        provider = SinaAshareProvider()

        def fake_fetch(self, raw_symbol, start_date, end_date, adjust_flag):
            if "000300" in raw_symbol:
                raise RuntimeError("sina 假装没 000300")
            return [_fake_record(raw_symbol, raw_symbol.split(".")[0], "SH" if raw_symbol.endswith(".SH") else "SZ")]

        with patch.object(SinaAshareProvider, "_fetch_one_symbol", autospec=True, side_effect=fake_fetch):
            records = provider.fetch_daily_bars(
                symbols=["600519.SH", "000300.SH"],
                start_date="2025-01-10",
                end_date="2025-01-15",
                adjust_flag="qfq",
            )
        assert {r["code"] for r in records} == {"600519"}
        assert "000300" not in [r["code"] for r in records]


class TestBaostockPartialFailure:
    """baostock provider：单 symbol 失败不影响其他。"""

    def test_partial_failure_keeps_successful_records(self):
        provider = BaostockAshareProvider()

        def fake_fetch(self, bs, code, exchange, start_date, end_date, adjust_flag, adjust_code):
            if code == "000300":
                raise RuntimeError("baostock 假装没 000300")
            return [_fake_record(f"{code}.{exchange}", code, exchange)]

        with patch.object(BaostockAshareProvider, "_fetch_one_symbol", autospec=True, side_effect=fake_fetch):
            records = provider.fetch_daily_bars(
                symbols=["600519.SH", "000300.SH", "000001.SZ"],
                start_date="2025-01-10",
                end_date="2025-01-15",
                adjust_flag="qfq",
            )
        assert {r["code"] for r in records} == {"600519", "000001"}
        assert "000300" not in [r["code"] for r in records]


class TestAutoChainHierarchy:
    """Auto chain 拓扑约束 — Yahoo 在末尾兜底；eastmoney/akshare 已弃用（外网访问超时）。"""

    def test_auto_chain_includes_yahoo(self):
        from quant_client.provider_factory import _AUTO_CHAIN

        provider_names = [_cls.provider_name for _, _cls in _AUTO_CHAIN]
        assert "yahoo" in provider_names

    def test_yahoo_has_lowest_priority(self):
        from quant_client.provider_factory import _AUTO_CHAIN

        last = max(_AUTO_CHAIN, key=lambda x: x[0])
        assert last[1].provider_name == "yahoo"

    def test_eastmoney_and_akshare_in_deprecated(self):
        from quant_client.provider_factory import _DEPRECATED_PROVIDERS

        # eastmoney / akshare 因外网访问默认超时，被列入弃用；用户仍可显式调用
        assert "eastmoney" in _DEPRECATED_PROVIDERS
        assert "akshare" in _DEPRECATED_PROVIDERS

    def test_yahoo_not_deprecated(self):
        from quant_client.provider_factory import _DEPRECATED_PROVIDERS

        assert "yahoo" not in _DEPRECATED_PROVIDERS