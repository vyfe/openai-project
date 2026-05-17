#!/usr/bin/env python3
"""量化数据源 Provider 级检测 — 复用采集端代码，不入库。

用法:
    # 快速检测（重试间隔 3s）
    QUANT_RETRY_SLEEP_SECONDS=3 python doc/quant/check_connectivity.py
    
    # 完整检测（重试间隔 60s，模拟生产）
    python doc/quant/check_connectivity.py
    
    # 指定股票
    python doc/quant/check_connectivity.py 000001.SZ
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime

os.environ.setdefault("ENABLE_EASTMONEY_PATCH", "true")
os.environ.setdefault("QUANT_RETRY_SLEEP_SECONDS", os.environ.get("QUANT_RETRY_SLEEP_SECONDS", "60"))

SERVER_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../cyf/project/server")
sys.path.insert(0, SERVER_DIR)

from quant_client.provider_factory import PROVIDER_MAP


def test_provider(provider_name: str, symbols: list[str], start_date: str, end_date: str) -> dict:
    cls = PROVIDER_MAP.get(provider_name)
    if not cls:
        return {"ok": False, "error": f"未知 provider: {provider_name}"}

    provider = cls()
    start = time.time()
    try:
        records = provider.fetch_daily_bars(symbols=symbols, start_date=start_date, end_date=end_date, adjust_flag="qfq")
        elapsed = time.time() - start
        sources = set(r.get("source", "?") for r in records)
        dates = sorted(set(r.get("trade_date", "")[:10] for r in records))
        has_change = any(r.get("change") is not None for r in records)
        has_amplitude = any(r.get("amplitude_pct") is not None for r in records)
        has_name = any(r.get("name") for r in records)
        extras = []
        if has_name: extras.append("name")
        if has_change: extras.append("change")
        if has_amplitude: extras.append("amplitude")
        return {
            "ok": True, "elapsed": elapsed, "records": len(records),
            "symbols": len(set(r.get("symbol", "") for r in records)),
            "dates": f"{dates[0]}~{dates[-1]}" if dates else "N/A",
            "source": ",".join(sources), "extras": extras,
        }
    except Exception as e:
        elapsed = time.time() - start
        return {"ok": False, "elapsed": elapsed, "error": str(e)[:150]}


def main():
    code = sys.argv[1] if len(sys.argv) > 1 else "600519"
    start_date = "2026-05-14"
    end_date = "2026-05-16"
    retry_sec = os.environ["QUANT_RETRY_SLEEP_SECONDS"]

    print(f"=== 量化数据源 Provider 级检测 ===")
    print(f"时间: {datetime.now().isoformat()}")
    print(f"股票: {code}  区间: {start_date} ~ {end_date}")
    print(f"东财补丁: ENABLE_EASTMONEY_PATCH={os.environ.get('ENABLE_EASTMONEY_PATCH','?')}")
    print(f"重试间隔: QUANT_RETRY_SLEEP_SECONDS={retry_sec}s")
    print()

    providers_order = ["eastmoney", "akshare", "baostock", "sina"]
    results = {}

    for name in providers_order:
        print(f"▶ {name:12s} ...", end=" ", flush=True)
        r = test_provider(name, [code], start_date, end_date)
        results[name] = r
        if r["ok"]:
            extra_str = f" 字段:{'+'.join(r['extras'])}" if r["extras"] else ""
            print(f"✅ {r['elapsed']:5.1f}s | {r['records']}条 | {r['dates']} | src={r['source']}{extra_str}")
        else:
            print(f"❌ {r['elapsed']:5.1f}s | {r['error']}")

    # auto
    print(f"\n▶ {'auto':12s} ...", end=" ", flush=True)
    r = test_provider("auto", [code], start_date, end_date)
    results["auto"] = r
    if r["ok"]:
        extra_str = f" 字段:{'+'.join(r['extras'])}" if r["extras"] else ""
        print(f"✅ {r['elapsed']:5.1f}s | {r['records']}条 | src={r['source']}{extra_str}")
    else:
        print(f"❌ {r['elapsed']:5.1f}s | {r['error']}")

    # 汇总表
    print(f"\n{'─'*60}")
    print(f"{'Provider':<12s} {'':<4s} {'耗时':>6s} {'记录':>5s} {'来源':<12s} {'额外字段'}")
    print(f"{'─'*60}")
    for name in ["eastmoney", "akshare", "baostock", "sina", "auto"]:
        r = results.get(name, {})
        if r.get("ok"):
            ok_str, elapsed = "✅", f"{r['elapsed']:.1f}s"
            records, source = str(r.get("records", "-")), r.get("source", "-")[:12]
            extras = ",".join(r.get("extras", []))
        else:
            ok_str, elapsed = "❌", f"{r.get('elapsed', 0):.1f}s"
            records, source, extras = "-", "-", r.get("error", "-")[:40]
        print(f"{name:<12s} {ok_str:<4s} {elapsed:>6s} {records:>5s} {source:<12s} {extras}")

    ok_count = sum(1 for r in results.values() if r.get("ok"))
    print(f"\n{ok_count}/{len(results)} 通过")


if __name__ == "__main__":
    main()
