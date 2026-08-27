"""SinaAshareProvider.fetch_minute_bars 单元测试。

覆盖点：
1. URL 中 scale=5（不是日线 scale=240）
2. start_dt/end_dt 非今日直接抛 ValueError（新浪分时仅当日）
3. trade_datetime 合成（day 字段形如 "2024-01-02 09:35"）
4. per-symbol 容错
"""

import json
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from quant_client.provider_sina import SinaAshareProvider


def _fake_response(payload_bytes):
    class _Resp:
        def __init__(self, body):
            self._body = body

        def read(self):
            return self._body

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    return _Resp(payload_bytes)


def _gbk_response(payload):
    return _fake_response(json.dumps(payload).encode("gbk"))


def _make_minute_payload(rows):
    return rows  # sina minute API 直接返回数组


class TestSinaScaleMapping:
    def test_scale_5_for_5m(self):
        provider = SinaAshareProvider()
        session = MagicMock()
        session.get_headers.return_value = ({"User-Agent": "test"}, "")
        captured_urls = []

        def fake_urlopen(req, timeout=None):
            captured_urls.append(req.full_url)
            return _gbk_response([])

        with patch("quant_client.provider_sina.urllib.request.urlopen", side_effect=fake_urlopen), \
             patch("quant_client.provider_sina.MAX_RETRIES", 1):
            today = date.today().isoformat()
            with pytest.raises(RuntimeError, match="分时"):
                provider._fetch_one_symbol_minute(raw_symbol="600519.SH", interval="5m")
        assert any("scale=5" in url for url in captured_urls)
        assert not any("scale=240" in url for url in captured_urls)


class TestSinaTodayRestriction:
    def test_non_today_raises(self):
        provider = SinaAshareProvider()
        with pytest.raises(ValueError, match="仅支持当日"):
            provider.fetch_minute_bars(
                symbols=["600519.SH"], interval="5m",
                start_dt="2024-01-02", end_dt="2024-01-02",
            )

    def test_cross_day_raises(self):
        provider = SinaAshareProvider()
        today = date.today().isoformat()
        with pytest.raises(ValueError, match="仅支持当日"):
            provider.fetch_minute_bars(
                symbols=["600519.SH"], interval="5m",
                start_dt=today, end_dt="2024-01-02",
            )

    def test_unsupported_interval_raises(self):
        provider = SinaAshareProvider()
        with pytest.raises(ValueError, match="不支持的 interval"):
            provider.fetch_minute_bars(
                symbols=["600519.SH"], interval="3m",
                start_dt=date.today().isoformat(), end_dt=date.today().isoformat(),
            )


class TestSinaMinuteParsing:
    def test_trade_datetime_iso_format(self, monkeypatch):
        provider = SinaAshareProvider()
        today = date.today()
        day_text = today.strftime("%Y-%m-%d")
        rows = [
            {"day": f"{day_text} 09:35", "open": "1700.0", "high": "1702.0", "low": "1699.0", "close": "1701.0", "volume": "1000"},
            {"day": f"{day_text} 09:40", "open": "1701.0", "high": "1705.0", "low": "1701.0", "close": "1704.0", "volume": "1500"},
        ]
        with patch("quant_client.provider_sina.urllib.request.urlopen", return_value=_gbk_response(rows)), \
             patch("quant_client.provider_sina.MAX_RETRIES", 1):
            result = provider._fetch_one_symbol_minute(raw_symbol="600519.SH", interval="5m")
        assert len(result) == 2
        first, second = result
        assert first["symbol"] == "600519.SH"
        assert first["trade_datetime"] == f"{day_text}T09:35:00"
        assert first["trade_date"] == day_text
        assert first["interval"] == "5m"
        assert first["adjust_flag"] == "raw"
        assert first["volume"] == 1000.0
        assert second["trade_datetime"] == f"{day_text}T09:40:00"

    def test_skips_non_today_rows(self):
        provider = SinaAshareProvider()
        today = date.today()
        day_text = today.strftime("%Y-%m-%d")
        rows = [
            {"day": "2024-01-02 09:35", "open": "1", "high": "2", "low": "0.5", "close": "1.5", "volume": "100"},
            {"day": f"{day_text} 09:35", "open": "1", "high": "2", "low": "0.5", "close": "1.5", "volume": "100"},
        ]
        with patch("quant_client.provider_sina.urllib.request.urlopen", return_value=_gbk_response(rows)), \
             patch("quant_client.provider_sina.MAX_RETRIES", 1):
            result = provider._fetch_one_symbol_minute(raw_symbol="600519.SH", interval="5m")
        assert len(result) == 1
        assert result[0]["trade_date"] == day_text

    def test_invalid_day_returns_no_records(self):
        provider = SinaAshareProvider()
        rows = [
            {"day": "garbage", "open": "1", "high": "2", "low": "0.5", "close": "1.5", "volume": "100"},
        ]
        with patch("quant_client.provider_sina.urllib.request.urlopen", return_value=_gbk_response(rows)), \
             patch("quant_client.provider_sina.MAX_RETRIES", 1):
            with pytest.raises(RuntimeError, match="未返回"):
                provider._fetch_one_symbol_minute(raw_symbol="600519.SH", interval="5m")


class TestSinaMinuteTopLevel:
    def test_per_symbol_failure_isolated(self):
        provider = SinaAshareProvider()
        today = date.today()
        day_text = today.strftime("%Y-%m-%d")
        call_count = {"n": 0}

        def fake_urlopen(req, timeout=None):
            call_count["n"] += 1
            if "000001" in req.full_url:
                raise RuntimeError("mock symbol failure")
            return _gbk_response([
                {"day": f"{day_text} 09:35", "open": "1", "high": "2", "low": "0.5", "close": "1.5", "volume": "100"},
            ])

        with patch("quant_client.provider_sina.urllib.request.urlopen", side_effect=fake_urlopen), \
             patch("quant_client.provider_sina.MAX_RETRIES", 1):
            records = provider.fetch_minute_bars(
                symbols=["000001.SZ", "600519.SH"], interval="5m",
                start_dt=day_text, end_dt=day_text,
            )
        assert len(records) == 1
        assert records[0]["symbol"] == "600519.SH"