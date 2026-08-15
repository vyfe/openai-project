from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any, Optional

from peewee import fn

from quant.db import quant_db
from quant.entities import QuantIndustryBoard, QuantIndustryWatchSymbol
from service.quant.common import infer_exchange, normalize_code, normalize_symbol, parse_trade_date, to_float
from service.quant.industry_common import _json_dumps, _now, _url_hash
from service.quant.industry_indicator_service import collect_indicator_snapshots
from service.quant.industry_news_service import collect_announcements, collect_news, collect_research_reports
from service.quant.industry_quote_service import collect_market_snapshot

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
