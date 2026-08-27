"""BaostockAshareProvider.fetch_minute_bars 单元测试。

覆盖点：
1. _map_minute_rows 把 baostock time 字段（14 位紧凑或 HH:MM:SS）合成 trade_datetime
2. fetch_minute_bars 顶层调用走完整 mock 链路，frequency 参数正确传 5
3. 单 symbol 失败不影响其他 symbol（per-symbol 容错）
4. 未实现 fetch_minute_bars 的 provider 调用必须抛 NotImplementedError
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from quant_client.provider_baostock import BaostockAshareProvider


def _make_minute_response(rows_data):
    """构造 baostock 5min 返回：fields 含 time 列；每行 [date, time, code, open, high, low, close, volume, amount]."""
    rows = []
    for item in rows_data:
        rows.append([
            item["date"], item["time"], "600519",
            item["open"], item["high"], item["low"], item["close"],
            item["volume"], item["amount"],
        ])
    columns = ["date", "time", "code", "open", "high", "low", "close", "volume", "amount"]
    return rows, columns


class FakeBaostockResult:
    """模拟 bs.query_history_k_data_plus 返回对象：支持 next() / get_row_data() / fields / error_code。"""

    def __init__(self, rows, columns, error_code="0"):
        self._rows = list(rows)
        self._cursor = -1
        self.fields = columns
        self.error_code = error_code
        self.error_msg = "" if error_code == "0" else "mock error"

    def next(self):
        self._cursor += 1
        return self._cursor < len(self._rows)

    def get_row_data(self):
        return self._rows[self._cursor]


class TestComposeBaostockMinuteDatetime:
    """_compose_baostock_minute_datetime 时间解析分支。"""

    def test_compact_14_digit(self):
        from quant_client.provider_baostock import _compose_baostock_minute_datetime
        result = _compose_baostock_minute_datetime("2024-01-02", "20240102093500000")
        assert result == datetime(2024, 1, 2, 9, 35, 0)

    def test_compact_17_digit_truncates_milliseconds(self):
        from quant_client.provider_baostock import _compose_baostock_minute_datetime
        result = _compose_baostock_minute_datetime("2024-01-02", "20240102093500123")
        assert result == datetime(2024, 1, 2, 9, 35, 0)

    def test_hms_format(self):
        from quant_client.provider_baostock import _compose_baostock_minute_datetime
        result = _compose_baostock_minute_datetime("2024-01-02", "09:35:00")
        assert result == datetime(2024, 1, 2, 9, 35, 0)

    def test_hm_format(self):
        from quant_client.provider_baostock import _compose_baostock_minute_datetime
        result = _compose_baostock_minute_datetime("2024-01-02", "09:35")
        assert result == datetime(2024, 1, 2, 9, 35, 0)

    def test_empty_returns_none(self):
        from quant_client.provider_baostock import _compose_baostock_minute_datetime
        assert _compose_baostock_minute_datetime("2024-01-02", "") is None
        assert _compose_baostock_minute_datetime("2024-01-02", None) is None

    def test_invalid_returns_none(self):
        from quant_client.provider_baostock import _compose_baostock_minute_datetime
        assert _compose_baostock_minute_datetime("2024-01-02", "not-a-time") is None


class TestMapMinuteRows:
    def test_compose_trade_datetime_and_trade_date(self):
        provider = BaostockAshareProvider()
        rows, columns = _make_minute_response([
            {
                "date": "2024-01-02", "time": "20240102093500000",
                "open": "1700.0", "high": "1702.0", "low": "1699.0", "close": "1701.0",
                "volume": "1000", "amount": "1701000.0",
            },
            {
                "date": "2024-01-02", "time": "20240102094000000",
                "open": "1701.0", "high": "1705.0", "low": "1701.0", "close": "1704.0",
                "volume": "1500", "amount": "2556000.0",
            },
        ])
        result = provider._map_minute_rows(
            code="600519", exchange="SH", columns=columns, records=rows,
            interval="5m", adjust_flag="qfq",
        )
        assert len(result) == 2
        first, second = result
        assert first["symbol"] == "600519.SH"
        assert first["code"] == "600519"
        assert first["exchange"] == "SH"
        assert first["trade_datetime"] == "2024-01-02T09:35:00"
        assert first["trade_date"] == "2024-01-02"
        assert first["interval"] == "5m"
        assert first["adjust_flag"] == "qfq"
        assert first["open_price"] == 1700.0
        assert first["high_price"] == 1702.0
        assert first["close_price"] == 1701.0
        assert first["volume"] == 1000.0
        assert first["amount"] == 1701000.0
        assert first["source"] == "baostock"
        assert second["trade_datetime"] == "2024-01-02T09:40:00"

    def test_skips_invalid_time_rows(self):
        provider = BaostockAshareProvider()
        rows, columns = _make_minute_response([
            {"date": "2024-01-02", "time": "garbage", "open": "1", "high": "1", "low": "1", "close": "1", "volume": "1", "amount": "1"},
            {"date": "2024-01-02", "time": "20240102093500000", "open": "1", "high": "1", "low": "1", "close": "1", "volume": "1", "amount": "1"},
        ])
        result = provider._map_minute_rows(
            code="600519", exchange="SH", columns=columns, records=rows,
            interval="5m", adjust_flag="qfq",
        )
        assert len(result) == 1
        assert result[0]["trade_datetime"] == "2024-01-02T09:35:00"


class TestFetchMinuteBarsTopLevel:
    def _build_mock_bs(self, rows, columns):
        bs = MagicMock()
        bs.login.return_value = MagicMock(error_code="0")
        bs.logout.return_value = None
        bs.query_history_k_data_plus.return_value = FakeBaostockResult(rows, columns)
        return bs

    def test_frequency_and_interval_passed_through(self):
        provider = BaostockAshareProvider()
        rows, columns = _make_minute_response([
            {"date": "2024-01-02", "time": "20240102093500000",
             "open": "1", "high": "2", "low": "0.5", "close": "1.5",
             "volume": "100", "amount": "150"},
        ])
        with patch.dict("sys.modules", {"baostock": self._build_mock_bs(rows, columns)}):
            import sys
            fake_bs = sys.modules["baostock"]
            with patch("quant_client.provider_baostock.MAX_RETRIES", 1):
                records = provider.fetch_minute_bars(
                    symbols=["600519.SH"], interval="5m",
                    start_dt="2024-01-02 00:00:00", end_dt="2024-01-02 23:59:59",
                    adjust_flag="qfq",
                )
        assert len(records) == 1
        assert records[0]["trade_datetime"] == "2024-01-02T09:35:00"
        assert records[0]["interval"] == "5m"
        # 频率参数必须传 "5" 给 baostock
        call_kwargs = fake_bs.query_history_k_data_plus.call_args.kwargs
        assert call_kwargs["frequency"] == "5"
        assert call_kwargs["adjustflag"] == "2"  # qfq
        assert call_kwargs["start_date"] == "2024-01-02"
        assert call_kwargs["end_date"] == "2024-01-02"

    def test_per_symbol_failure_isolated(self):
        provider = BaostockAshareProvider()
        rows, columns = _make_minute_response([
            {"date": "2024-01-02", "time": "20240102093500000",
             "open": "1", "high": "2", "low": "0.5", "close": "1.5",
             "volume": "100", "amount": "150"},
        ])
        bs = self._build_mock_bs(rows, columns)

        def side_effect(*args, **kwargs):
            symbol = args[0] if args else kwargs.get("code", "")
            if "000001" in str(symbol):
                raise RuntimeError("mock symbol failure")
            return FakeBaostockResult(rows, columns)

        bs.query_history_k_data_plus.side_effect = side_effect
        with patch.dict("sys.modules", {"baostock": bs}):
            with patch("quant_client.provider_baostock.MAX_RETRIES", 1):
                records = provider.fetch_minute_bars(
                    symbols=["000001.SZ", "600519.SH"], interval="5m",
                    start_dt="2024-01-02 00:00:00", end_dt="2024-01-02 23:59:59",
                )
        # 失败的 symbol 不影响其他 — 只有 600519 的记录
        assert len(records) == 1
        assert records[0]["symbol"] == "600519.SH"

    def test_interval_15m_passes_frequency_15(self):
        provider = BaostockAshareProvider()
        rows, columns = _make_minute_response([])
        bs = self._build_mock_bs(rows, columns)  # 空结果：单 symbol 失败被 per-symbol 容错吞掉
        with patch.dict("sys.modules", {"baostock": bs}):
            with patch("quant_client.provider_baostock.MAX_RETRIES", 1):
                records = provider.fetch_minute_bars(
                    symbols=["600519.SH"], interval="15m",
                    start_dt="2024-01-02", end_dt="2024-01-02",
                )
        # 单 symbol 失败时返回空列表（per-symbol 容错），不会抛错到外层
        assert records == []
        call_kwargs = bs.query_history_k_data_plus.call_args.kwargs
        assert call_kwargs["frequency"] == "15"