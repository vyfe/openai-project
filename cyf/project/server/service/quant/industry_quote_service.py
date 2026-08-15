from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Optional

from peewee import fn

from quant.db import quant_db
from quant.entities import QuantDailyBar, QuantImportBatch, QuantIndustryBoard, QuantIndustryWatchSymbol, QuantInstrument, QuantMarketSnapshot
from service.quant.common import infer_exchange, normalize_code, normalize_symbol, parse_trade_date, to_float
from service.quant.industry_common import _fetch_json, _fetch_text, _get_secid, _json_dumps, _market_prefix, _now


def fetch_latest_kline(code: str) -> dict[str, Any]:
    params = {
        "secid": _get_secid(code),
        "ut": EASTMONEY_UT,
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "klt": "101",
        "fqt": "1",
        "beg": "0",
        "end": "20500101",
        "lmt": "5",
    }
    url = "https://push2his.eastmoney.com/api/qt/stock/kline/get?" + urllib.parse.urlencode(params)
    payload = _fetch_json(url, referer="https://quote.eastmoney.com/", timeout=6, attempts=1)
    data = payload.get("data") or {}
    klines = data.get("klines") or []
    if not klines:
        raise RuntimeError(f"东方财富未返回 {code} 日线")
    fields = klines[-1].split(",")
    trade_date, open_, close, high, low, volume, amount, amplitude, pct_change, change, turnover = fields
    return {
        "name": str(data.get("name") or code),
        "trade_date": trade_date,
        "open_price": to_float(open_),
        "close_price": to_float(close),
        "high_price": to_float(high),
        "low_price": to_float(low),
        "volume": to_float(volume),
        "amount": to_float(amount),
        "amplitude_pct": to_float(amplitude),
        "pct_change": to_float(pct_change),
        "change": to_float(change),
        "turnover_rate": to_float(turnover),
        "source": "eastmoney_kline",
        "payload": data,
    }

def fetch_sina_snapshot(code: str) -> dict[str, Any]:
    url = f"https://hq.sinajs.cn/list={_market_prefix(code)}{code}"
    text = _fetch_text(url, referer="https://finance.sina.com.cn/", timeout=10, encoding="gbk")
    if '="' not in text:
        raise RuntimeError(f"Sina 未返回 {code} 快照")
    raw = text.split('="', 1)[1].rsplit('";', 1)[0]
    fields = raw.split(",")
    if len(fields) < 32:
        raise RuntimeError(f"Sina 返回 {code} 快照格式异常")
    prev_close = to_float(fields[2]) or 0
    current = to_float(fields[3])
    high = to_float(fields[4])
    low = to_float(fields[5])
    pct_change = None if not prev_close or current is None else (current - prev_close) / prev_close * 100
    amplitude_pct = None if not prev_close or high is None or low is None else (high - low) / prev_close * 100
    return {
        "name": fields[0] or code,
        "trade_date": fields[30],
        "open_price": to_float(fields[1]),
        "close_price": current,
        "current_price": current,
        "high_price": high,
        "low_price": low,
        "preclose_price": prev_close,
        "volume": to_float(fields[8]),
        "amount": to_float(fields[9]),
        "pct_change": pct_change,
        "amplitude_pct": amplitude_pct,
        "source": "sina_snapshot",
        "payload": {"fields": fields},
    }

def fetch_quote(code: str) -> dict[str, Any]:
    fields = "f43,f44,f45,f46,f47,f48,f50,f57,f58,f60,f116,f117,f162,f167,f170"
    url = f"https://push2.eastmoney.com/api/qt/stock/get?secid={_get_secid(code)}&fields={fields}"
    payload = _fetch_json(url, referer="https://quote.eastmoney.com/", timeout=6, attempts=1)
    data = payload.get("data") or {}
    if not data:
        raise RuntimeError(f"东方财富未返回 {code} 行情")
    return {
        "code": str(data.get("f57") or code),
        "name": str(data.get("f58") or code),
        "current_price": _scaled(data.get("f43"), 100),
        "open_price": _scaled(data.get("f46"), 100),
        "high_price": _scaled(data.get("f44"), 100),
        "low_price": _scaled(data.get("f45"), 100),
        "preclose_price": _scaled(data.get("f60"), 100),
        "pct_change": _scaled(data.get("f170"), 100),
        "volume": _scaled(data.get("f47"), 1),
        "amount": _scaled(data.get("f48"), 1),
        "pe_ttm": _scaled(data.get("f162"), 100),
        "pb": _scaled(data.get("f167"), 100),
        "market_cap": _scaled(data.get("f116"), 1),
        "float_market_cap": _scaled(data.get("f117"), 1),
        "source": "eastmoney_quote",
        "payload": data,
    }

def fetch_latest_capital_flow(code: str) -> dict[str, Any]:
    fields2 = "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63"
    url = (
        "https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get"
        f"?lmt=3&klt=101&secid={_get_secid(code)}&fields1=f1,f2,f3,f7&fields2={fields2}"
    )
    payload = _fetch_json(url, referer="https://quote.eastmoney.com/", timeout=5, attempts=1)
    lines = (payload.get("data") or {}).get("klines") or []
    if not lines:
        raise RuntimeError(f"东方财富未返回 {code} 资金流")
    parts = lines[-1].split(",")
    return {
        "trade_date": parts[0],
        "main_flow": to_float(parts[1]),
        "small_flow": to_float(parts[2]),
        "mid_flow": to_float(parts[3]),
        "large_flow": to_float(parts[4]),
        "super_large_flow": to_float(parts[5]),
        "main_flow_pct": to_float(parts[6]),
        "close_price": to_float(parts[11]) if len(parts) > 11 else None,
        "pct_change": to_float(parts[12]) if len(parts) > 12 else None,
        "source": "eastmoney_capital_flow",
        "payload": payload.get("data") or {},
    }

def collect_market_snapshot(board: QuantIndustryBoard, watch: QuantIndustryWatchSymbol) -> dict:
    now = _now()
    code = watch.code
    from service.quant import industry_service
    from service.quant.industry_board_service import INDUSTRY_COLLECT_VERSION
    try:
        kline = industry_service.fetch_latest_kline(code)
    except Exception:
        kline = industry_service.fetch_sina_snapshot(code)
    try:
        quote = industry_service.fetch_quote(code)
    except Exception:
        quote = {}
    try:
        flow = industry_service.fetch_latest_capital_flow(code)
    except Exception:
        flow = {}

    trade_date = parse_trade_date(kline.get("trade_date") or quote.get("trade_date") or flow.get("trade_date") or date.today())
    name = quote.get("name") or kline.get("name") or watch.name or code
    snapshot = {
        "board_id": board.id,
        "symbol": watch.symbol,
        "code": code,
        "exchange": watch.exchange,
        "name": name,
        "trade_date": trade_date,
        "current_price": quote.get("current_price") if quote.get("current_price") is not None else kline.get("current_price") or kline.get("close_price"),
        "open_price": quote.get("open_price") if quote.get("open_price") is not None else kline.get("open_price"),
        "high_price": quote.get("high_price") if quote.get("high_price") is not None else kline.get("high_price"),
        "low_price": quote.get("low_price") if quote.get("low_price") is not None else kline.get("low_price"),
        "close_price": kline.get("close_price") or quote.get("current_price"),
        "preclose_price": quote.get("preclose_price") or kline.get("preclose_price"),
        "pct_change": quote.get("pct_change") if quote.get("pct_change") is not None else kline.get("pct_change"),
        "volume": quote.get("volume") if quote.get("volume") is not None else kline.get("volume"),
        "amount": quote.get("amount") if quote.get("amount") is not None else kline.get("amount"),
        "pe_ttm": quote.get("pe_ttm"),
        "pb": quote.get("pb"),
        "market_cap": quote.get("market_cap"),
        "float_market_cap": quote.get("float_market_cap"),
        "main_flow": flow.get("main_flow"),
        "super_large_flow": flow.get("super_large_flow"),
        "large_flow": flow.get("large_flow"),
        "mid_flow": flow.get("mid_flow"),
        "small_flow": flow.get("small_flow"),
        "main_flow_pct": flow.get("main_flow_pct"),
        "source": ",".join(filter(None, [kline.get("source"), quote.get("source"), flow.get("source")]))[:240],
        "payload_json": _json_dumps({"kline": kline.get("payload"), "quote": quote.get("payload"), "flow": flow.get("payload")}),
        "created_at": now,
        "updated_at": now,
    }
    bar = {
        "symbol": watch.symbol,
        "code": code,
        "exchange": watch.exchange,
        "trade_date": trade_date,
        "adjust_flag": "qfq" if kline.get("source") == "eastmoney_kline" else "raw",
        "open_price": snapshot["open_price"],
        "high_price": snapshot["high_price"],
        "low_price": snapshot["low_price"],
        "close_price": snapshot["close_price"],
        "preclose_price": snapshot["preclose_price"],
        "volume": snapshot["volume"],
        "amount": snapshot["amount"],
        "turnover_rate": kline.get("turnover_rate"),
        "pct_change": snapshot["pct_change"],
        "change": kline.get("change"),
        "amplitude_pct": kline.get("amplitude_pct"),
        "source": snapshot["source"] or INDUSTRY_COLLECT_VERSION,
        "source_run_id": INDUSTRY_COLLECT_VERSION,
        "data_source_version": INDUSTRY_COLLECT_VERSION,
        "created_at": now,
        "updated_at": now,
    }
    with quant_db.atomic():
        QuantInstrument.insert(
            symbol=watch.symbol,
            code=code,
            exchange=watch.exchange,
            market="A_SHARE",
            name=name,
            source=INDUSTRY_COLLECT_VERSION,
            status="active",
            created_at=now,
            updated_at=now,
        ).on_conflict(
            conflict_target=[QuantInstrument.symbol],
            update={
                QuantInstrument.name: name,
                QuantInstrument.source: INDUSTRY_COLLECT_VERSION,
                QuantInstrument.status: "active",
                QuantInstrument.updated_at: now,
            },
        ).execute()
        QuantDailyBar.insert(bar).on_conflict(
            conflict_target=[QuantDailyBar.symbol, QuantDailyBar.trade_date, QuantDailyBar.adjust_flag],
            update={field: bar[field.name] for field in QuantDailyBar._meta.sorted_fields if field.name in bar and field.name != "id"},
        ).execute()
        QuantMarketSnapshot.insert(snapshot).on_conflict(
            conflict_target=[QuantMarketSnapshot.board_id, QuantMarketSnapshot.symbol, QuantMarketSnapshot.trade_date],
            update={field: snapshot[field.name] for field in QuantMarketSnapshot._meta.sorted_fields if field.name in snapshot and field.name != "id"},
        ).execute()
    return {"market_snapshots": 1, "daily_bars": 1}
