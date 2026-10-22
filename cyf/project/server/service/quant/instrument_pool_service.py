"""股票池维护 — 前端「数据中心」与飞书「加入」指令共用。

对外两个入口：
- ``upsert_instrument``：单只写入（幂等，on_conflict 更新）
- ``add_instruments_by_keywords``：按代码/中文名批量加入，模糊匹配有歧义时
  明确回候选让用户二次确认，而不是静默挑一只
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from service.quant.common import infer_exchange, normalize_code, normalize_symbol

# 模糊匹配返回的候选上限：超过这个数用户基本无法肉眼挑选，直接判歧义
MAX_CANDIDATES_HINT = 6


def upsert_instrument(
    symbol: str,
    *,
    name: str = "",
    source: str = "manual",
    exchange: str = "",
) -> dict:
    """写入/更新一只标的到股票池。symbol 已存在时更新名称与状态（恢复软删）。"""
    from quant.entities import QuantInstrument
    from service.quant.instrument_display_service import resolve_display_name

    normalized_symbol = normalize_symbol(symbol)
    normalized_code = normalize_code(normalized_symbol)
    normalized_exchange = str(exchange or "").strip().upper() or infer_exchange(normalized_symbol)
    now = datetime.now()
    payload = {
        "symbol": normalized_symbol,
        "code": normalized_code,
        "exchange": normalized_exchange,
        "market": "A_SHARE",
        "name": str(name or "").strip(),
        "source": str(source or "manual").strip() or "manual",
        "status": "active",
        "created_at": now,
        "updated_at": now,
    }
    QuantInstrument.insert(payload).on_conflict(
        conflict_target=[QuantInstrument.symbol],
        update={
            QuantInstrument.code: normalized_code,
            QuantInstrument.exchange: normalized_exchange,
            QuantInstrument.market: "A_SHARE",
            QuantInstrument.name: payload["name"],
            QuantInstrument.source: payload["source"],
            QuantInstrument.status: "active",
            QuantInstrument.updated_at: now,
        },
    ).execute()
    saved = QuantInstrument.get(QuantInstrument.symbol == normalized_symbol)
    return {
        "symbol": saved.symbol,
        "code": saved.code,
        "exchange": saved.exchange,
        "market": saved.market,
        "name": saved.name or "",
        "custom_name": saved.custom_name or "",
        "display_name": resolve_display_name(saved.symbol, saved.custom_name or "", saved.name or ""),
        "source": saved.source or "",
        "status": saved.status,
    }


def _find_existing_in_pool(keyword: str) -> Optional[dict]:
    """在本地股票池里精确匹配 code / symbol / name / custom_name。"""
    from quant.entities import QuantInstrument

    raw = str(keyword or "").strip()
    if not raw:
        return None
    candidates = [raw]
    if "." not in raw and raw.isdigit() and len(raw) == 6:
        # 6 位裸代码补全后缀，覆盖 000300/000688 这类实际在上交所的指数
        try:
            candidates.append(normalize_symbol(raw))
        except ValueError:
            pass
    record = QuantInstrument.select().where(
        (QuantInstrument.symbol.in_(candidates))
        | (QuantInstrument.code.in_(candidates))
        | (QuantInstrument.name == raw)
        | (QuantInstrument.custom_name == raw)
    ).first()
    if not record:
        return None
    return {
        "symbol": record.symbol,
        "code": record.code,
        "name": record.name or record.custom_name or record.symbol,
    }


def _resolve_keyword_to_instrument(keyword: str) -> tuple[Optional[dict], Optional[str], list[dict]]:
    """把用户输入解析成唯一标的。

    返回 (instrument, error, candidates)：
    - instrument 非 None → 命中，dict 内 ``in_pool`` 标记是否本来就在池中
    - error 非 None → 失败原因（歧义/未找到/不支持）
    - candidates 非空 → 歧义时的候选列表，供提示用户二次指定
    """
    from service.quant.symbol_search_service import search_symbols_fallback

    raw = str(keyword or "").strip()
    if not raw:
        return None, "关键词为空", []

    existing = _find_existing_in_pool(raw)
    if existing:
        return {**existing, "in_pool": True}, None, []

    try:
        matches = search_symbols_fallback(raw, limit=MAX_CANDIDATES_HINT + 1)
    except Exception as exc:
        return None, f"股票搜索服务不可用（{exc}），请稍后重试或改用 6 位代码", []

    if not matches:
        return None, "未搜索到匹配的 A 股标的，请确认代码或名称是否正确", []

    # 二次精确过滤：东财 suggest 是模糊召回，拼音缩写会带回一堆无关标的
    exact = [
        item for item in matches
        if raw in (item.get("code"), item.get("symbol"), item.get("name"), item.get("custom_name"))
    ]
    if len(exact) == 1:
        return {
            "symbol": item_symbol(exact[0]),
            "code": str(exact[0].get("code") or "").strip(),
            "name": str(exact[0].get("name") or "").strip(),
            "in_pool": False,
        }, None, []

    if len(exact) > 1:
        return None, "匹配到多只同名标的，请用 6 位代码指定", [_brief(m) for m in exact[:MAX_CANDIDATES_HINT]]

    top = matches[:MAX_CANDIDATES_HINT]
    if len(top) == 1:
        return {
            "symbol": item_symbol(top[0]),
            "code": str(top[0].get("code") or "").strip(),
            "name": str(top[0].get("name") or "").strip(),
            "in_pool": False,
        }, None, []

    return None, "匹配到多只标的，请用 6 位代码或完整名称指定", [_brief(m) for m in top]


def item_symbol(item: dict) -> str:
    symbol = str(item.get("symbol") or "").strip()
    if symbol and "." in symbol:
        return symbol
    code = str(item.get("code") or "").strip()
    market = str(item.get("market") or item.get("exchange") or "").strip().upper()
    if code and market:
        return f"{code}.{market}"
    return symbol or code


def _brief(item: dict) -> str:
    name = str(item.get("name") or "").strip()
    code = str(item.get("code") or "").strip()
    return f"{code} {name}".strip()


def add_instruments_by_keywords(keywords: list[str], *, source: str = "manual") -> dict:
    """按关键词批量加入股票池。

    返回 {"added": [...], "existing": [...], "failed": [...]}：
    - added：本次新建的标的
    - existing：已在池中（幂等，不重复写）
    - failed：{keyword, reason, candidates}
    """
    added: list[dict] = []
    existing: list[dict] = []
    failed: list[dict] = []
    seen: set[str] = set()

    for keyword in keywords or []:
        raw = str(keyword or "").strip()
        if not raw:
            continue
        instrument, error, candidates = _resolve_keyword_to_instrument(raw)
        if error or not instrument:
            failed.append({"keyword": raw, "reason": error or "解析失败", "candidates": candidates})
            continue
        symbol = instrument["symbol"]
        if symbol in seen:
            continue
        seen.add(symbol)

        saved = upsert_instrument(symbol, name=instrument.get("name", ""), source=source)
        if instrument.get("in_pool"):
            existing.append(saved)
        else:
            added.append(saved)

    return {"added": added, "existing": existing, "failed": failed}
