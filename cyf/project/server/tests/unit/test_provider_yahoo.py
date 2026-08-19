"""Yahoo Finance provider 集成测试 — 覆盖指数 / 股票 / 转换 / 容错。"""

import json
import time
from datetime import datetime
from unittest.mock import patch

import pytest

from quant_client import provider_yahoo
from quant_client.provider_yahoo import (
    YfinanceAshareProvider,
    _to_yahoo_symbol,
)


@pytest.fixture(autouse=True)
def _shorten_yahoo_retry_sleep(monkeypatch):
    """Yahoo provider 在失败时 sleep RETRY_SLEEP_SECONDS（默认 60s）后重试 3 次。
    注意：常量在模块 import 时绑定，env var 改动无效，必须 monkeypatch 模块本身。
    """
    monkeypatch.setattr(provider_yahoo, "RETRY_SLEEP_SECONDS", 0)


def _make_yahoo_response(
    symbol: str,
    timestamps: list[int],
    opens: list,
    highs: list,
    lows: list,
    closes: list,
    volumes: list,
    adjclose: list,
) -> dict:
    """构造一个 Yahoo Finance v8 chart API 真实格式的响应。"""
    return {
        "chart": {
            "result": [{
                "meta": {
                    "currency": "CNY",
                    "symbol": symbol,
                    "exchangeName": "Shanghai",
                    "instrumentType": "INDEX",
                    "regularMarketPrice": closes[-1] if closes else None,
                },
                "timestamp": timestamps,
                "indicators": {
                    "quote": [{
                        "open": opens,
                        "high": highs,
                        "low": lows,
                        "close": closes,
                        "volume": volumes,
                    }],
                    "adjclose": [{
                        "adjclose": adjclose,
                    }],
                },
            }],
            "error": None,
        }
    }


def _unix_for(date_str: str) -> int:
    """把 YYYY-MM-DD 转 Unix 时间戳（秒）。"""
    return int(time.mktime(datetime.strptime(date_str, "%Y-%m-%d").timetuple()))


class TestYahooSymbolConversion:
    """_to_yahoo_symbol — 我们 .SH / .SZ / .BJ → Yahoo .SS / .SZ。"""

    def test_shanghai_index_to_ss(self):
        assert _to_yahoo_symbol("000300.SH") == "000300.SS"

    def test_shanghai_stock_to_ss(self):
        assert _to_yahoo_symbol("600519.SH") == "600519.SS"

    def test_shenzhen_stock_to_sz(self):
        assert _to_yahoo_symbol("000001.SZ") == "000001.SZ"

    def test_shenzhen_index_to_sz(self):
        assert _to_yahoo_symbol("399001.SZ") == "399001.SZ"

    def test_beijing_to_ss(self):
        """北交所 Yahoo 不可严格区分，统一映射为 .SS。"""
        assert _to_yahoo_symbol("830946.BJ") == "830946.SS"

    def test_lowercase_suffix_works(self):
        assert _to_yahoo_symbol("000300.sh") == "000300.SS"


class _FakeResp:
    def __init__(self, payload: dict):
        self._bytes = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._bytes

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class TestYahooFetchIndex:
    """Yahoo 拉指数（上证综指 000001.SH）的端到端解析。"""

    def test_fetch_shanghai_index(self):
        provider = YfinanceAshareProvider()
        ts1 = _unix_for("2025-01-10")
        ts2 = _unix_for("2025-01-13")
        ts3 = _unix_for("2025-01-14")
        response = _make_yahoo_response(
            symbol="000001.SS",
            timestamps=[ts1, ts2, ts3],
            opens=[3000.0, 3050.0, 3100.0],
            highs=[3050.0, 3100.0, 3150.0],
            lows=[2990.0, 3040.0, 3090.0],
            closes=[3040.0, 3080.0, 3120.0],
            volumes=[100000.0, 120000.0, 130000.0],
            adjclose=[3040.0, 3080.0, 3120.0],
        )
        with patch("urllib.request.urlopen", return_value=_FakeResp(response)):
            records = provider.fetch_daily_bars(
                symbols=["000001.SH"],
                start_date="2025-01-10",
                end_date="2025-01-15",
                adjust_flag="qfq",
            )
        assert len(records) == 3
        # 字段映射正确
        assert records[0]["symbol"] == "000001.SH"  # 还原成我们的格式
        assert records[0]["code"] == "000001"
        assert records[0]["exchange"] == "SH"
        assert records[0]["open_price"] == 3000.0
        assert records[0]["high_price"] == 3050.0
        assert records[0]["close_price"] == 3040.0
        assert records[0]["volume"] == 100000.0
        assert records[0]["source"] == "yahoo"
        # 涨跌幅从相邻收盘价反算（首日 None）
        assert records[0]["pct_change"] is None
        assert abs(records[1]["pct_change"] - (3080.0 - 3040.0) / 3040.0 * 100) < 0.001
        # 日期精度
        assert records[0]["trade_date"] == "2025-01-10"
        assert records[2]["trade_date"] == "2025-01-14"

    def test_fetch_hs300_index(self):
        """沪深300 000300.SH → Yahoo 000300.SS 验证。"""
        provider = YfinanceAshareProvider()
        ts = _unix_for("2025-01-15")
        response = _make_yahoo_response(
            symbol="000300.SS",
            timestamps=[ts],
            opens=[3850.0],
            highs=[3860.0],
            lows=[3840.0],
            closes=[3855.0],
            volumes=[200000.0],
            adjclose=[3855.0],
        )
        with patch("urllib.request.urlopen", return_value=_FakeResp(response)):
            records = provider.fetch_daily_bars(
                symbols=["000300.SH"],
                start_date="2025-01-15",
                end_date="2025-01-15",
                adjust_flag="qfq",
            )
        assert records[0]["symbol"] == "000300.SH"
        assert records[0]["close_price"] == 3855.0


class TestYahooFetchStock:
    """Yahoo 拉股票（贵州茅台 600519.SH）。"""

    def test_fetch_stock(self):
        provider = YfinanceAshareProvider()
        ts = _unix_for("2025-01-15")
        response = _make_yahoo_response(
            symbol="600519.SS",
            timestamps=[ts],
            opens=[1700.0],
            highs=[1710.0],
            lows=[1690.0],
            closes=[1705.0],
            volumes=[10000.0],
            adjclose=[1705.0],
        )
        with patch("urllib.request.urlopen", return_value=_FakeResp(response)):
            records = provider.fetch_daily_bars(
                symbols=["600519.SH"],
                start_date="2025-01-15",
                end_date="2025-01-15",
                adjust_flag="qfq",
            )
        assert records[0]["symbol"] == "600519.SH"
        assert records[0]["code"] == "600519"
        assert records[0]["exchange"] == "SH"
        assert records[0]["adjust_flag"] == "qfq"


class TestYahooPartialFailure:
    """Yahoo 单 symbol 失败不影响其他。"""

    def test_partial_failure_keeps_successful_records(self):
        provider = YfinanceAshareProvider()

        call_count = {"n": 0}

        def fake_urlopen(req, timeout=30):
            call_count["n"] += 1
            url = req.full_url if hasattr(req, "full_url") else str(req)
            if "000300" in url:
                raise RuntimeError("Yahoo 假装没 000300")
            ts = _unix_for("2025-01-15")
            if "000001.SS" in url:
                symbol = "000001.SS"
                closes = [3040.0]
            else:
                symbol = "600519.SS"
                closes = [1705.0]
            return _FakeResp(_make_yahoo_response(
                symbol=symbol,
                timestamps=[ts],
                opens=[closes[0] - 5],
                highs=[closes[0] + 5],
                lows=[closes[0] - 10],
                closes=closes,
                volumes=[10000.0],
                adjclose=closes,
            ))

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            records = provider.fetch_daily_bars(
                symbols=["600519.SH", "000300.SH", "000001.SZ"],
                start_date="2025-01-15",
                end_date="2025-01-15",
                adjust_flag="qfq",
            )
        # 000300 失败，其他成功
        assert {r["code"] for r in records} == {"600519", "000001"}
        assert "000300" not in [r["code"] for r in records]


class TestYahooErrors:
    """Yahoo 错误响应处理：per-symbol 容错下，错误被吞掉记日志，不冒泡。"""

    def test_chart_error_swallowed_per_symbol(self):
        """chart.error 响应（如 Not Found）走 per-symbol 容错，调用者拿到空 records。"""
        provider = YfinanceAshareProvider()
        response = {"chart": {"error": {"code": "Not Found", "description": "No data"}, "result": None}}
        with patch("urllib.request.urlopen", return_value=_FakeResp(response)):
            records = provider.fetch_daily_bars(
                symbols=["invalid.SH"],
                start_date="2025-01-15",
                end_date="2025-01-15",
                adjust_flag="qfq",
            )
        assert records == []

    def test_empty_result_swallowed_per_symbol(self):
        """Yahoo 返回 result:[] 同样被 per-symbol 容错吞掉。"""
        provider = YfinanceAshareProvider()
        response = {"chart": {"result": [], "error": None}}
        with patch("urllib.request.urlopen", return_value=_FakeResp(response)):
            records = provider.fetch_daily_bars(
                symbols=["empty.SH"],
                start_date="2025-01-15",
                end_date="2025-01-15",
                adjust_flag="qfq",
            )
        assert records == []


class TestYahooUnderlyingErrors:
    """_fetch_one_symbol 直接调用时，错误是会冒泡的（per-symbol 容错在 fetch_daily_bars 层）。"""

    def test_chart_error_raises_in_underlying(self):
        provider = YfinanceAshareProvider()
        response = {"chart": {"error": {"code": "Not Found", "description": "No data"}, "result": None}}
        with patch("urllib.request.urlopen", return_value=_FakeResp(response)):
            with pytest.raises(RuntimeError, match="Yahoo 返回错误"):
                provider._fetch_one_symbol(
                    "invalid.SH", period1=0, period2=1, adjust_flag="qfq",
                )


class TestYahooInAutoChain:
    """Yahoo 已在 _AUTO_CHAIN 末尾兜底。"""

    def test_yahoo_in_auto_chain(self):
        from quant_client.provider_factory import _AUTO_CHAIN

        provider_names = [_cls.provider_name for _, _cls in _AUTO_CHAIN]
        assert "yahoo" in provider_names

    def test_yahoo_at_lowest_priority(self):
        from quant_client.provider_factory import _AUTO_CHAIN

        last = max(_AUTO_CHAIN, key=lambda x: x[0])
        assert last[1].provider_name == "yahoo"

    def test_yahoo_in_provider_map(self):
        from quant_client.provider_factory import get_provider, PROVIDER_MAP

        assert "yahoo" in PROVIDER_MAP
        # 显式调用 `yahoo` 不报 DeprecationWarning
        provider = get_provider("yahoo")
        assert provider.provider_name == "yahoo"
