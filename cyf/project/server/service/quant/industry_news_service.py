from __future__ import annotations

import html
import json
import re
from datetime import datetime
from typing import Any, Optional

from quant.db import quant_db
from quant.entities import QuantIndustryBoard, QuantIndustryNewsItem, QuantIndustryWatchSymbol, QuantResearchReportItem
from service.quant.common import to_float
from service.quant.industry_common import _fetch_json, _fetch_text, _json_dumps, _now, _url_hash


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

def collect_announcements(board: QuantIndustryBoard, watch: QuantIndustryWatchSymbol) -> int:
    from service.quant import industry_service
    rows = industry_service.fetch_announcements(watch.code)
    return _save_news_like_items(board, watch, rows, keyword="announcement", source_type="announcement")

def collect_news(board: QuantIndustryBoard, watch: QuantIndustryWatchSymbol) -> int:
    from service.quant import industry_service
    rows = industry_service.fetch_ths_stock_news(watch.code, watch.name)
    return _save_news_like_items(board, watch, rows, keyword="news", source_type="news")

def collect_research_reports(board: QuantIndustryBoard, watch: QuantIndustryWatchSymbol) -> int:
    from service.quant import industry_service
    rows = industry_service.fetch_research_reports(watch.code)
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

def _clean_escaped(value: str) -> str:
    return html.unescape(value.replace(r"\/", "/").replace(r"\\", "\\").replace(r"\"", '"')).strip()
