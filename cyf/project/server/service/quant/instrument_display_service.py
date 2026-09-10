"""量化标的"显示名"解析（custom_name 优先，回退 name）。

供报告渲染 / dashboard / 前端列表 / 搜索统一使用，避免到处复制
"先 custom_name 再 name"的逻辑。custom_name 是数据中心用户维护的全局别名。
"""
from __future__ import annotations

from datetime import datetime
from typing import Iterable

from quant.entities import QuantInstrument


def resolve_display_name(symbol: str, custom_name: str | None, name: str) -> str:
    """单条解析：custom_name 非空则用，否则 name。空串也算"未设置"。"""
    cn = (custom_name or "").strip()
    if cn:
        return cn
    return name or ""


def bulk_lookup_display_names(symbols: Iterable[str]) -> dict[str, str]:
    """批量：symbol → 显示名（custom_name 优先，回退 name）。空串表示无任何名字。

    与 report_generation_service._bulk_lookup_instrument_names 完全等价的语义，
    但额外把 custom_name 纳入优先级；report / dashboard 两边后续统一调这里。
    """
    cleaned = sorted({s for s in (symbols or []) if s})
    if not cleaned:
        return {}
    rows = QuantInstrument.select(
        QuantInstrument.symbol,
        QuantInstrument.name,
        QuantInstrument.custom_name,
    ).where(QuantInstrument.symbol.in_(cleaned))
    return {
        row.symbol: resolve_display_name(row.symbol, row.custom_name, row.name or "")
        for row in rows
    }


def bulk_lookup_instrument_records(symbols: Iterable[str]) -> dict[str, dict]:
    """批量：symbol → {name, custom_name, display_name} 三件套。

    用于需要同时读取原名 / 自定义名 / 显示名的位置（dashboard 的 _attach_names、
    report 的 _build_top_signals 等），避免各处重复 select + 各自构造 dict。
    缺失的 symbol 不出现在结果 dict 里；调用方用 .get(symbol, {...默认空...}) 容错。
    """
    cleaned = sorted({s for s in (symbols or []) if s})
    if not cleaned:
        return {}
    rows = QuantInstrument.select(
        QuantInstrument.symbol,
        QuantInstrument.name,
        QuantInstrument.custom_name,
    ).where(QuantInstrument.symbol.in_(cleaned))
    out: dict[str, dict] = {}
    for row in rows:
        name = row.name or ""
        custom_name = row.custom_name or ""
        out[row.symbol] = {
            "name": name,
            "custom_name": custom_name,
            "display_name": resolve_display_name(row.symbol, custom_name, name),
        }
    return out


def list_instruments_with_display_name(
    *,
    keyword: str = "",
    exchange: str = "",
    only_with_custom: bool = False,
    limit: int = 200,
) -> list[dict]:
    """列出 quant_instrument（带显示名），用于前端"数据中心股票池"管理 UI。

    - keyword：模糊匹配 symbol / code / name / custom_name
    - exchange：可选过滤 SH / SZ / BJ
    - only_with_custom=True：只列出 custom_name 非空的（数据中心"自定义名管理"视图）
    """
    query = QuantInstrument.select().order_by(QuantInstrument.symbol.asc())
    if exchange:
        query = query.where(QuantInstrument.exchange == exchange)
    if only_with_custom:
        query = query.where(QuantInstrument.custom_name.is_null(False))
    if keyword:
        like = f"%{keyword.strip()}%"
        query = query.where(
            (QuantInstrument.symbol ** like)
            | (QuantInstrument.code ** like)
            | (QuantInstrument.name ** like)
            | (QuantInstrument.custom_name ** like)
        )
    items: list[dict] = []
    for row in query.limit(limit):
        items.append({
            "symbol": row.symbol,
            "code": row.code,
            "exchange": row.exchange,
            "market": row.market,
            "name": row.name or "",
            "custom_name": row.custom_name or "",
            "display_name": resolve_display_name(row.symbol, row.custom_name, row.name or ""),
            "status": row.status,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        })
    return items


def set_custom_name(symbol: str, custom_name: str | None) -> dict:
    """给单个 symbol 写 custom_name。

    custom_name 为 None / 空字符串 → 清空（回退到 name）。
    返回最新 record 的 to_dict。symbol 不存在抛 ValueError。
    """
    try:
        record = QuantInstrument.get(QuantInstrument.symbol == symbol)
    except QuantInstrument.DoesNotExist:
        raise ValueError(f"标的 {symbol} 不存在 quant_instrument 表中，无法设置自定义名")
    new_value = (custom_name or "").strip() or None
    record.custom_name = new_value
    # peewee DateTimeField(default=datetime.now) 只在 INSERT 时触发，UPDATE 需显式写
    record.updated_at = datetime.now()
    record.save()
    return {
        "symbol": record.symbol,
        "name": record.name or "",
        "custom_name": record.custom_name or "",
        "display_name": resolve_display_name(record.symbol, record.custom_name, record.name or ""),
        "updated_at": record.updated_at.isoformat() if record.updated_at else None,
    }


def clear_custom_name(symbol: str) -> dict:
    """清空单个 symbol 的 custom_name（等价于 set_custom_name(symbol, None)）。"""
    return set_custom_name(symbol, None)