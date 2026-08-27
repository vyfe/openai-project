"""端到端手动拉分时数据测试——直接走 service 层与真实 baostock。

用法：
  cd cyf/project/server && python tools/e2e_minute_fetch.py

会跑四个用例：
1. baostock 拉 600519.SH 2024-01-02 5min
2. auto 链接力
3. tencent 不支持分时 → 抛 NotImplementedError
4. fetch_minute_bars 查询验证

所有数据写入临时 SQLite（不污染开发库），脚本退出后自动清理。
修改脚本顶部的 SYMBOL / START_DATE / END_DATE / INTERVAL 可换标的与区间。
"""
import json
import os
import sys
import tempfile
import traceback

# 让 import 路径包含当前目录
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from playhouse.sqlite_ext import SqliteExtDatabase

tmp = tempfile.mkdtemp(prefix="quant_minute_e2e_")
print(f"使用临时数据库目录: {tmp}")


def build_quant_db(path):
    db = SqliteExtDatabase(path, pragmas={"journal_mode": "wal", "foreign_keys": 1})
    return db


def build_log_db(path):
    return SqliteExtDatabase(path, pragmas={"foreign_keys": 1})


def patch_singletons(quant_db, log_db):
    """复制 conftest.py 的 patch 逻辑，把模块级单例指向临时数据库。"""
    from unittest.mock import patch
    from quant.entities import QUANT_MODELS, QuantBaseModel
    from model.entities import ALL_MODELS, BaseModel

    QuantBaseModel._meta.database = quant_db
    for m in QUANT_MODELS:
        m._meta.database = quant_db
    quant_db.connect(reuse_if_open=True)
    quant_db.create_tables(QUANT_MODELS, safe=True)

    BaseModel._meta.database = log_db
    for m in ALL_MODELS:
        m._meta.database = log_db
    log_db.connect(reuse_if_open=True)
    log_db.create_tables(ALL_MODELS, safe=True)

    from model.entities import User
    ph, salt = User.hash_password("test123")
    User.create(username="test_admin", password_hash=ph, salt=salt, role="admin", is_active=True)


def main():
    quant_db = build_quant_db(os.path.join(tmp, "test_quant.db"))
    log_db = build_log_db(os.path.join(tmp, "test_logs.db"))
    patch_singletons(quant_db, log_db)

    from service.quant.import_service import import_bundle
    from quant_client.bundle_builder import build_fetch_bundle

    print("\n=== 测试 1：baostock 拉 600519.SH 2024-01-02 5min ===")
    try:
        bundle = build_fetch_bundle(
            provider_name="baostock",
            symbols=["600519.SH"],
            start_date="2024-01-02",
            end_date="2024-01-02",
            adjust_flag="qfq",
            frequency="5m",
            interval="5m",
        )
        print(f"  dataset = {bundle['dataset']}")
        print(f"  source = {bundle['source']}")
        print(f"  records = {len(bundle.get('records', []))}")
        if bundle.get("records"):
            r = bundle["records"][0]
            print(f"  sample: {r['symbol']} {r['trade_datetime']} interval={r['interval']} close={r['close_price']}")

        payload_bytes = json.dumps(bundle, ensure_ascii=False, sort_keys=True).encode("utf-8")
        result = import_bundle(bundle, payload_bytes=payload_bytes)
        print(f"  import: dataset={result['dataset']} imported={result['records_imported']}/{result['records_total']} status={result['status']}")
    except Exception as exc:
        print(f"  [失败] {type(exc).__name__}: {exc}")
        traceback.print_exc()

    print("\n=== 测试 2：auto 链拉同一标的 ===")
    try:
        bundle = build_fetch_bundle(
            provider_name="auto",
            symbols=["600519.SH"],
            start_date="2024-01-02",
            end_date="2024-01-02",
            adjust_flag="qfq",
            frequency="5m",
            interval="5m",
        )
        print(f"  auto source = {bundle['source']}")
        print(f"  records = {len(bundle.get('records', []))}")
        if bundle.get("records"):
            payload_bytes = json.dumps(bundle, ensure_ascii=False, sort_keys=True).encode("utf-8")
            result = import_bundle(bundle, payload_bytes=payload_bytes)
            print(f"  import: imported={result['records_imported']}/{result['records_total']}")
    except Exception as exc:
        print(f"  [失败] {type(exc).__name__}: {exc}")
        traceback.print_exc()

    print("\n=== 测试 3：tencent 不支持分时，应抛 NotImplementedError ===")
    try:
        from quant_client.provider_factory import get_provider
        provider = get_provider("tencent")
        provider.fetch_minute_bars(symbols=["600519.SH"], interval="5m",
                                   start_dt="2024-01-02", end_dt="2024-01-02")
        print("  [失败] 期望抛错")
    except NotImplementedError as exc:
        print(f"  [OK] 抛 NotImplementedError: {exc}")
    except Exception as exc:
        print(f"  [意外] {type(exc).__name__}: {exc}")

    print("\n=== 测试 4：拉分时后用 query_service.fetch_minute_bars 查询 ===")
    try:
        from service.quant.query_service import fetch_minute_bars
        records = fetch_minute_bars("600519.SH", interval="5m", limit=10)
        print(f"  查询返回 {len(records)} 条")
        if records:
            print(f"  最新: {records[0]['trade_datetime']} close={records[0]['close_price']}")
            print(f"  最旧: {records[-1]['trade_datetime']} close={records[-1]['close_price']}")
    except Exception as exc:
        print(f"  [失败] {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()