#!/usr/bin/env python3
"""同花顺 ths provider 本地调用 demo。

使用方式：
1. 在 conf.ini [quant].ths_api_key 填入真实 key，或
2. 设置环境变量 `THS_API_KEY=<your-key>`（推荐）
3. `python tools/ths_demo.py` 或 `python tools/ths_demo.py --symbol 600519.SH`

输出：拉取指定标的最近 N 个交易日的日 K，按字段名一一映射展示。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, timedelta


def _resolve_ths_dir():
    server_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if server_root not in sys.path:
        sys.path.insert(0, server_root)


def main() -> int:
    parser = argparse.ArgumentParser(description="同花顺 ths provider 本地连通性 + 字段映射 demo")
    parser.add_argument("--symbol", default="600519.SH", help="thscode，如 600519.SH")
    parser.add_argument("--days", type=int, default=5, help="最近 N 天（默认 5）")
    parser.add_argument("--adjust", default="qfq", choices=["qfq", "hfq", "raw"], help="复权方式")
    parser.add_argument("--raw-response", action="store_true", help="只打印原始响应，不做字段映射")
    args = parser.parse_args()

    _resolve_ths_dir()

    from quant_client.provider_ths import ThsAshareProvider

    end_date = date.today().isoformat()
    start_date = (date.today() - timedelta(days=args.days + 30)).isoformat()

    api_key = os.environ.get("THS_API_KEY", "").strip()
    if not api_key:
        try:
            from conf.settings import settings
            api_key = getattr(settings, "quant_ths_api_key", "")
        except Exception:
            pass

    if not api_key:
        print(
            "⚠️  未检测到 THS_API_KEY。请在 conf.ini [quant].ths_api_key 填写，或导出环境变量 THS_API_KEY。",
            file=sys.stderr,
        )
        print(
            "   获取地址：https://fuyao.aicubes.cn/admin （用同花顺账号登录后创建）",
            file=sys.stderr,
        )
        return 2

    provider = ThsAshareProvider(api_key=api_key)
    print(f"[demo] symbol={args.symbol} start={start_date} end={end_date} adjust={args.adjust}")
    print(f"[demo] base_url=https://fuyao.aicubes.cn/api/a-share/prices/historical")
    print(f"[demo] api_key=***{api_key[-6:] if len(api_key) >= 6 else 'short'}（已脱敏）")
    print()

    try:
        records = provider.fetch_daily_bars(
            symbols=[args.symbol],
            start_date=start_date,
            end_date=end_date,
            adjust_flag=args.adjust,
        )
    except Exception as exc:
        print(f"❌ fetch 失败: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    if args.raw_response:
        print(json.dumps(records, ensure_ascii=False, indent=2))
        return 0

    print(f"✅ 拉到 {len(records)} 条记录：")
    if not records:
        print("（空 —— 标的可能停牌 / 未上市 / 区间无数据）")
        return 0

    print()
    print(f"{'trade_date':<12} {'adjust':<6} {'open':>10} {'high':>10} {'low':>10} {'close':>10} "
          f"{'preclose':>10} {'volume':>14} {'amount':>16} {'pct_change':>10}")
    print("-" * 120)
    for r in records:
        preclose_text = (
            f"{r['preclose_price']:>10.3f}"
            if r['preclose_price'] is not None
            else f"{'-':>10}"
        )
        pct_text = (
            f"{r['pct_change']:>10.3f}"
            if r['pct_change'] is not None
            else f"{'-':>10}"
        )
        print(
            f"{r['trade_date']:<12} {r['adjust_flag']:<6} "
            f"{r['open_price']!s:>10} {r['high_price']!s:>10} {r['low_price']!s:>10} "
            f"{r['close_price']!s:>10} {preclose_text} "
            f"{r['volume']!s:>14} {r['amount']!s:>16} {pct_text}"
        )

    print()
    print(f"source={records[0]['source']}  version={records[0]['data_source_version']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())