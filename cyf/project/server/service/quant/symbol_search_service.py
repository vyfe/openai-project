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

# 接受东财返回的 SecurityTypeName（白名单）。覆盖：
# - 沪A / 深A / 京A：主板 A 股
# - 科创板：上交所科创板（688xxx）
# - 指数：沪深主要指数（000001.SH / 000300.SH / 399001.SZ / 399006.SZ / 000688.SH 等）
ACCEPTED_SECURITY_TYPES = {"沪A", "深A", "京A", "科创板", "指数"}


def search_symbols(
    keyword: str,
    limit: int = 20,
    suggest_type: str = SUGGEST_TYPE_A_SHARE,
    timeout: int = 10,
) -> list[dict]:
    """模糊搜索 A 股股票（含科创板与主要指数）。

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

        sec_type = str(item.get("SecurityTypeName", "")).strip()
        if sec_type not in ACCEPTED_SECURITY_TYPES:
            continue

        # 优先用东财的 MarketType 字段（指数/科创板等"code 前缀 ≠ 实际交易所"的标的必须依赖这个字段）
        market = _infer_market(code, item.get("MarketType", ""))
        symbol = _to_symbol(code, market)

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


def _infer_market(code: str, market_type: str = "") -> str:
    """推断交易所。优先使用东财 MarketType 字段（避免把 000300/000001/000688
    这类"code 以 0 开头但实际属于上交所"的指数/科创板归错）。

    东财 MarketType:
      "1"   → 上交所 (SH)
      "2"   → 深交所 (SZ)
      "_TB" → 新三板/北交所 (BJ)
      "5"   → 港股
      "_KRX" → 韩股等
    """
    if market_type == "1":
        return "SH"
    if market_type == "2":
        return "SZ"
    if market_type == "_TB":
        return "BJ"
    # 没有 MarketType 时按 code 前缀兜底
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
    """带本地 fallback 的搜索（当东财不可达时使用 quant_instrument 表查询）。

    两条路径都会在结果里补上 custom_name + display_name（custom_name 优先，回退 name），
    供前端"策略池"el-select 展示用。
    """
    try:
        remote = search_symbols(keyword, limit=limit)
    except Exception:
        # Fallback: 从本地 quant_instrument 表模糊匹配
        return _local_search(keyword, limit)
    return _attach_custom_name(remote)


def _attach_custom_name(items: list[dict]) -> list[dict]:
    """对远端搜索结果批量补 custom_name + display_name（基于 quant_instrument 表反查）。

    单次 select + dedup，避免逐条 .get() 触发 N 次 IO。
    """
    if not items:
        return items
    from quant.entities import QuantInstrument
    from service.quant.instrument_display_service import resolve_display_name
    symbols = [str(it.get("symbol") or "").strip() for it in items if it.get("symbol")]
    if not symbols:
        return items
    rows = QuantInstrument.select(
        QuantInstrument.symbol,
        QuantInstrument.name,
        QuantInstrument.custom_name,
    ).where(QuantInstrument.symbol.in_(list(set(symbols))))
    lookup = {r.symbol: r for r in rows.iterator()}
    for it in items:
        symbol = str(it.get("symbol") or "").strip()
        if not symbol:
            continue
        row = lookup.get(symbol)
        if row is None:
            # 远端有，quant_instrument 没注册过 → custom_name 视为空
            it["custom_name"] = ""
            it["display_name"] = it.get("name") or ""
            continue
        custom_name = row.custom_name or ""
        original_name = it.get("name") or row.name or ""
        it["custom_name"] = custom_name
        it["display_name"] = resolve_display_name(symbol, custom_name, original_name)
    return items


def _local_search(keyword: str, limit: int = 20) -> list[dict]:
    from quant.entities import QuantInstrument
    from service.quant.instrument_display_service import resolve_display_name

    keyword_lower = keyword.lower().strip()
    if not keyword_lower:
        return []

    query = QuantInstrument.select().where(
        (QuantInstrument.code.contains(keyword_lower))
        | (QuantInstrument.name.contains(keyword_lower))
        | (QuantInstrument.custom_name.contains(keyword_lower))
    ).limit(limit)

    results = []
    for item in query.iterator():
        name = item.name or ""
        custom_name = item.custom_name or ""
        results.append(
            {
                "code": item.code,
                "name": name,
                "custom_name": custom_name,
                # display_name 优先 custom_name，空时回退到 name。
                # 策略池下拉展示用 display_name，与报告渲染逻辑保持一致。
                "display_name": resolve_display_name(item.symbol, custom_name, name),
                "market": item.exchange,
                "symbol": item.symbol,
                "type": "",
                "exchange": item.exchange,
            }
        )
    return results
