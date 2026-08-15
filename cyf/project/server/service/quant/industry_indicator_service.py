from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from typing import Any, Optional

from peewee import fn

from quant.db import quant_db
from quant.entities import (
    QuantDailyIndicator,
    QuantIndustryBoard,
    QuantIndustryIndicatorSnapshot,
    QuantIndustryNewsItem,
    QuantIndustryWatchSymbol,
    QuantMarketSnapshot,
    QuantResearchReportItem,
)
from service.quant.common import normalize_symbol, to_float
from service.quant.industry_common import _fetch_text, _json_dumps, _now


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
    from service.quant.industry_board_service import ensure_default_industry_boards
    ensure_default_industry_boards()
    query = QuantIndustryBoard.select()
    if board_id is not None:
        query = query.where(QuantIndustryBoard.id == board_id)
    elif board_key:
        query = query.where(QuantIndustryBoard.board_key == board_key)
    else:
        query = query.order_by(QuantIndustryBoard.id.asc()).limit(1)
    board = query.order_by(QuantIndustryBoard.id.asc()).first()
    if not board:
        return {"board": None, "symbols": [], "latest_trade_date": None, "latest_cards": [], "series": {}, "indicators": [], "news": [], "research_reports": [], "boards": []}
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
        "boards": [b.to_dict() for b in QuantIndustryBoard.select().where(QuantIndustryBoard.status == "active").order_by(QuantIndustryBoard.id.asc()).iterator()],
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

def _fmt(value) -> str:
    if value is None:
        return "-"
    try:
        return str(round(float(value), 2))
    except Exception:
        return str(value)
