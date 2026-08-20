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


def _fake_record(symbol: str, code: str, exchange: str, source: str = "test", trade_date: str = "2025-01-15") -> dict:
    """构造一个简单的 fetch_daily_bars 返回 record。"""
    short_exchange = "SH" if exchange == "SH" else ("SZ" if exchange == "SZ" else "BJ")
    if code == "":
        code = symbol.split(".")[0]
    if exchange == "":
        exchange = short_exchange
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


class TestYahooRateLimitFailFast:
    """429 限流：fail-fast，不加重试（避免拖累整体调度 + 加重 Yahoo 压力）。

    per-symbol 容错下，429 会被 fetch_daily_bars 吞掉——所以测试用 _fetch_one_symbol
    直接验，或验 fetch_daily_bars 不抛异常。
    """

    def test_429_does_not_retry_in_underlying(self):
        provider = YfinanceAshareProvider()

        import urllib.error
        call_count = {"n": 0}

        def fake_urlopen(req, timeout=30):
            call_count["n"] += 1
            raise urllib.error.HTTPError(
                req.full_url, 429, "Too Many Requests", {}, None,
            )

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            with pytest.raises(RuntimeError, match="不重试"):
                provider._fetch_one_symbol(
                    "000001.SH", period1=0, period2=1, adjust_flag="qfq",
                )
        # 关键：429 应该只调用 1 次，**没有 3 次重试**
        assert call_count["n"] == 1

    def test_404_does_not_retry_in_underlying(self):
        provider = YfinanceAshareProvider()

        import urllib.error
        call_count = {"n": 0}

        def fake_urlopen(req, timeout=30):
            call_count["n"] += 1
            raise urllib.error.HTTPError(
                req.full_url, 404, "Not Found", {}, None,
            )

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            with pytest.raises(RuntimeError, match="不重试"):
                provider._fetch_one_symbol(
                    "invalid.SH", period1=0, period2=1, adjust_flag="qfq",
                )
        assert call_count["n"] == 1

    def test_429_swallowed_per_symbol_in_fetch_daily_bars(self):
        """fetch_daily_bars 走 per-symbol 容错，429 抛出但被吞掉，调用者拿到空 records。"""
        provider = YfinanceAshareProvider()

        import urllib.error

        def fake_urlopen(req, timeout=30):
            raise urllib.error.HTTPError(
                req.full_url, 429, "Too Many Requests", {}, None,
            )

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            records = provider.fetch_daily_bars(
                symbols=["000001.SH"],
                start_date="2025-01-15",
                end_date="2025-01-15",
                adjust_flag="qfq",
            )
        assert records == []


class TestAutoChainSeedBasedRelay:
    """Auto chain 改成 seed-based 接力：下一级 provider 只接未覆盖的 symbol。

    防止低优先级 provider（Yahoo）被无效调用 —— 不然 Yahoo 因为限流问题，
    对每个 stock 都去 HTTP 请求，浪费配额且拖慢整体调度。
    """

    def _mock_yahoo_call_log(self):
        """收集 Yahoo 被调用时传入的 symbols 列表。"""
        log = []

        def tracking_fetch(self, symbols, start_date, end_date, adjust_flag="qfq"):
            log.append(list(symbols))
            return []

        return tracking_fetch, log

    def _mock_other_providers_empty(self):
        """tencent/sina 强制返回空（不跑真实 HTTP）。"""
        def fake_empty(self, symbols, start_date, end_date, adjust_flag="qfq"):
            return []
        return fake_empty

    def test_stocks_covered_by_baostock_skip_yahoo(self):
        """baostock 拿到 600519/000002，yahoo 不会再被调用。"""
        from quant_client.provider_baostock import BaostockAshareProvider
        from quant_client.provider_tencent import TencentAshareProvider
        from quant_client.provider_sina import SinaAshareProvider
        from quant_client.provider_yahoo import YfinanceAshareProvider
        from quant_client.provider_factory import AutoAshareProvider

        def fake_baostock(self, symbols, start_date, end_date, adjust_flag="qfq"):
            return [_fake_record(s, s.split(".")[0], s.split(".")[1], source="baostock") for s in symbols]

        tracking_fetch, yahoo_log = self._mock_yahoo_call_log()
        tencent_empty = self._mock_other_providers_empty()

        with patch.object(BaostockAshareProvider, "fetch_daily_bars", autospec=True, side_effect=fake_baostock), \
             patch.object(TencentAshareProvider, "fetch_daily_bars", autospec=True, side_effect=tencent_empty), \
             patch.object(SinaAshareProvider, "fetch_daily_bars", autospec=True, side_effect=tencent_empty), \
             patch.object(YfinanceAshareProvider, "fetch_daily_bars", autospec=True, side_effect=tracking_fetch):
            records = AutoAshareProvider().fetch_daily_bars(
                symbols=["600519.SH", "000002.SZ"],
                start_date="2025-01-15",
                end_date="2025-01-15",
                adjust_flag="qfq",
            )

        # Yahoo 根本没被调用（baostock 全覆盖）
        assert yahoo_log == []
        assert {r["code"] for r in records} == {"600519", "000002"}

    def test_yahoo_only_called_for_missing_symbols(self):
        """baostock 拿到股票，000300 失败 → yahoo 只接 000300。"""
        from quant_client.provider_baostock import BaostockAshareProvider
        from quant_client.provider_tencent import TencentAshareProvider
        from quant_client.provider_sina import SinaAshareProvider
        from quant_client.provider_yahoo import YfinanceAshareProvider
        from quant_client.provider_factory import AutoAshareProvider

        def fake_baostock(self, symbols, start_date, end_date, adjust_flag="qfq"):
            rows = []
            for s in symbols:
                if "000300" in s:
                    continue  # 模拟 000300 失败
                rows.append(_fake_record(s, s.split(".")[0], s.split(".")[1], source="baostock"))
            return rows

        def fake_yahoo(self, symbols, start_date, end_date, adjust_flag="qfq"):
            # 验证 Yahoo 收到的只有 000300
            assert all("000300" in s for s in symbols), f"Yahoo got non-000300 symbols: {symbols}"
            return [_fake_record(s, s.split(".")[0], s.split(".")[1], source="yahoo") for s in symbols]

        tencent_empty = self._mock_other_providers_empty()

        with patch.object(BaostockAshareProvider, "fetch_daily_bars", autospec=True, side_effect=fake_baostock), \
             patch.object(TencentAshareProvider, "fetch_daily_bars", autospec=True, side_effect=tencent_empty), \
             patch.object(SinaAshareProvider, "fetch_daily_bars", autospec=True, side_effect=tencent_empty), \
             patch.object(YfinanceAshareProvider, "fetch_daily_bars", autospec=True, side_effect=fake_yahoo):
            records = AutoAshareProvider().fetch_daily_bars(
                symbols=["600519.SH", "000300.SH"],
                start_date="2025-01-15",
                end_date="2025-01-15",
                adjust_flag="qfq",
            )

        # 600519 来自 baostock，000300 来自 yahoo
        sources = {r["code"]: r["source"] for r in records}
        assert sources["600519"] == "baostock"
        assert sources["000300"] == "yahoo"
