from __future__ import annotations

import hashlib
import html
import json
import re
import ssl
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from typing import Any, Optional

from peewee import fn

from quant.db import quant_db
from quant.entities import (
    QuantDailyBar,
    QuantImportBatch,
    QuantIndustryBoard,
    QuantIndustryIndicatorSnapshot,
    QuantIndustryNewsItem,
    QuantIndustryWatchSymbol,
    QuantInstrument,
    QuantMarketSnapshot,
    QuantResearchReportItem,
)
from service.quant.common import infer_exchange, normalize_code, normalize_symbol, parse_trade_date, to_float


EASTMONEY_UT = "fa5fd1943c7b386f172d6893dbfba10b"
INDUSTRY_COLLECT_VERSION = "industry-collect-v1"

DEFAULT_INDUSTRY_BOARDS = [
    {
        "board_key": "tungsten",
        "name": "钨产业链",
        "description": "钨矿、冶炼、硬质合金和出口管制相关跟踪。",
        "keywords": ["钨", "钨矿", "仲钨酸铵", "碳化钨", "出口管制"],
        "symbols": [
            {
                "symbol": "000657.SZ",
                "name": "中钨高新",
                "role": "钨矿-冶炼-硬质合金全产业链基准",
                "keywords": ["中钨高新", "钨", "硬质合金"],
                "weight": 1.0,
            }
        ],
    },
    {
        "board_key": "pcb_drill",
        "name": "PCB钻针",
        "description": "PCB微钻、精密刀具、IC载板和AI服务器链路跟踪。",
        "keywords": ["PCB钻针", "微钻", "IC载板", "AI服务器"],
        "symbols": [
            {
                "symbol": "301377.SZ",
                "name": "鼎泰高科",
                "role": "PCB微钻/精密刀具需求基准",
                "keywords": ["鼎泰高科", "PCB钻针", "微钻"],
                "weight": 1.0,
            }
        ],
    },
]


def _now() -> datetime:
    return datetime.now()


def _json_dumps(payload: Any) -> str:
    return json.dumps(payload if payload is not None else {}, ensure_ascii=False)


def _url_hash(board_id: int, url: str) -> str:
    return hashlib.sha256(f"{board_id}:{url}".encode("utf-8")).hexdigest()


def _get_secid(code: str) -> str:
    return f"1.{code}" if code.startswith("6") else f"0.{code}"


def _market_prefix(code: str) -> str:
    return "sh" if infer_exchange(code) == "SH" else "sz"


def _fetch_text(url: str, *, referer: str, timeout: int = 10, encoding: str = "utf-8") -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
            "Referer": referer,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Connection": "close",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode(encoding, errors="ignore")


def _fetch_json(url: str, *, referer: str, timeout: int = 8, attempts: int = 1) -> dict[str, Any]:
    ctx = ssl.create_default_context()
    last_exc: Exception | None = None
    for attempt in range(max(1, attempts)):
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
                "Referer": referer,
                "Accept": "application/json,text/plain,*/*",
                "Connection": "close",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            last_exc = exc
            if attempt < attempts - 1:
                time.sleep(1 + attempt)
    raise RuntimeError(str(last_exc)) from last_exc


def ensure_default_industry_boards() -> list[dict]:
    created = []
    now = _now()
    with quant_db.atomic():
        for board in DEFAULT_INDUSTRY_BOARDS:
            record, _ = QuantIndustryBoard.get_or_create(
                board_key=board["board_key"],
                defaults={
                    "name": board["name"],
                    "description": board["description"],
                    "status": "active",
                    "keywords_json": _json_dumps(board["keywords"]),
                    "created_at": now,
                    "updated_at": now,
                },
            )
            record.name = board["name"]
            record.description = board["description"]
            record.status = "active"
            record.keywords_json = _json_dumps(board["keywords"])
            record.updated_at = now
            record.save()

            for symbol_cfg in board["symbols"]:
                symbol = normalize_symbol(symbol_cfg["symbol"])
                code = normalize_code(symbol)
                exchange = infer_exchange(symbol)
                QuantIndustryWatchSymbol.insert(
                    board_id=record.id,
                    symbol=symbol,
                    code=code,
                    exchange=exchange,
                    name=symbol_cfg["name"],
                    role=symbol_cfg["role"],
                    weight=float(symbol_cfg.get("weight", 1.0) or 1.0),
                    status="active",
                    keywords_json=_json_dumps(symbol_cfg.get("keywords") or []),
                    created_at=now,
                    updated_at=now,
                ).on_conflict(
                    conflict_target=[QuantIndustryWatchSymbol.board_id, QuantIndustryWatchSymbol.symbol],
                    update={
                        QuantIndustryWatchSymbol.name: symbol_cfg["name"],
                        QuantIndustryWatchSymbol.role: symbol_cfg["role"],
                        QuantIndustryWatchSymbol.weight: float(symbol_cfg.get("weight", 1.0) or 1.0),
                        QuantIndustryWatchSymbol.status: "active",
                        QuantIndustryWatchSymbol.keywords_json: _json_dumps(symbol_cfg.get("keywords") or []),
                        QuantIndustryWatchSymbol.updated_at: now,
                    },
                ).execute()
            created.append(record.to_dict())
    return created


def list_industry_boards(status: Optional[str] = None) -> list[dict]:
    ensure_default_industry_boards()
    query = QuantIndustryBoard.select().order_by(QuantIndustryBoard.id.asc())
    if status:
        query = query.where(QuantIndustryBoard.status == status)
    boards = []
    for board in query.iterator():
        payload = board.to_dict()
        symbols = (
            QuantIndustryWatchSymbol.select()
            .where(QuantIndustryWatchSymbol.board_id == board.id)
            .order_by(QuantIndustryWatchSymbol.weight.desc(), QuantIndustryWatchSymbol.id.asc())
        )
        payload["symbols"] = [item.to_dict() for item in symbols.iterator()]
        boards.append(payload)
    return boards


def get_industry_board(board_id: Optional[int] = None, board_key: str = "") -> QuantIndustryBoard:
    ensure_default_industry_boards()
    if board_id:
        return QuantIndustryBoard.get_by_id(board_id)
    key = str(board_key or "").strip()
    if key:
        record = QuantIndustryBoard.get_or_none(QuantIndustryBoard.board_key == key)
        if record:
            return record
    record = QuantIndustryBoard.select().where(QuantIndustryBoard.status == "active").order_by(QuantIndustryBoard.id.asc()).first()
    if not record:
        raise ValueError("没有可用行业板块")
    return record


def create_or_update_industry_board(*, board_key: str, name: str, description: str = "", keywords=None, symbols=None, status: str = "active") -> dict:
    if not str(board_key or "").strip():
        raise ValueError("board_key 不能为空")
    if not str(name or "").strip():
        raise ValueError("name 不能为空")
    keywords = keywords or []
    symbols = symbols or []
    now = _now()
    with quant_db.atomic():
        board, _ = QuantIndustryBoard.get_or_create(
            board_key=str(board_key).strip(),
            defaults={
                "name": str(name).strip(),
                "description": str(description or "").strip(),
                "status": str(status or "active").strip() or "active",
                "keywords_json": _json_dumps(keywords),
                "created_at": now,
                "updated_at": now,
            },
        )
        board.name = str(name).strip()
        board.description = str(description or "").strip()
        board.status = str(status or "active").strip() or "active"
        board.keywords_json = _json_dumps(keywords)
        board.updated_at = now
        board.save()
        for item in symbols:
            symbol = normalize_symbol(item.get("symbol") or item.get("code"))
            code = normalize_code(symbol)
            exchange = infer_exchange(symbol)
            QuantIndustryWatchSymbol.insert(
                board_id=board.id,
                symbol=symbol,
                code=code,
                exchange=exchange,
                name=str(item.get("name") or "").strip(),
                role=str(item.get("role") or "").strip(),
                weight=float(item.get("weight", 1.0) or 1.0),
                status=str(item.get("status", "active") or "active"),
                keywords_json=_json_dumps(item.get("keywords") or []),
                created_at=now,
                updated_at=now,
            ).on_conflict(
                conflict_target=[QuantIndustryWatchSymbol.board_id, QuantIndustryWatchSymbol.symbol],
                update={
                    QuantIndustryWatchSymbol.name: str(item.get("name") or "").strip(),
                    QuantIndustryWatchSymbol.role: str(item.get("role") or "").strip(),
                    QuantIndustryWatchSymbol.weight: float(item.get("weight", 1.0) or 1.0),
                    QuantIndustryWatchSymbol.status: str(item.get("status", "active") or "active"),
                    QuantIndustryWatchSymbol.keywords_json: _json_dumps(item.get("keywords") or []),
                    QuantIndustryWatchSymbol.updated_at: now,
                },
            ).execute()
    return get_industry_board(board_key=board_key).to_dict()


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


def fetch_announcements(code: str, limit: int = 15) -> list[dict[str, Any]]:
    params = {
        "page_size": limit,
        "page_index": 1,
        "sr": -1,
        "stock_list": code,
        "client_source": "web",
        "ann_type": "A",
        "f_node": 0,
        "s_node": 0,
    }
    url = "https://np-anotice-stock.eastmoney.com/api/security/ann?" + urllib.parse.urlencode(params)
    payload = _fetch_json(url, referer=f"https://data.eastmoney.com/notices/stock/{code}.html", timeout=8, attempts=1)
    items = []
    for item in ((payload.get("data") or {}).get("list") or [])[:limit]:
        title = str(item.get("title") or item.get("art_title") or item.get("notice_title") or "").strip()
        if not title:
            continue
        notice_date = str(item.get("notice_date") or item.get("display_time") or item.get("eiTime") or "")[:10]
        art_code = item.get("art_code") or item.get("notice_id") or ""
        ann_url = f"https://data.eastmoney.com/notices/detail/{code}/{art_code}.html" if art_code else f"https://data.eastmoney.com/notices/stock/{code}.html"
        items.append(
            {
                "title": title,
                "url": ann_url,
                "published_at": notice_date or date.today().isoformat(),
                "source": "东方财富公告",
                "domain": "data.eastmoney.com",
                "summary": _classify_event(title),
                "payload": item,
            }
        )
    return items


def fetch_ths_stock_news(code: str, name: str, limit: int = 20) -> list[dict[str, Any]]:
    url = f"https://stockpage.10jqka.com.cn/{code}/news/"
    text = _fetch_text(url, referer="https://stockpage.10jqka.com.cn/", timeout=10)
    pattern = re.compile(
        r'\\"title\\":\\"(?P<title>.*?)\\".*?'
        r'\\"timeLabel\\":\\"(?P<time>.*?)\\".*?'
        r'\\"jumpUrl\\":\\"(?P<url>.*?)\\".*?'
        r'\\"source\\":\\"(?P<source>.*?)\\"',
        re.S,
    )
    rows = []
    for match in pattern.finditer(text):
        if len(rows) >= limit:
            break
        title = _clean_escaped(match.group("title"))
        article_url = _clean_escaped(match.group("url"))
        if not title or not article_url:
            continue
        rows.append(
            {
                "title": title,
                "url": article_url,
                "published_at": _normalize_time_label(_clean_escaped(match.group("time"))),
                "source": _clean_escaped(match.group("source")) or "同花顺",
                "domain": "news.10jqka.com.cn",
                "summary": f"{name}个股资讯",
                "payload": {"code": code, "name": name, "source_page": url},
            }
        )
    return rows


def fetch_research_reports(code: str, limit: int = 10) -> list[dict[str, Any]]:
    end_day = date.today()
    begin_day = end_day - timedelta(days=365)
    params = {
        "pageSize": limit,
        "pageNo": 1,
        "beginTime": begin_day.isoformat(),
        "endTime": end_day.isoformat(),
        "qType": 0,
        "orgCode": "",
        "code": code,
        "rcode": "",
        "p": 1,
        "pageNum": 1,
        "pageNumber": 1,
        "industryCode": "*",
        "industry": "*",
        "rating": "*",
        "ratingChange": "*",
        "fields": "",
    }
    url = "https://reportapi.eastmoney.com/report/list?" + urllib.parse.urlencode(params)
    payload = _fetch_json(url, referer="https://data.eastmoney.com/report/stock.jshtml", timeout=8, attempts=1)
    rows = []
    for item in (payload.get("data") or [])[:limit]:
        title = str(item.get("title") or item.get("titleShort") or "").strip()
        if not title:
            continue
        report_url = str(item.get("url") or item.get("attachUrl") or "").strip()
        if report_url and report_url.startswith("//"):
            report_url = f"https:{report_url}"
        if not report_url:
            info_code = str(item.get("infoCode") or item.get("info_code") or "")
            report_url = f"https://data.eastmoney.com/report/zw_stock.jshtml?infocode={info_code}" if info_code else f"https://data.eastmoney.com/report/{code}.html"
        rows.append(
            {
                "title": title,
                "url": report_url,
                "org_name": str(item.get("orgSName") or item.get("orgName") or ""),
                "analyst": str(item.get("researcher") or item.get("author") or ""),
                "rating": str(item.get("emRatingName") or item.get("rating") or ""),
                "target_price": to_float(item.get("predictNextTwoYearEps") or item.get("targetPrice")),
                "published_at": str(item.get("publishDate") or item.get("datetime") or "")[:10],
                "summary": str(item.get("summary") or item.get("indvInduName") or ""),
                "source": "东方财富研报",
                "payload": item,
            }
        )
    return rows


def collect_industry(board_id: Optional[int] = None, board_key: str = "", targets: Optional[list[str]] = None) -> dict:
    ensure_default_industry_boards()
    targets = targets or ["market", "announcements", "news", "research_reports", "indicators"]
    if board_id or board_key:
        boards = [get_industry_board(board_id=board_id, board_key=board_key)]
    else:
        boards = list(QuantIndustryBoard.select().where(QuantIndustryBoard.status == "active").order_by(QuantIndustryBoard.id.asc()))
    result = {"boards": len(boards), "market_snapshots": 0, "daily_bars": 0, "announcements": 0, "news_items": 0, "research_reports": 0, "indicator_snapshots": 0, "errors": []}
    for board in boards:
        symbols = list(
            QuantIndustryWatchSymbol.select()
            .where((QuantIndustryWatchSymbol.board_id == board.id) & (QuantIndustryWatchSymbol.status == "active"))
            .order_by(QuantIndustryWatchSymbol.weight.desc(), QuantIndustryWatchSymbol.id.asc())
        )
        for watch in symbols:
            if "market" in targets:
                try:
                    counts = collect_market_snapshot(board, watch)
                    result["market_snapshots"] += counts.get("market_snapshots", 0)
                    result["daily_bars"] += counts.get("daily_bars", 0)
                except Exception as exc:
                    result["errors"].append(f"{watch.symbol} market: {exc}")
            if "announcements" in targets:
                try:
                    result["announcements"] += collect_announcements(board, watch)
                except Exception as exc:
                    result["errors"].append(f"{watch.symbol} announcements: {exc}")
            if "news" in targets:
                try:
                    result["news_items"] += collect_news(board, watch)
                except Exception as exc:
                    result["errors"].append(f"{watch.symbol} news: {exc}")
            if "research_reports" in targets:
                try:
                    result["research_reports"] += collect_research_reports(board, watch)
                except Exception as exc:
                    result["errors"].append(f"{watch.symbol} research_reports: {exc}")
        if "indicators" in targets:
            result["indicator_snapshots"] += collect_indicator_snapshots(board)
    return result


def collect_market_snapshot(board: QuantIndustryBoard, watch: QuantIndustryWatchSymbol) -> dict:
    now = _now()
    code = watch.code
    try:
        kline = fetch_latest_kline(code)
    except Exception:
        kline = fetch_sina_snapshot(code)
    try:
        quote = fetch_quote(code)
    except Exception:
        quote = {}
    try:
        flow = fetch_latest_capital_flow(code)
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


def collect_announcements(board: QuantIndustryBoard, watch: QuantIndustryWatchSymbol) -> int:
    rows = fetch_announcements(watch.code)
    return _save_news_like_items(board, watch, rows, keyword="announcement", source_type="announcement")


def collect_news(board: QuantIndustryBoard, watch: QuantIndustryWatchSymbol) -> int:
    rows = fetch_ths_stock_news(watch.code, watch.name)
    return _save_news_like_items(board, watch, rows, keyword="news", source_type="news")


def collect_research_reports(board: QuantIndustryBoard, watch: QuantIndustryWatchSymbol) -> int:
    rows = fetch_research_reports(watch.code)
    now = _now()
    saved = 0
    with quant_db.atomic():
        for row in rows:
            url = str(row.get("url") or "").strip()
            title = str(row.get("title") or "").strip()
            if not url or not title:
                continue
            payload = {
                "board_id": board.id,
                "symbol": watch.symbol,
                "code": watch.code,
                "title": title,
                "url": url,
                "url_hash": _url_hash(board.id, url),
                "org_name": str(row.get("org_name") or ""),
                "analyst": str(row.get("analyst") or ""),
                "rating": str(row.get("rating") or ""),
                "target_price": to_float(row.get("target_price")),
                "published_at": str(row.get("published_at") or ""),
                "summary": str(row.get("summary") or ""),
                "source": str(row.get("source") or ""),
                "payload_json": _json_dumps(row.get("payload") or row),
                "created_at": now,
                "updated_at": now,
            }
            QuantResearchReportItem.insert(payload).on_conflict(
                conflict_target=[QuantResearchReportItem.url_hash],
                update={field: payload[field.name] for field in QuantResearchReportItem._meta.sorted_fields if field.name in payload and field.name != "id"},
            ).execute()
            saved += 1
    return saved


def _save_news_like_items(board: QuantIndustryBoard, watch: QuantIndustryWatchSymbol, rows: list[dict[str, Any]], *, keyword: str, source_type: str) -> int:
    now = _now()
    saved = 0
    with quant_db.atomic():
        for row in rows:
            url = str(row.get("url") or "").strip()
            title = str(row.get("title") or "").strip()
            if not url or not title:
                continue
            payload = {
                "board_id": board.id,
                "symbol": watch.symbol,
                "code": watch.code,
                "keyword": keyword,
                "title": title,
                "url": url,
                "url_hash": _url_hash(board.id, url),
                "source": str(row.get("source") or ""),
                "domain": str(row.get("domain") or ""),
                "published_at": str(row.get("published_at") or ""),
                "summary": str(row.get("summary") or source_type),
                "payload_json": _json_dumps(row.get("payload") or row),
                "created_at": now,
                "updated_at": now,
            }
            QuantIndustryNewsItem.insert(payload).on_conflict(
                conflict_target=[QuantIndustryNewsItem.url_hash],
                update={field: payload[field.name] for field in QuantIndustryNewsItem._meta.sorted_fields if field.name in payload and field.name != "id"},
            ).execute()
            saved += 1
    return saved


def collect_indicator_snapshots(board: QuantIndustryBoard) -> int:
    today = date.today()
    now = _now()
    records = []
    latest_snapshots = (
        QuantMarketSnapshot.select()
        .where(
            (QuantMarketSnapshot.board_id == board.id)
            & (QuantMarketSnapshot.trade_date == QuantMarketSnapshot.select(fn.MAX(QuantMarketSnapshot.trade_date)).where(QuantMarketSnapshot.board_id == board.id))
        )
    )
    for item in latest_snapshots.iterator():
        records.extend(
            [
                _indicator_row(board.id, "stock_close", "收盘价", "market", item.symbol, item.name, item.trade_date, item.close_price, "元", item.source, item.to_dict(), now),
                _indicator_row(board.id, "stock_change_pct", "日涨跌幅", "market", item.symbol, item.name, item.trade_date, item.pct_change, "%", item.source, item.to_dict(), now),
                _indicator_row(board.id, "stock_amount", "成交额", "market", item.symbol, item.name, item.trade_date, (item.amount or 0) / 1e8 if item.amount is not None else None, "亿元", item.source, item.to_dict(), now),
                _indicator_row(board.id, "pe_ttm", "动态PE", "valuation", item.symbol, item.name, item.trade_date, item.pe_ttm, "倍", item.source, item.to_dict(), now),
                _indicator_row(board.id, "pb", "PB", "valuation", item.symbol, item.name, item.trade_date, item.pb, "倍", item.source, item.to_dict(), now),
                _indicator_row(board.id, "main_flow", "主力净流入", "capital_flow", item.symbol, item.name, item.trade_date, (item.main_flow or 0) / 1e8 if item.main_flow is not None else None, "亿元", item.source, item.to_dict(), now),
            ]
        )
    recent_cutoff = (today - timedelta(days=7)).isoformat()
    news_count = QuantIndustryNewsItem.select().where((QuantIndustryNewsItem.board_id == board.id) & (QuantIndustryNewsItem.published_at >= recent_cutoff)).count()
    report_count = QuantResearchReportItem.select().where((QuantResearchReportItem.board_id == board.id) & (QuantResearchReportItem.published_at >= recent_cutoff)).count()
    records.append(_indicator_row(board.id, "news_count_7d", "7日新闻数", "sentiment", board.board_key, board.name, today, news_count, "条", "industry_news", {"board": board.to_dict()}, now))
    records.append(_indicator_row(board.id, "research_report_count_7d", "7日研报数", "research", board.board_key, board.name, today, report_count, "篇", "research_reports", {"board": board.to_dict()}, now))
    if not records:
        return 0
    with quant_db.atomic():
        for row in records:
            QuantIndustryIndicatorSnapshot.insert(row).on_conflict(
                conflict_target=[
                    QuantIndustryIndicatorSnapshot.board_id,
                    QuantIndustryIndicatorSnapshot.indicator_key,
                    QuantIndustryIndicatorSnapshot.subject_code,
                    QuantIndustryIndicatorSnapshot.observed_date,
                ],
                update={field: row[field.name] for field in QuantIndustryIndicatorSnapshot._meta.sorted_fields if field.name in row and field.name != "id"},
            ).execute()
    return len(records)


def get_industry_dashboard(board_id: Optional[int] = None, board_key: str = "", days: int = 90) -> dict:
    board = get_industry_board(board_id=board_id, board_key=board_key)
    symbols = [
        item.to_dict()
        for item in (
            QuantIndustryWatchSymbol.select()
            .where(QuantIndustryWatchSymbol.board_id == board.id)
            .order_by(QuantIndustryWatchSymbol.weight.desc(), QuantIndustryWatchSymbol.id.asc())
        ).iterator()
    ]
    latest_trade_date = QuantMarketSnapshot.select(fn.MAX(QuantMarketSnapshot.trade_date)).where(QuantMarketSnapshot.board_id == board.id).scalar()
    cards = [
        item.to_dict()
        for item in (
            QuantMarketSnapshot.select()
            .where(
                (QuantMarketSnapshot.board_id == board.id)
                & (QuantMarketSnapshot.trade_date == latest_trade_date)
            )
            .order_by(QuantMarketSnapshot.symbol.asc())
        ).iterator()
    ]
    series = {}
    for symbol in symbols:
        rows = (
            QuantMarketSnapshot.select()
            .where((QuantMarketSnapshot.board_id == board.id) & (QuantMarketSnapshot.symbol == symbol["symbol"]))
            .order_by(QuantMarketSnapshot.trade_date.desc())
            .limit(max(10, min(int(days or 90), 240)))
        )
        series[symbol["symbol"]] = list(reversed([item.to_dict() for item in rows.iterator()]))
    indicators = [
        item.to_dict()
        for item in (
            QuantIndustryIndicatorSnapshot.select()
            .where(QuantIndustryIndicatorSnapshot.board_id == board.id)
            .order_by(QuantIndustryIndicatorSnapshot.observed_date.desc(), QuantIndustryIndicatorSnapshot.indicator_group.asc(), QuantIndustryIndicatorSnapshot.indicator_key.asc())
            .limit(120)
        ).iterator()
    ]
    news = list_industry_news(board_id=board.id, limit=30)
    reports = list_research_reports(board_id=board.id, limit=30)
    return {
        "board": board.to_dict(),
        "boards": list_industry_boards(status="active"),
        "symbols": symbols,
        "latest_trade_date": latest_trade_date.isoformat() if latest_trade_date else None,
        "latest_cards": cards,
        "series": series,
        "indicators": indicators,
        "news": news,
        "research_reports": reports,
    }


def list_industry_news(board_id: Optional[int] = None, symbol: str = "", limit: int = 100) -> list[dict]:
    query = QuantIndustryNewsItem.select().order_by(QuantIndustryNewsItem.published_at.desc(), QuantIndustryNewsItem.id.desc())
    if board_id:
        query = query.where(QuantIndustryNewsItem.board_id == board_id)
    if symbol:
        query = query.where(QuantIndustryNewsItem.symbol == normalize_symbol(symbol))
    return [item.to_dict() for item in query.limit(max(1, min(limit, 300))).iterator()]


def list_research_reports(board_id: Optional[int] = None, symbol: str = "", limit: int = 100) -> list[dict]:
    query = QuantResearchReportItem.select().order_by(QuantResearchReportItem.published_at.desc(), QuantResearchReportItem.id.desc())
    if board_id:
        query = query.where(QuantResearchReportItem.board_id == board_id)
    if symbol:
        query = query.where(QuantResearchReportItem.symbol == normalize_symbol(symbol))
    return [item.to_dict() for item in query.limit(max(1, min(limit, 300))).iterator()]


def render_industry_daily_markdown(board_id: Optional[int] = None, board_key: str = "") -> str:
    dashboard = get_industry_dashboard(board_id=board_id, board_key=board_key)
    board = dashboard["board"]
    cards = dashboard["latest_cards"]
    indicators = dashboard["indicators"]
    news = dashboard["news"][:8]
    reports = dashboard["research_reports"][:6]
    lines = [
        f"# {board['name']} 行业跟踪日报",
        "",
        f"- 最新交易日: `{dashboard.get('latest_trade_date') or '-'}`",
        f"- 标的数: `{len(dashboard.get('symbols') or [])}`",
        "",
        "## 核心标的",
    ]
    if not cards:
        lines.append("- 暂无行情快照。")
    for item in cards:
        amount = None if item.get("amount") is None else round(float(item["amount"]) / 1e8, 2)
        main_flow = None if item.get("main_flow") is None else round(float(item["main_flow"]) / 1e8, 2)
        lines.append(
            f"- {item['name']} `{item['symbol']}` 收盘 `{item.get('close_price')}`，涨跌幅 `{_fmt(item.get('pct_change'))}%`，成交额 `{amount}` 亿，PE `{_fmt(item.get('pe_ttm'))}`，PB `{_fmt(item.get('pb'))}`，主力 `{main_flow}` 亿。"
        )
    lines.extend(["", "## 行业指标"])
    for item in indicators[:10]:
        lines.append(f"- {item['indicator_name']} / {item.get('subject_name') or item.get('subject_code')}: `{_fmt(item.get('value'))}{item.get('unit') or ''}`")
    lines.extend(["", "## 重点新闻与公告"])
    if not news:
        lines.append("- 暂无新闻/公告。")
    for item in news:
        lines.append(f"- [{item['title']}]({item['url']}) · {item.get('source') or '-'} · {item.get('published_at') or '-'}")
    lines.extend(["", "## 研报"])
    if not reports:
        lines.append("- 暂无研报元数据。")
    for item in reports:
        org = item.get("org_name") or "-"
        rating = item.get("rating") or "-"
        lines.append(f"- [{item['title']}]({item['url']}) · {org} · {rating} · {item.get('published_at') or '-'}")
    lines.extend(
        [
            "",
            "## 验证与证伪",
            "- 继续跟踪价格/成交额是否与资金流、公告和研报变化互相确认。",
            "- 若新闻热度上升但成交额、资金流和后续公告不配合，主题交易需要降权。",
            "- 若估值继续扩张但利润、现金流或订单证据无法跟上，当前行业逻辑被削弱。",
        ]
    )
    return "\n".join(lines)


def _indicator_row(board_id, key, name, group, subject_code, subject_name, observed_date, value, unit, source, payload, now):
    return {
        "board_id": board_id,
        "indicator_key": key,
        "indicator_name": name,
        "indicator_group": group,
        "subject_code": str(subject_code or ""),
        "subject_name": str(subject_name or ""),
        "observed_date": observed_date,
        "value": float(value) if value is not None else None,
        "unit": unit,
        "source": source,
        "payload_json": _json_dumps(payload),
        "created_at": now,
        "updated_at": now,
    }


def _scaled(value: Any, factor: float) -> Optional[float]:
    number = to_float(value)
    if number is None:
        return None
    return number / factor


def _clean_escaped(value: str) -> str:
    return html.unescape(value.replace(r"\/", "/").replace(r"\\", "\\").replace(r"\"", '"')).strip()


def _normalize_time_label(label: str) -> str:
    today = date.today()
    text = str(label or "").strip()
    if not text:
        return ""
    if "小时前" in text or "分钟前" in text:
        return today.isoformat()
    if text.startswith("昨天"):
        return (today - timedelta(days=1)).isoformat()
    match = re.match(r"(?P<month>\d{1,2})-(?P<day>\d{1,2})", text)
    if match:
        month = int(match.group("month"))
        day = int(match.group("day"))
        candidate = date(today.year, month, day)
        if candidate > today + timedelta(days=7):
            candidate = date(today.year - 1, month, day)
        return candidate.isoformat()
    return text


def _classify_event(title: str) -> str:
    rules = [
        (("业绩预告", "业绩快报", "年报", "半年报", "一季报", "三季报"), "业绩披露"),
        (("定增", "可转债", "募资", "重组", "并购", "H股"), "融资/并购"),
        (("中标", "合同", "订单", "扩产", "投资建设"), "经营/项目"),
        (("处罚", "立案", "诉讼", "仲裁", "风险提示", "异常波动"), "风险事项"),
        (("回购", "增持", "减持", "分红", "利润分配"), "股东回报/股东行为"),
    ]
    for keywords, label in rules:
        if any(keyword in title for keyword in keywords):
            return label
    return "公告事件"


def _fmt(value) -> str:
    if value is None:
        return "-"
    try:
        return str(round(float(value), 2))
    except Exception:
        return str(value)
