#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, timedelta
from typing import Any


EASTMONEY_UT = "fa5fd1943c7b386f172d6893dbfba10b"
EASTMONEY_SUGGEST_TOKEN = "D43BF722C8E33BDC906FB84D85E326E8"


def normalize_code(symbol: str) -> str:
    return str(symbol or "").strip().upper().split(".")[0]


def infer_exchange(code: str) -> str:
    if code.startswith(("6", "5", "9")):
        return "SH"
    if code.startswith(("0", "2", "3")):
        return "SZ"
    if code.startswith(("4", "8")):
        return "BJ"
    return "SZ"


def eastmoney_secid(code: str) -> str:
    return f"1.{code}" if infer_exchange(code) == "SH" else f"0.{code}"


def sina_symbol(code: str) -> str:
    return ("sh" if infer_exchange(code) == "SH" else "sz") + code


def fetch_text(url: str, *, timeout: int, headers: dict[str, str], encoding: str = "utf-8") -> tuple[int, str]:
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
        return int(getattr(resp, "status", 200)), raw.decode(encoding, errors="ignore")


def run_probe(name: str, fn) -> dict[str, Any]:
    started = time.time()
    result: dict[str, Any] = {"name": name, "ok": False}
    try:
        detail = fn()
        result.update(detail)
        result["ok"] = True
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    result["elapsed_ms"] = int((time.time() - started) * 1000)
    return result


def probe_eastmoney_suggest(keyword: str, timeout: int) -> dict[str, Any]:
    params = {
        "input": keyword,
        "type": "14",
        "token": EASTMONEY_SUGGEST_TOKEN,
        "count": "5",
    }
    url = "https://searchapi.eastmoney.com/api/suggest/get?" + urllib.parse.urlencode(params)
    status, text = fetch_text(
        url,
        timeout=timeout,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://www.eastmoney.com/",
        },
    )
    payload = json.loads(text)
    items = (payload.get("QuotationCodeTable") or {}).get("Data") or []
    return {"status": status, "items": len(items), "sample": _sample_stock(items)}


def probe_eastmoney_kline(code: str, start_date: str, end_date: str, timeout: int) -> dict[str, Any]:
    params = {
        "secid": eastmoney_secid(code),
        "ut": EASTMONEY_UT,
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "klt": "101",
        "fqt": "1",
        "beg": start_date.replace("-", ""),
        "end": end_date.replace("-", ""),
        "lmt": "60",
    }
    url = "https://push2his.eastmoney.com/api/qt/stock/kline/get?" + urllib.parse.urlencode(params)
    status, text = fetch_text(
        url,
        timeout=timeout,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://quote.eastmoney.com/",
        },
    )
    payload = json.loads(text)
    data = payload.get("data") or {}
    klines = data.get("klines") or []
    return {"status": status, "items": len(klines), "sample": klines[:1]}


def probe_sina_kline(code: str, timeout: int) -> dict[str, Any]:
    params = {"symbol": sina_symbol(code), "scale": "240", "ma": "no", "datalen": "10"}
    url = "https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?" + urllib.parse.urlencode(params)
    status, text = fetch_text(
        url,
        timeout=timeout,
        encoding="gbk",
        headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://finance.sina.com.cn/",
        },
    )
    payload = json.loads(text)
    return {"status": status, "items": len(payload) if isinstance(payload, list) else 0, "sample": payload[:1] if isinstance(payload, list) else payload}


def probe_sina_snapshot(code: str, timeout: int) -> dict[str, Any]:
    url = f"https://hq.sinajs.cn/list={sina_symbol(code)}"
    status, text = fetch_text(
        url,
        timeout=timeout,
        encoding="gbk",
        headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://finance.sina.com.cn/",
        },
    )
    raw = text.split('="', 1)[1].rsplit('";', 1)[0] if '="' in text else ""
    fields = raw.split(",") if raw else []
    return {"status": status, "items": 1 if len(fields) >= 32 else 0, "sample": fields[:4]}


def probe_ths_news(code: str, timeout: int) -> dict[str, Any]:
    url = f"https://stockpage.10jqka.com.cn/{code}/news/"
    status, text = fetch_text(
        url,
        timeout=timeout,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://stockpage.10jqka.com.cn/",
        },
    )
    return {"status": status, "items": text.count(r"\\\"title\\\""), "bytes": len(text)}


def probe_eastmoney_report(code: str, timeout: int) -> dict[str, Any]:
    params = {
        "industryCode": "*",
        "pageSize": "5",
        "industry": "*",
        "rating": "*",
        "ratingChange": "*",
        "beginTime": "2020-01-01",
        "endTime": date.today().isoformat(),
        "pageNo": "1",
        "fields": "",
        "qType": "0",
        "orgCode": "",
        "code": code,
        "rcode": "",
        "p": "1",
        "pageNum": "1",
        "pageNumber": "1",
        "_": str(int(time.time() * 1000)),
    }
    url = "https://reportapi.eastmoney.com/report/list?" + urllib.parse.urlencode(params)
    status, text = fetch_text(
        url,
        timeout=timeout,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://data.eastmoney.com/report/stock.jshtml",
        },
    )
    payload = json.loads(text)
    items = payload.get("data") or []
    return {"status": status, "items": len(items), "sample": items[:1]}


def _sample_stock(items: list[dict[str, Any]]) -> list[dict[str, str]]:
    sample = []
    for item in items[:3]:
        sample.append({"code": str(item.get("Code", "")), "name": str(item.get("Name", "")), "type": str(item.get("SecurityTypeName", ""))})
    return sample


def print_table(results: list[dict[str, Any]]) -> None:
    print(f"{'source':<24} {'ok':<3} {'ms':>7} {'status':>6} {'items':>6} detail")
    print("-" * 86)
    for item in results:
        detail = ""
        if item.get("ok"):
            sample = item.get("sample")
            detail = json.dumps(sample, ensure_ascii=False)[:160] if sample is not None else ""
        else:
            detail = str(item.get("error", ""))[:160]
        print(
            f"{item['name']:<24} "
            f"{'Y' if item.get('ok') else 'N':<3} "
            f"{int(item.get('elapsed_ms', 0)):>7} "
            f"{str(item.get('status', '-')):>6} "
            f"{str(item.get('items', '-')):>6} "
            f"{detail}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Check quant market-data source network connectivity.")
    parser.add_argument("--symbol", default="000657.SZ", help="A-share symbol, e.g. 000657.SZ")
    parser.add_argument("--keyword", default="", help="Suggest keyword. Defaults to stock code.")
    parser.add_argument("--start-date", default="", help="YYYY-MM-DD. Defaults to yesterday.")
    parser.add_argument("--end-date", default="", help="YYYY-MM-DD. Defaults to today.")
    parser.add_argument("--timeout", type=int, default=8, help="Per-source timeout seconds.")
    parser.add_argument("--json", action="store_true", help="Print raw JSON results.")
    args = parser.parse_args()

    code = normalize_code(args.symbol)
    today = date.today()
    start_date = args.start_date or (today - timedelta(days=7)).isoformat()
    end_date = args.end_date or today.isoformat()
    keyword = args.keyword or code
    timeout = max(1, int(args.timeout or 8))

    probes = [
        ("eastmoney_suggest", lambda: probe_eastmoney_suggest(keyword, timeout)),
        ("eastmoney_kline", lambda: probe_eastmoney_kline(code, start_date, end_date, timeout)),
        ("sina_kline", lambda: probe_sina_kline(code, timeout)),
        ("sina_snapshot", lambda: probe_sina_snapshot(code, timeout)),
        ("ths_stock_news", lambda: probe_ths_news(code, timeout)),
        ("eastmoney_report", lambda: probe_eastmoney_report(code, timeout)),
    ]
    results = [run_probe(name, fn) for name, fn in probes]

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print(f"symbol={args.symbol} code={code} range={start_date}~{end_date} timeout={timeout}s")
        print_table(results)

    return 0 if all(item.get("ok") for item in results) else 2


if __name__ == "__main__":
    sys.exit(main())
