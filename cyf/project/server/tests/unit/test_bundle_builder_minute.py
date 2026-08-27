"""bundle_builder frequency 分发单元测试。"""

from unittest.mock import MagicMock, patch

import pytest

from quant_client.bundle_builder import build_fetch_bundle


def _make_minute_record(symbol="600519.SH"):
    return {
        "symbol": symbol,
        "code": symbol.split(".")[0],
        "exchange": symbol.split(".")[1],
        "trade_datetime": "2024-01-02T09:35:00",
        "trade_date": "2024-01-02",
        "interval": "5m",
        "adjust_flag": "qfq",
        "open_price": 1700.0,
        "high_price": 1702.0,
        "low_price": 1699.0,
        "close_price": 1701.0,
        "volume": 1000.0,
        "amount": 1701000.0,
        "source": "baostock",
        "data_source_version": "v1",
    }


class TestBuildFetchBundleFrequencyDispatch:
    def test_frequency_1d_uses_daily_dataset(self):
        provider = MagicMock()
        provider.fetch_daily_bars.return_value = [
            {"symbol": "600519.SH", "trade_date": "2024-01-02", "source": "baostock"},
        ]
        with patch("quant_client.bundle_builder.get_provider", return_value=provider):
            bundle = build_fetch_bundle(
                "baostock", ["600519.SH"], "2024-01-02", "2024-01-02", "qfq",
            )
        assert bundle["dataset"] == "a_share_daily_bars_v1"
        assert bundle["provider_meta"]["frequency"] == "1d"
        provider.fetch_daily_bars.assert_called_once()
        provider.fetch_minute_bars.assert_not_called()

    def test_frequency_5m_uses_minute_dataset_and_method(self):
        provider = MagicMock()
        provider.fetch_minute_bars.return_value = [_make_minute_record()]
        with patch("quant_client.bundle_builder.get_provider", return_value=provider):
            bundle = build_fetch_bundle(
                "baostock", ["600519.SH"], "2024-01-02 00:00:00", "2024-01-02 23:59:59",
                "qfq", frequency="5m", interval="5m",
            )
        assert bundle["dataset"] == "a_share_5min_bars_v1"
        assert bundle["provider_meta"]["frequency"] == "5m"
        assert bundle["provider_meta"]["interval"] == "5m"
        provider.fetch_minute_bars.assert_called_once()
        provider.fetch_daily_bars.assert_not_called()

    def test_unsupported_provider_for_minute_raises(self):
        provider = MagicMock(spec=["fetch_daily_bars"])  # 没有 fetch_minute_bars
        provider.provider_name = "tencent"
        provider.provider_version = "v1"
        with patch("quant_client.bundle_builder.get_provider", return_value=provider):
            with pytest.raises(RuntimeError, match="不支持分时"):
                build_fetch_bundle(
                    "tencent", ["600519.SH"], "2024-01-02", "2024-01-02",
                    "qfq", frequency="5m", interval="5m",
                )

    def test_invalid_frequency_raises(self):
        with pytest.raises(ValueError, match="不支持的 frequency"):
            build_fetch_bundle(
                "auto", ["600519.SH"], "2024-01-02", "2024-01-02",
                "qfq", frequency="3m",
            )