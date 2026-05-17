"""A 股股票模糊搜索 — 基于东方财富 Suggest API。

支持按股票名称、代码、拼音首字母模糊匹配，返回代码/名称/市场/类型。
用于前端持仓录入、策略配置等需要股票代码提示的场景。
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Optional


EASTMONEY_SUGGEST_URL = "https://searchapi.eastmoney.com/api/suggest/get"
EASTMONEY_SUGGEST_TOKEN = "D43BF722C8E33BDC906FB84D85E326E8"
SUGGEST_TYPE_A_SHARE = "14"  # A 股


def search_symbols(
    keyword: str,
    limit: int = 20,
    suggest_type: str = SUGGEST_TYPE_A_SHARE,
    timeout: int = 10,
) -> list[dict]:
    """模糊搜索 A 股股票。

    Args:
        keyword: 搜索关键词（名称/代码/拼音）
        limit: 最大返回条数
        suggest_type: 证券类型，"14"=A股
        timeout: 请求超时秒数

    Returns:
        [{"code": "600519", "name": "贵州茅台", "market": "SH", "type": "沪A"}, ...]
    """
    keyword = str(keyword or "").strip()
    if not keyword:
        return []

    params = {
        "input": keyword,
        "type": suggest_type,
        "token": EASTMONEY_SUGGEST_TOKEN,
        "count": str(max(1, min(limit, 50))),
    }
    url = f"{EASTMONEY_SUGGEST_URL}?{urllib.parse.urlencode(params)}"

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
            "Referer": "https://www.eastmoney.com/",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        raise RuntimeError(f"股票搜索请求失败: {exc}") from exc

    data = payload.get("QuotationCodeTable", {}).get("Data") or []
    results = []
    for item in data:
        code = str(item.get("Code", "")).strip()
        name = str(item.get("Name", "")).strip()
        if not code or not name:
            continue

        # 推断交易所
        market = _infer_market(code)
        # 统一代码格式
        symbol = _to_symbol(code, market)

        sec_type = str(item.get("SecurityTypeName", "")).strip()
        # 仅保留 A 股结果
        if sec_type not in ("沪A", "深A", "京A"):
            continue

        results.append(
            {
                "code": code,
                "name": name,
                "market": market,
                "symbol": symbol,
                "type": sec_type,
                "exchange": market,
            }
        )

    return results


def _infer_market(code: str) -> str:
    if code.startswith(("6", "5", "9")):
        return "SH"
    if code.startswith(("0", "2", "3")):
        return "SZ"
    if code.startswith(("4", "8")):
        return "BJ"
    return ""


def _to_symbol(code: str, market: str) -> str:
    if not market:
        return code
    return f"{code}.{market}"


def search_symbols_fallback(keyword: str, limit: int = 20) -> list[dict]:
    """带本地 fallback 的搜索（当东财不可达时使用 quant_instrument 表查询）"""
    try:
        return search_symbols(keyword, limit=limit)
    except Exception:
        # Fallback: 从本地 quant_instrument 表模糊匹配
        return _local_search(keyword, limit)


def _local_search(keyword: str, limit: int = 20) -> list[dict]:
    from quant.entities import QuantInstrument

    keyword_lower = keyword.lower().strip()
    if not keyword_lower:
        return []

    query = QuantInstrument.select().where(
        (QuantInstrument.code.contains(keyword_lower)) | (QuantInstrument.name.contains(keyword_lower))
    ).limit(limit)

    results = []
    for item in query.iterator():
        results.append(
            {
                "code": item.code,
                "name": item.name or "",
                "market": item.exchange,
                "symbol": item.symbol,
                "type": "",
                "exchange": item.exchange,
            }
        )
    return results
