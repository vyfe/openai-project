"""import_service 集成测试 — 验证 instrument.name 在 import 时不会被空串覆盖。"""

import json
from datetime import datetime, timedelta

import pytest

from quant.entities import QuantInstrument, QuantDailyBar
from service.quant.import_service import import_bundle
from quant_client.constants import SUPPORTED_DATASET


def _make_bundle(symbols_with_codes, start_date="2025-01-10", end_date="2025-01-15"):
    """构造一个最简单的 fetch bundle，不含 name。模拟 baostock/tencent/sina 的 records。"""
    records = []
    for symbol, code, exchange in symbols_with_codes:
        records.append({
            "symbol": symbol,
            "code": code,
            "exchange": exchange,
            "trade_date": "2025-01-15",
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
            "source": "test",
            "data_source_version": "v1",
        })
    return {
        "dataset": SUPPORTED_DATASET,
        "bundle_version": 1,
        "batch_id": "test-batch-001",
        "source": "test",
        "source_run_id": "test-batch-001",
        "generated_at": datetime.now().isoformat(),
        "market": "A_SHARE",
        "provider_meta": {
            "provider_name": "test",
            "requested_provider": "test",
            "provider_version": "v1",
            "adjust_flag": "qfq",
            "start_date": start_date,
            "end_date": end_date,
        },
        "records": records,
    }


class TestImportBundlePreservesInstrumentName:
    """import_bundle 不应覆盖 quant_instrument.name（即使 bundle 里 name 为空）。"""

    def test_existing_name_preserved_when_bundle_has_no_name(self):
        # 预置一条人工添加的记录，带中文名
        QuantInstrument.create(
            symbol="600519.SH",
            code="600519",
            exchange="SH",
            market="A_SHARE",
            name="贵州茅台",
            source="manual",
            status="active",
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        # bundle 里 records 没有 name 字段——模拟 baostock/tencent/sina 的行为
        bundle = _make_bundle([("600519.SH", "600519", "SH")])
        import_bundle(bundle)
        # 名字必须保留
        record = QuantInstrument.get(QuantInstrument.symbol == "600519.SH")
        assert record.name == "贵州茅台"

    def test_new_instrument_inserted_with_empty_name(self):
        """首次插入时 name 为空是允许的，由 refresh_names 后续回填。"""
        bundle = _make_bundle([("000001.SZ", "000001", "SZ")])
        import_bundle(bundle)
        record = QuantInstrument.get(QuantInstrument.symbol == "000001.SZ")
        assert record.symbol == "000001.SZ"
        assert record.code == "000001"
        assert record.exchange == "SZ"
        # name 字段为空（不会因 import_bundle 被人工覆盖）
        assert record.name == ""

    def test_other_fields_still_updated_on_conflict(self):
        """on_conflict 仍应更新 source / updated_at 等元数据。"""
        QuantInstrument.create(
            symbol="000002.SZ",
            code="000002",
            exchange="SZ",
            market="A_SHARE",
            name="万科A",
            source="manual",
            status="active",
            created_at=datetime.now() - timedelta(days=30),
            updated_at=datetime.now() - timedelta(days=30),
        )
        original_created = QuantInstrument.get(QuantInstrument.symbol == "000002.SZ").created_at
        bundle = _make_bundle([("000002.SZ", "000002", "SZ")])
        import_bundle(bundle)
        record = QuantInstrument.get(QuantInstrument.symbol == "000002.SZ")
        assert record.name == "万科A"  # name 保留
        assert record.source == "test"  # source 更新
        # created_at 应该不变（insert 时设置，update 不动）
        assert record.created_at == original_created

    def test_daily_bar_inserted(self):
        """导入 bundle 同时写入 quant_daily_bar（不受 name 修复影响）。"""
        bundle = _make_bundle([("600000.SH", "600000", "SH")])
        import_bundle(bundle)
        bar = QuantDailyBar.get_or_none(
            (QuantDailyBar.symbol == "600000.SH") & (QuantDailyBar.trade_date == "2025-01-15")
        )
        assert bar is not None
        assert bar.close_price == 10.5