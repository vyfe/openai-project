"""import_service 分钟数据集路由集成测试。"""

import json
from datetime import datetime

import pytest


@pytest.fixture()
def sample_minute_bundle():
    return {
        "dataset": "a_share_5min_bars_v1",
        "bundle_version": 1,
        "batch_id": "test-min-bundle",
        "source": "baostock",
        "source_run_id": "test-min-bundle",
        "generated_at": "2024-01-02T10:00:00",
        "market": "A_SHARE",
        "provider_meta": {
            "provider_name": "baostock",
            "frequency": "5m",
            "interval": "5m",
            "adjust_flag": "qfq",
            "start_date": "2024-01-02",
            "end_date": "2024-01-02",
        },
        "records": [
            {
                "symbol": "600519.SH",
                "code": "600519",
                "exchange": "SH",
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
            },
            {
                "symbol": "600519.SH",
                "code": "600519",
                "exchange": "SH",
                "trade_datetime": "2024-01-02T09:40:00",
                "trade_date": "2024-01-02",
                "interval": "5m",
                "adjust_flag": "qfq",
                "open_price": 1701.0,
                "high_price": 1705.0,
                "low_price": 1701.0,
                "close_price": 1704.0,
                "volume": 1500.0,
                "amount": 2556000.0,
                "source": "baostock",
                "data_source_version": "v1",
            },
        ],
    }


class TestImportMinuteBundle:
    def test_import_minute_bundle_persists_to_quant_minute_bar(self, test_db, sample_minute_bundle):
        from quant.entities import QuantMinuteBar
        from service.quant.import_service import import_bundle

        result = import_bundle(
            sample_minute_bundle,
            file_name="test.json",
            payload_bytes=json.dumps(sample_minute_bundle, ensure_ascii=False, sort_keys=True).encode("utf-8"),
        )
        assert result["dataset"] == "a_share_5min_bars_v1"
        assert result["records_imported"] == 2
        assert QuantMinuteBar.select().count() == 2
        first = QuantMinuteBar.get(QuantMinuteBar.symbol == "600519.SH", QuantMinuteBar.trade_datetime == datetime(2024, 1, 2, 9, 35, 0))
        assert first.interval == "5m"
        assert first.adjust_flag == "qfq"
        assert first.open_price == 1700.0
        assert first.close_price == 1701.0

    def test_import_minute_upsert_on_conflict(self, test_db, sample_minute_bundle):
        from quant.entities import QuantMinuteBar
        from service.quant.import_service import import_bundle

        import_bundle(
            sample_minute_bundle,
            payload_bytes=json.dumps(sample_minute_bundle, ensure_ascii=False, sort_keys=True).encode("utf-8"),
        )
        # 改 close_price，并用新 batch_id 让 import_bundle 不走"幂等返回"分支
        sample_minute_bundle["records"][0]["close_price"] = 9999.0
        sample_minute_bundle["batch_id"] = "test-min-bundle-v2"
        sample_minute_bundle["source_run_id"] = "test-min-bundle-v2"
        import_bundle(
            sample_minute_bundle,
            payload_bytes=json.dumps(sample_minute_bundle, ensure_ascii=False, sort_keys=True).encode("utf-8"),
        )
        assert QuantMinuteBar.select().count() == 2
        updated = QuantMinuteBar.get(
            QuantMinuteBar.symbol == "600519.SH",
            QuantMinuteBar.trade_datetime == datetime(2024, 1, 2, 9, 35, 0),
        )
        assert updated.close_price == 9999.0

    def test_import_minute_creates_instrument(self, test_db, sample_minute_bundle):
        from quant.entities import QuantInstrument
        from service.quant.import_service import import_bundle

        import_bundle(
            sample_minute_bundle,
            payload_bytes=json.dumps(sample_minute_bundle, ensure_ascii=False, sort_keys=True).encode("utf-8"),
        )
        instrument = QuantInstrument.get(QuantInstrument.symbol == "600519.SH")
        assert instrument.code == "600519"
        assert instrument.exchange == "SH"
        assert instrument.market == "A_SHARE"

    def test_import_unknown_dataset_raises(self, test_db, sample_minute_bundle):
        from service.quant.import_service import import_bundle

        sample_minute_bundle["dataset"] = "a_share_30min_bars_v1"
        with pytest.raises(ValueError, match="不支持的数据集类型"):
            import_bundle(sample_minute_bundle)

    def test_import_minute_without_trade_date_fills_from_datetime(self, test_db):
        from datetime import date

        from quant.entities import QuantMinuteBar
        from service.quant.import_service import import_bundle

        bundle = {
            "dataset": "a_share_5min_bars_v1",
            "batch_id": "test-fill",
            "source": "baostock",
            "source_run_id": "test-fill",
            "records": [
                {
                    "symbol": "600519.SH", "code": "600519", "exchange": "SH",
                    "trade_datetime": "2024-01-02T09:35:00",
                    # 故意不传 trade_date
                    "interval": "5m", "adjust_flag": "qfq",
                    "open_price": 1, "high_price": 2, "low_price": 0.5, "close_price": 1.5,
                    "volume": 100, "amount": 150,
                    "source": "baostock",
                },
            ],
        }
        import_bundle(bundle)
        bar = QuantMinuteBar.get(QuantMinuteBar.symbol == "600519.SH")
        assert bar.trade_date == date(2024, 1, 2)