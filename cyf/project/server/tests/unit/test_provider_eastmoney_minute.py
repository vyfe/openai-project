"""EastmoneyAshareProvider.fetch_minute_bars 单元测试。

覆盖点：
1. klt 参数随 interval 正确转换（5m → "5"，15m → "15"）
2. URL 中 klt=5（不是日线 klt=101）
3. 分钟线 fields 切到分时返回格式（trade_datetime 合成）
4. per-symbol 容错
5. NID session header 仍然复用
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from quant_client.provider_eastmoney import EastmoneyAshareProvider


def _fake_response(payload):
    body = json.dumps(payload).encode("utf-8")

    class _Resp:
        def __init__(self, body):
            self._body = body

        def read(self):
            return self._body

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    return _Resp(body)


def _make_minute_payload(rows):
    return {"data": {"name": "贵州茅台", "klines": rows}}


def _make_minute_row(date_text, open_, close, high, low, volume="100", amount="1000"):
    return (
        f"{date_text},{open_},{close},{high},{low},{volume},{amount},"
        "1.5,0.5,0.5,1.0"
    )


class TestEastmoneyKltMapping:
    def test_klt_5m_passes_klt_5(self):
        provider = EastmoneyAshareProvider()
        payload = _make_minute_payload([])
        session = MagicMock()
        session.get_headers.return_value = ({"User-Agent": "test"}, "")
        captured_urls = []

        def fake_urlopen(req, timeout=None):
            captured_urls.append(req.full_url)
            return _fake_response(payload)

        with patch("quant_client.provider_eastmoney.get_eastmoney_session", return_value=session), \
             patch("quant_client.provider_eastmoney.urllib.request.urlopen", side_effect=fake_urlopen), \
             patch("quant_client.provider_eastmoney.MAX_RETRIES", 1):
            with pytest.raises(RuntimeError, match="未返回"):
                provider._fetch_one_symbol_minute(
                    raw_symbol="600519.SH", interval="5m",
                    start_dt="2024-01-02", end_dt="2024-01-02",
                    adjust_flag="qfq",
                )
        assert any("klt=5" in url for url in captured_urls)
        assert not any("klt=101" in url for url in captured_urls), "日线 klt=101 不可出现在分时 URL"


class TestEastmoneyMinuteParsing:
    def test_trade_datetime_iso_format(self):
        provider = EastmoneyAshareProvider()
        rows = [
            _make_minute_row("2024-01-02 09:35", "1700.0", "1701.0", "1702.0", "1699.0"),
            _make_minute_row("2024-01-02 09:40", "1701.0", "1704.0", "1705.0", "1701.0"),
        ]
        payload = _make_minute_payload(rows)
        session = MagicMock()
        session.get_headers.return_value = ({"User-Agent": "test"}, "")

        with patch("quant_client.provider_eastmoney.get_eastmoney_session", return_value=session), \
             patch("quant_client.provider_eastmoney.urllib.request.urlopen", return_value=_fake_response(payload)), \
             patch("quant_client.provider_eastmoney.MAX_RETRIES", 1):
            result = provider._fetch_one_symbol_minute(
                raw_symbol="600519.SH", interval="5m",
                start_dt="2024-01-02", end_dt="2024-01-02",
                adjust_flag="qfq",
            )
        assert len(result) == 2
        first, second = result
        assert first["symbol"] == "600519.SH"
        assert first["trade_datetime"] == "2024-01-02T09:35:00"
        assert first["trade_date"] == "2024-01-02"
        assert first["interval"] == "5m"
        assert first["open_price"] == 1700.0
        assert first["high_price"] == 1702.0
        assert first["close_price"] == 1701.0
        assert first["amount"] == 1000.0
        assert second["trade_datetime"] == "2024-01-02T09:40:00"

    def test_date_range_filter(self):
        provider = EastmoneyAshareProvider()
        rows = [
            _make_minute_row("2024-01-01 09:35", "1", "1", "1", "1"),
            _make_minute_row("2024-01-02 09:35", "1", "1", "1", "1"),
            _make_minute_row("2024-01-03 09:35", "1", "1", "1", "1"),
        ]
        payload = _make_minute_payload(rows)
        session = MagicMock()
        session.get_headers.return_value = ({"User-Agent": "test"}, "")

        with patch("quant_client.provider_eastmoney.get_eastmoney_session", return_value=session), \
             patch("quant_client.provider_eastmoney.urllib.request.urlopen", return_value=_fake_response(payload)), \
             patch("quant_client.provider_eastmoney.MAX_RETRIES", 1):
            result = provider._fetch_one_symbol_minute(
                raw_symbol="600519.SH", interval="5m",
                start_dt="2024-01-02", end_dt="2024-01-02",
                adjust_flag="qfq",
            )
        assert len(result) == 1
        assert result[0]["trade_date"] == "2024-01-02"

    def test_invalid_interval_raises(self):
        provider = EastmoneyAshareProvider()
        with pytest.raises(ValueError, match="不支持的 interval"):
            provider._fetch_one_symbol_minute(
                raw_symbol="600519.SH", interval="3m",
                start_dt="2024-01-02", end_dt="2024-01-02",
                adjust_flag="qfq",
            )


class TestEastmoneyMinuteTopLevel:
    def test_per_symbol_failure_isolated(self):
        provider = EastmoneyAshareProvider()
        session = MagicMock()
        session.get_headers.return_value = ({"User-Agent": "test"}, "")
        payloads = {
            "1.600519": _make_minute_payload([
                _make_minute_row("2024-01-02 09:35", "1", "1.5", "2", "0.5"),
            ]),
            "0.000001": _make_minute_payload([]),  # empty
        }

        def urlopen_side_effect(req, timeout=None):
            for prefix, payload in payloads.items():
                if prefix in req.full_url:
                    if not payload["data"]["klines"]:
                        raise RuntimeError("empty payload")
                    return _fake_response(payload)
            raise RuntimeError("unexpected url")

        with patch("quant_client.provider_eastmoney.get_eastmoney_session", return_value=session), \
             patch("quant_client.provider_eastmoney.urllib.request.urlopen", side_effect=urlopen_side_effect), \
             patch("quant_client.provider_eastmoney.MAX_RETRIES", 1):
            records = provider.fetch_minute_bars(
                symbols=["600519.SH", "000001.SZ"], interval="5m",
                start_dt="2024-01-02", end_dt="2024-01-02",
                adjust_flag="qfq",
            )
        assert len(records) == 1
        assert records[0]["symbol"] == "600519.SH"

    def test_index_symbols_skipped_without_api_call(self):
        """指数在白名单内，fetch_minute_bars 必须直接跳过（不发请求）。"""
        provider = EastmoneyAshareProvider()
        session = MagicMock()
        session.get_headers.return_value = ({"User-Agent": "test"}, "")

        with patch("quant_client.provider_eastmoney.get_eastmoney_session", return_value=session), \
             patch("quant_client.provider_eastmoney.urllib.request.urlopen") as mock_urlopen, \
             patch("quant_client.provider_eastmoney.MAX_RETRIES", 1):
            records = provider.fetch_minute_bars(
                symbols=["000300.SH", "399006.SZ", "399001.SZ"], interval="5m",
                start_dt="2024-01-02", end_dt="2024-01-02",
                adjust_flag="qfq",
            )
        assert records == []
        mock_urlopen.assert_not_called()

    def test_stocks_fetched_indices_skipped(self):
        """混传：股票正常拉取，指数被跳过（只对股票发起 urlopen）。"""
        provider = EastmoneyAshareProvider()
        session = MagicMock()
        session.get_headers.return_value = ({"User-Agent": "test"}, "")

        def urlopen_side_effect(req, timeout=None):
            if "1.600519" in req.full_url or "0.300750" in req.full_url:
                return _fake_response(_make_minute_payload([
                    _make_minute_row("2024-01-02 09:35", "1", "1.5", "2", "0.5"),
                ]))
            raise AssertionError(f"指数 URL 不应被请求: {req.full_url}")

        with patch("quant_client.provider_eastmoney.get_eastmoney_session", return_value=session), \
             patch("quant_client.provider_eastmoney.urllib.request.urlopen", side_effect=urlopen_side_effect), \
             patch("quant_client.provider_eastmoney.MAX_RETRIES", 1):
            records = provider.fetch_minute_bars(
                symbols=["600519.SH", "000300.SH", "300750.SZ", "399006.SZ"],
                interval="5m",
                start_dt="2024-01-02", end_dt="2024-01-02",
                adjust_flag="qfq",
            )
        assert len(records) == 2
        symbols_returned = {r["symbol"] for r in records}
        assert symbols_returned == {"600519.SH", "300750.SZ"}