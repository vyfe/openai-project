"""AutoAshareProvider.fetch_minute_bars 与 provider 工厂 guard 测试。

覆盖点：
1. 未实现 fetch_minute_bars 的 provider（tencent/yahoo/akshare）调用时抛 NotImplementedError
2. AutoAshareProvider.fetch_minute_bars 用 baostock → eastmoney → sina 接力
3. Auto chain 全失败时抛 RuntimeError（绝不降级到日线 fetch_daily_bars）
4. 单 symbol 在第一级 provider 拿到数据后，下一级 provider 不再被请求
"""

from unittest.mock import patch

import pytest

from quant_client.provider_factory import (
    AutoAshareProvider,
    get_provider,
)
from quant_client.provider_tencent import TencentAshareProvider
from quant_client.provider_yahoo import YfinanceAshareProvider
from quant_client.provider_akshare import AkshareAshareProvider


class TestUnsupportedMinuteProviders:
    """显式调 fetch_minute_bars 必须立刻抛错，不允许静默降级到 fetch_daily_bars。"""

    @pytest.mark.parametrize("provider_name", ["tencent", "yahoo", "akshare"])
    def test_raises_not_implemented(self, provider_name):
        provider = get_provider(provider_name)
        with pytest.raises(NotImplementedError, match="不支持分时"):
            provider.fetch_minute_bars(
                symbols=["600519.SH"], interval="5m",
                start_dt="2024-01-02", end_dt="2024-01-02",
            )


class TestAutoMinuteRelay:
    def _fake_baostock_records(self):
        return [
            {
                "symbol": "600519.SH", "code": "600519", "exchange": "SH",
                "trade_datetime": "2024-01-02T09:35:00", "trade_date": "2024-01-02",
                "interval": "5m", "adjust_flag": "qfq",
                "open_price": 1700.0, "high_price": 1702.0, "low_price": 1699.0, "close_price": 1701.0,
                "volume": 1000.0, "amount": 1701000.0,
                "source": "baostock", "data_source_version": "v1",
            }
        ]

    def test_baostock_first_round_skips_downstream(self):
        provider = AutoAshareProvider()
        with patch.object(
            __import__("quant_client.provider_baostock", fromlist=["BaostockAshareProvider"]).BaostockAshareProvider,
            "fetch_minute_bars",
            return_value=self._fake_baostock_records(),
        ) as baostock_mock, \
            patch.object(
                __import__("quant_client.provider_eastmoney", fromlist=["EastmoneyAshareProvider"]).EastmoneyAshareProvider,
                "fetch_minute_bars",
            ) as eastmoney_mock, \
            patch.object(
                __import__("quant_client.provider_sina", fromlist=["SinaAshareProvider"]).SinaAshareProvider,
                "fetch_minute_bars",
            ) as sina_mock:
            records = provider.fetch_minute_bars(
                symbols=["600519.SH"], interval="5m",
                start_dt="2024-01-02", end_dt="2024-01-02",
            )
        assert len(records) == 1
        assert records[0]["symbol"] == "600519.SH"
        baostock_mock.assert_called_once()
        # 接力不向下游传递
        eastmoney_mock.assert_not_called()
        sina_mock.assert_not_called()

    def test_falls_back_to_eastmoney_when_baostock_empty(self):
        provider = AutoAshareProvider()
        eastmoney_records = [
            {
                "symbol": "600519.SH", "code": "600519", "exchange": "SH",
                "trade_datetime": "2024-01-02T09:35:00", "trade_date": "2024-01-02",
                "interval": "5m", "adjust_flag": "qfq",
                "open_price": 1700.0, "high_price": 1702.0, "low_price": 1699.0, "close_price": 1701.0,
                "volume": 1000.0, "amount": 1701000.0,
                "source": "eastmoney", "data_source_version": "v1",
            }
        ]
        with patch.object(
            __import__("quant_client.provider_baostock", fromlist=["BaostockAshareProvider"]).BaostockAshareProvider,
            "fetch_minute_bars",
            return_value=[],
        ), \
            patch.object(
                __import__("quant_client.provider_eastmoney", fromlist=["EastmoneyAshareProvider"]).EastmoneyAshareProvider,
                "fetch_minute_bars",
                return_value=eastmoney_records,
            ) as eastmoney_mock, \
            patch.object(
                __import__("quant_client.provider_sina", fromlist=["SinaAshareProvider"]).SinaAshareProvider,
                "fetch_minute_bars",
            ) as sina_mock:
            records = provider.fetch_minute_bars(
                symbols=["600519.SH"], interval="5m",
                start_dt="2024-01-02", end_dt="2024-01-02",
            )
        assert len(records) == 1
        assert records[0]["source"] == "eastmoney"
        eastmoney_mock.assert_called_once()
        sina_mock.assert_not_called()

    def test_all_failures_raise_runtime_error_no_fallback_to_daily(self):
        """分时 chain 全失败必须抛错，绝不允许降级到 fetch_daily_bars。"""
        provider = AutoAshareProvider()
        with patch.object(
            __import__("quant_client.provider_baostock", fromlist=["BaostockAshareProvider"]).BaostockAshareProvider,
            "fetch_minute_bars",
            side_effect=RuntimeError("baostock down"),
        ), \
            patch.object(
                __import__("quant_client.provider_eastmoney", fromlist=["EastmoneyAshareProvider"]).EastmoneyAshareProvider,
                "fetch_minute_bars",
                side_effect=RuntimeError("eastmoney down"),
            ), \
            patch.object(
                __import__("quant_client.provider_sina", fromlist=["SinaAshareProvider"]).SinaAshareProvider,
                "fetch_minute_bars",
                side_effect=RuntimeError("sina down"),
            ), \
            patch.object(
                AutoAshareProvider, "fetch_daily_bars",
            ) as daily_mock:
            with pytest.raises(RuntimeError, match="分钟线获取失败"):
                provider.fetch_minute_bars(
                    symbols=["600519.SH"], interval="5m",
                    start_dt="2024-01-02", end_dt="2024-01-02",
                )
        daily_mock.assert_not_called()

    def test_symbols_partially_covered_skip_downstream(self):
        """已被上游覆盖的 symbol 不进入下游请求。"""
        provider = AutoAshareProvider()
        baostock_records = [
            {
                "symbol": "600519.SH", "code": "600519", "exchange": "SH",
                "trade_datetime": "2024-01-02T09:35:00", "trade_date": "2024-01-02",
                "interval": "5m", "adjust_flag": "qfq",
                "open_price": 1700.0, "high_price": 1702.0, "low_price": 1699.0, "close_price": 1701.0,
                "volume": 1000.0, "amount": 1701000.0,
                "source": "baostock", "data_source_version": "v1",
            }
        ]
        # 第一轮 baostock 只返回 600519；下游应只请求 000001
        call_kwargs_per_provider = {"baostock": [], "eastmoney": []}

        def baostock_side_effect(symbols, **kwargs):
            call_kwargs_per_provider["baostock"].append(list(symbols))
            return baostock_records

        eastmoney_records = [
            {
                "symbol": "000001.SZ", "code": "000001", "exchange": "SZ",
                "trade_datetime": "2024-01-02T09:35:00", "trade_date": "2024-01-02",
                "interval": "5m", "adjust_flag": "qfq",
                "open_price": 10.0, "high_price": 10.5, "low_price": 9.5, "close_price": 10.2,
                "volume": 500.0, "amount": 5100.0,
                "source": "eastmoney", "data_source_version": "v1",
            }
        ]

        def eastmoney_side_effect(symbols, **kwargs):
            call_kwargs_per_provider["eastmoney"].append(list(symbols))
            return eastmoney_records

        with patch.object(
            __import__("quant_client.provider_baostock", fromlist=["BaostockAshareProvider"]).BaostockAshareProvider,
            "fetch_minute_bars",
            side_effect=baostock_side_effect,
        ), \
            patch.object(
                __import__("quant_client.provider_eastmoney", fromlist=["EastmoneyAshareProvider"]).EastmoneyAshareProvider,
                "fetch_minute_bars",
                side_effect=eastmoney_side_effect,
            ), \
            patch.object(
                __import__("quant_client.provider_sina", fromlist=["SinaAshareProvider"]).SinaAshareProvider,
                "fetch_minute_bars",
            ):
            records = provider.fetch_minute_bars(
                symbols=["600519.SH", "000001.SZ"], interval="5m",
                start_dt="2024-01-02", end_dt="2024-01-02",
            )
        assert call_kwargs_per_provider["baostock"][0] == ["600519.SH", "000001.SZ"]
        assert call_kwargs_per_provider["eastmoney"][0] == ["000001.SZ"], "下游只请求未被覆盖的 symbol"
        symbols = sorted([r["symbol"] for r in records])
        assert symbols == ["000001.SZ", "600519.SH"]