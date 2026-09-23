"""同花顺 ths provider 集成测试 — 覆盖鉴权、字段映射、限流、per-symbol 容错、auto chain 集成。"""

import json
import os
import urllib.error
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

import pytest

from quant_client import provider_ths
from quant_client.provider_ths import (
    ThsAshareProvider,
    _date_to_ms,
    _resolve_api_key,
)


_SHANGHAI_TZ = timezone(timedelta(hours=8))


@pytest.fixture(autouse=True)
def _shorten_ths_retry_sleep(monkeypatch):
    """ths provider 失败时默认 sleep 60s，缩短到 0 加速测试。常量在模块 import 时绑定。"""
    monkeypatch.setattr(provider_ths, "RETRY_SLEEP_SECONDS", 0)


@pytest.fixture
def ths_env(monkeypatch):
    """设置测试用的 API Key；autouse 之外用例也会用。"""
    monkeypatch.setenv("THS_API_KEY", "test-key-abc")
    return "test-key-abc"


class _FakeResp:
    def __init__(self, payload: dict, *, status: int = 200):
        self._bytes = json.dumps(payload).encode("utf-8")
        self.status = status

    def read(self):
        return self._bytes

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _make_ths_response(items: list[dict]) -> dict:
    return {
        "code": 0,
        "message": "success",
        "request_id": "test-request-id",
        "data": {
            "timestamp": 1747584000000,
            "item": items,
        },
    }


def _bar(date_iso: str, *, open: float, high: float, low: float, close: float,
         volume: float, turnover: float) -> dict:
    dt = datetime.strptime(date_iso, "%Y-%m-%d").replace(tzinfo=_SHANGHAI_TZ)
    return {
        "date_ms": int(dt.timestamp() * 1000),
        "open_price": open,
        "high_price": high,
        "low_price": low,
        "close_price": close,
        "volume": volume,
        "turnover": turnover,
    }


class TestDateToMs:
    """ths 时间戳生成：YYYY-MM-DD → Asia/Shanghai 00:00 ms。"""

    def test_known_date(self):
        # 2025-01-10 00:00 +08:00 = 2025-01-09 16:00 UTC = 1736438400000 ms
        ms = _date_to_ms("2025-01-10")
        expected = int(datetime(2025, 1, 10, tzinfo=_SHANGHAI_TZ).timestamp() * 1000)
        assert ms == expected

    def test_invalid_format(self):
        with pytest.raises(ValueError, match="日期格式错误"):
            _date_to_ms("2025/01/10")


class TestResolveApiKey:
    """API Key 解析：env 优先，conf 已在 settings.py 注入 env。"""

    def test_from_env(self, monkeypatch):
        monkeypatch.setenv("THS_API_KEY", "env-key")
        assert _resolve_api_key() == "env-key"

    def test_empty_when_not_set(self, monkeypatch):
        monkeypatch.delenv("THS_API_KEY", raising=False)
        assert _resolve_api_key() == ""


class TestThsFetchHappyPath:
    """正常路径：拉取股票日线 K，验证字段映射。"""

    def test_fetch_stock_qfq(self, ths_env):
        provider = ThsAshareProvider()
        items = [
            _bar("2025-01-13", open=1611.602, high=1626.602, low=1601.722, close=1602.612,
                 volume=3142572.0, turnover=5401389334.87),
            _bar("2025-01-14", open=1602.612, high=1620.0, low=1598.0, close=1610.0,
                 volume=3200000.0, turnover=5150000000.0),
        ]
        with patch("urllib.request.urlopen", return_value=_FakeResp(_make_ths_response(items))):
            records = provider.fetch_daily_bars(
                symbols=["600519.SH"],
                start_date="2025-01-10",
                end_date="2025-01-15",
                adjust_flag="qfq",
            )

        assert len(records) == 2
        r0, r1 = records
        assert r0["symbol"] == "600519.SH"
        assert r0["code"] == "600519"
        assert r0["exchange"] == "SH"
        assert r0["trade_date"] == "2025-01-13"
        assert r0["open_price"] == 1611.602
        assert r0["high_price"] == 1626.602
        assert r0["low_price"] == 1601.722
        assert r0["close_price"] == 1602.612
        assert r0["volume"] == 3142572.0
        assert r0["amount"] == 5401389334.87  # turnover → amount
        assert r0["turnover_rate"] is None   # ths 不提供
        # preclose 首日为 None
        assert r0["preclose_price"] is None
        assert r0["pct_change"] is None
        # 第二日：preclose = 第一日 close，反算 pct_change / change
        assert r1["preclose_price"] == 1602.612
        assert abs(r1["pct_change"] - (1610.0 - 1602.612) / 1602.612 * 100) < 0.001
        assert abs(r1["change"] - (1610.0 - 1602.612)) < 0.001
        assert r1["adjust_flag"] == "qfq"
        assert r0["source"] == "ths"
        assert r0["data_source_version"] == "fuyao_v1"

    def test_fetch_raw_adjust(self, ths_env):
        provider = ThsAshareProvider()
        items = [_bar("2025-01-13", open=1, high=1, low=1, close=1, volume=1, turnover=1)]
        with patch("urllib.request.urlopen", return_value=_FakeResp(_make_ths_response(items))) as m:
            provider.fetch_daily_bars(
                symbols=["000001.SZ"], start_date="2025-01-13", end_date="2025-01-13",
                adjust_flag="raw",
            )
            called_url = m.call_args[0][0].full_url
        assert "adjust=none" in called_url
        assert "thscode=000001.SZ" in called_url

    def test_fetch_hfq_adjust(self, ths_env):
        provider = ThsAshareProvider()
        items = [_bar("2025-01-13", open=1, high=1, low=1, close=1, volume=1, turnover=1)]
        with patch("urllib.request.urlopen", return_value=_FakeResp(_make_ths_response(items))) as m:
            provider.fetch_daily_bars(
                symbols=["600519.SH"], start_date="2025-01-13", end_date="2025-01-13",
                adjust_flag="hfq",
            )
            called_url = m.call_args[0][0].full_url
        assert "adjust=backward" in called_url

    def test_fetch_empty_items_returns_empty(self, ths_env):
        """业务成功但 data.item 为空：不是错，返回空列表。"""
        provider = ThsAshareProvider()
        with patch("urllib.request.urlopen", return_value=_FakeResp(_make_ths_response([]))):
            records = provider.fetch_daily_bars(
                symbols=["600519.SH"], start_date="2025-01-13", end_date="2025-01-13",
            )
        assert records == []


class TestThsFetchErrorCodes:
    """业务错误码：2001/2003/3001/3002/4001/1001..1004 → fail-fast，不重试。"""

    @pytest.mark.parametrize("biz_code", [2001, 2003, 3001, 3002, 4001, 1001, 1003])
    def test_business_error_fail_fast_no_retry(self, ths_env, biz_code):
        provider = ThsAshareProvider()
        call_count = {"n": 0}

        def fake_urlopen(req, **kwargs):
            call_count["n"] += 1
            return _FakeResp({
                "code": biz_code,
                "message": "biz error",
                "request_id": "rid",
                "data": None,
            })

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            records = provider.fetch_daily_bars(
                symbols=["600519.SH"], start_date="2025-01-13", end_date="2025-01-13",
            )
        # 业务错不重试，且 per-symbol 容错吞掉，返回 []
        assert records == []
        assert call_count["n"] == 1, f"code={biz_code} should fail-fast, but was called {call_count['n']} times"

    def test_5002_retries_then_raises(self, ths_env):
        provider = ThsAshareProvider()
        call_count = {"n": 0}

        def fake_urlopen(req, **kwargs):
            call_count["n"] += 1
            return _FakeResp({
                "code": 5002, "message": "upstream timeout", "request_id": "rid", "data": None,
            })

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            records = provider.fetch_daily_bars(
                symbols=["600519.SH"], start_date="2025-01-13", end_date="2025-01-13",
            )
        # 5002 重试 3 次后失败，被 per-symbol 容错吞掉，返回 []
        assert records == []
        assert call_count["n"] == 3, f"5002 should retry 3 times, got {call_count['n']}"


class TestThsFetchHttpErrors:
    """HTTP 层错误：401/403/404/429 → fail-fast；5xx → 重试。"""

    @pytest.mark.parametrize("http_code", [401, 403, 404, 429])
    def test_http_4xx_no_retry(self, ths_env, http_code):
        provider = ThsAshareProvider()
        call_count = {"n": 0}

        def fake_urlopen(req, **kwargs):
            call_count["n"] += 1
            raise urllib.error.HTTPError(
                req.full_url, http_code, "Error", {}, None,
            )

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            records = provider.fetch_daily_bars(
                symbols=["600519.SH"], start_date="2025-01-13", end_date="2025-01-13",
            )
        assert records == []
        assert call_count["n"] == 1, f"HTTP {http_code} should not retry, got {call_count['n']}"

    def test_http_500_retries_then_raises(self, ths_env):
        provider = ThsAshareProvider()
        call_count = {"n": 0}

        def fake_urlopen(req, **kwargs):
            call_count["n"] += 1
            raise urllib.error.HTTPError(
                req.full_url, 500, "Internal Server Error", {}, None,
            )

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            records = provider.fetch_daily_bars(
                symbols=["600519.SH"], start_date="2025-01-13", end_date="2025-01-13",
            )
        assert records == []
        assert call_count["n"] == 3


class TestThsRequestHeaders:
    """请求头必须带 X-api-key。"""

    def test_request_carries_api_key(self, ths_env):
        provider = ThsAshareProvider()
        items = [_bar("2025-01-13", open=1, high=1, low=1, close=1, volume=1, turnover=1)]
        captured_headers = {}

        def fake_urlopen(req, **kwargs):
            captured_headers.update(req.header_items())
            return _FakeResp(_make_ths_response(items))

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            provider.fetch_daily_bars(
                symbols=["600519.SH"], start_date="2025-01-13", end_date="2025-01-13",
            )

        # header_items() 返回 (name, value) 元组列表
        headers_dict = {name.lower(): value for name, value in captured_headers.items()}
        assert headers_dict.get("x-api-key") == "test-key-abc"


class TestThsMissingApiKey:
    """未配置 API Key：抛出清晰错误，不静默。"""

    def test_raises_clear_error_when_no_api_key(self, monkeypatch):
        monkeypatch.delenv("THS_API_KEY", raising=False)
        provider = ThsAshareProvider()
        with pytest.raises(RuntimeError, match="未配置 API Key"):
            provider.fetch_daily_bars(
                symbols=["600519.SH"], start_date="2025-01-13", end_date="2025-01-13",
            )

    def test_constructor_arg_overrides_env(self, monkeypatch):
        monkeypatch.delenv("THS_API_KEY", raising=False)
        provider = ThsAshareProvider(api_key="constructor-key")
        items = [_bar("2025-01-13", open=1, high=1, low=1, close=1, volume=1, turnover=1)]
        captured_headers = {}

        def fake_urlopen(req, **kwargs):
            captured_headers.update(req.header_items())
            return _FakeResp(_make_ths_response(items))

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            provider.fetch_daily_bars(
                symbols=["600519.SH"], start_date="2025-01-13", end_date="2025-01-13",
            )
        headers_dict = {name.lower(): value for name, value in captured_headers.items()}
        assert headers_dict["x-api-key"] == "constructor-key"


class TestThsPartialFailure:
    """单 symbol 失败不影响其他 symbol 的结果。"""

    def test_partial_failure_keeps_successful_records(self, ths_env):
        provider = ThsAshareProvider()

        call_count = {"n": 0}

        def fake_urlopen(req, **kwargs):
            call_count["n"] += 1
            url = req.full_url
            if "thscode=000300" in url:
                raise RuntimeError("ths 假装没 000300")
            items = [_bar("2025-01-15", open=1, high=1, low=1, close=1, volume=1, turnover=1)]
            return _FakeResp(_make_ths_response(items))

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            records = provider.fetch_daily_bars(
                symbols=["600519.SH", "000300.SH", "000001.SZ"],
                start_date="2025-01-15",
                end_date="2025-01-15",
            )
        # 000300 失败，其他成功
        assert {r["code"] for r in records} == {"600519", "000001"}
        assert "000300" not in {r["code"] for r in records}


class TestThsDateRange:
    """日期范围校验：end >= start，跨度 ≤ 10 年。"""

    def test_end_before_start_raises(self, ths_env):
        provider = ThsAshareProvider()
        with pytest.raises(ValueError, match="结束日期早于起始"):
            provider.fetch_daily_bars(
                symbols=["600519.SH"], start_date="2025-01-15", end_date="2025-01-10",
            )

    def test_window_over_10_years_raises(self, ths_env):
        provider = ThsAshareProvider()
        with pytest.raises(ValueError, match="超过 10 年"):
            provider.fetch_daily_bars(
                symbols=["600519.SH"], start_date="2000-01-01", end_date="2025-01-01",
            )


class TestThsInProviderMapAndAutoChain:
    """ths 注册到 PROVIDER_MAP 和 _AUTO_CHAIN 首位。"""

    def test_in_provider_map(self):
        from quant_client.provider_factory import PROVIDER_MAP, get_provider
        assert "ths" in PROVIDER_MAP
        provider = get_provider("ths")
        assert provider.provider_name == "ths"

    def test_in_auto_chain_at_priority_zero(self):
        from quant_client.provider_factory import _AUTO_CHAIN
        first = min(_AUTO_CHAIN, key=lambda x: x[0])
        assert first[1].provider_name == "ths"
        assert first[0] == 0

    def test_not_in_minute_chain(self):
        """ths 仅支持日线，不进入分钟链。"""
        from quant_client.provider_factory import _AUTO_MINUTE_CHAIN
        provider_names = [_cls.provider_name for _, _cls in _AUTO_MINUTE_CHAIN]
        assert "ths" not in provider_names

    def test_auto_chain_priority_order(self):
        """ths 在 baostock/tencent/sina 之前。"""
        from quant_client.provider_factory import _AUTO_CHAIN
        priorities = {cls.provider_name: prio for prio, cls in _AUTO_CHAIN}
        assert priorities["ths"] < priorities["baostock"]
        assert priorities["ths"] < priorities["tencent"]
        assert priorities["ths"] < priorities["sina"]
        assert priorities["ths"] < priorities["yahoo"]


class TestThsMinuteNotImplemented:
    """ths 不支持分时 K，调用必须立即报错。"""

    def test_fetch_minute_bars_raises(self, ths_env):
        provider = ThsAshareProvider()
        with pytest.raises(NotImplementedError, match="不支持分时"):
            provider.fetch_minute_bars(
                symbols=["600519.SH"], interval="5m",
                start_dt="2025-01-13", end_dt="2025-01-13",
            )


class TestThsInAutoChainIntegration:
    """ths 在 auto chain 首位：能覆盖的 symbol 不向下传递；未配置的 api_key 让 ths 失败后由 baostock 兜底。"""

    def test_ths_covers_all_skips_baostock(self, monkeypatch):
        monkeypatch.setenv("THS_API_KEY", "test-key")
        from quant_client.provider_baostock import BaostockAshareProvider
        from quant_client.provider_tencent import TencentAshareProvider
        from quant_client.provider_factory import AutoAshareProvider

        items = [_bar("2025-01-15", open=1, high=1, low=1, close=1, volume=1, turnover=1)]

        def fake_ths(self, symbols, start_date, end_date, adjust_flag="qfq"):
            return [{
                "symbol": s, "code": s.split(".")[0], "exchange": s.split(".")[1],
                "trade_date": "2025-01-15", "adjust_flag": "qfq",
                "open_price": 1, "high_price": 1, "low_price": 1, "close_price": 1,
                "preclose_price": None, "volume": 1, "amount": 1,
                "turnover_rate": None, "pct_change": None, "change": None,
                "source": "ths", "data_source_version": "fuyao_v1",
            } for s in symbols]

        def fake_baostock(self, symbols, **kwargs):
            raise AssertionError("baostock should not be called when ths covers all")

        def fake_tencent(self, symbols, **kwargs):
            raise AssertionError("tencent should not be called when ths covers all")

        with patch("urllib.request.urlopen", return_value=_FakeResp(_make_ths_response(items))), \
             patch.object(BaostockAshareProvider, "fetch_daily_bars", autospec=True, side_effect=fake_baostock), \
             patch.object(TencentAshareProvider, "fetch_daily_bars", autospec=True, side_effect=fake_tencent):
            records = AutoAshareProvider().fetch_daily_bars(
                symbols=["600519.SH"], start_date="2025-01-15", end_date="2025-01-15",
            )
        assert len(records) == 1
        assert records[0]["source"] == "ths"

    def test_ths_no_api_key_falls_through_to_baostock(self, monkeypatch):
        monkeypatch.delenv("THS_API_KEY", raising=False)
        from quant_client.provider_baostock import BaostockAshareProvider
        from quant_client.provider_factory import AutoAshareProvider

        def fake_baostock(self, symbols, start_date, end_date, adjust_flag="qfq"):
            return [{
                "symbol": s, "code": s.split(".")[0], "exchange": s.split(".")[1],
                "trade_date": "2025-01-15", "adjust_flag": "qfq",
                "open_price": 1, "high_price": 1, "low_price": 1, "close_price": 1,
                "preclose_price": None, "volume": 1, "amount": 1,
                "turnover_rate": 1.0, "pct_change": 0.0, "change": 0.0,
                "source": "baostock", "data_source_version": "v1",
            } for s in symbols]

        with patch.object(BaostockAshareProvider, "fetch_daily_bars", autospec=True, side_effect=fake_baostock):
            records = AutoAshareProvider().fetch_daily_bars(
                symbols=["600519.SH"], start_date="2025-01-15", end_date="2025-01-15",
            )
        assert len(records) == 1
        assert records[0]["source"] == "baostock"