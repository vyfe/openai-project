from __future__ import annotations

from datetime import date, datetime


def normalize_code(raw_symbol: str) -> str:
    symbol = str(raw_symbol or "").strip().lower()
    if not symbol:
        raise ValueError("symbol 不能为空")
    if "." in symbol:
        left, right = symbol.split(".", 1)
        if left in ("sh", "sz", "bj"):
            return right
        if right in ("sh", "sz", "bj"):
            return left
    if symbol.endswith(".sh") or symbol.endswith(".sz") or symbol.endswith(".bj"):
        return symbol[:-3]
    return symbol


def infer_exchange(raw_symbol: str) -> str:
    symbol = normalize_code(raw_symbol)
    if symbol.startswith(("6", "5", "9")):
        return "SH"
    if symbol.startswith(("0", "2", "3")):
        return "SZ"
    if symbol.startswith(("4", "8")):
        return "BJ"
    raise ValueError(f"无法根据 symbol 推断交易所: {raw_symbol}")


def normalize_symbol(raw_symbol: str) -> str:
    code = normalize_code(raw_symbol)
    exchange = infer_exchange(code)
    return f"{code}.{exchange}"


def to_baostock_symbol(raw_symbol: str) -> str:
    code = normalize_code(raw_symbol)
    exchange = infer_exchange(code).lower()
    return f"{exchange}.{code}"


def parse_trade_date(value) -> date:
    if isinstance(value, date):
        return value
    text = str(value or "").strip()
    if not text:
        raise ValueError("trade_date 不能为空")
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"无法解析 trade_date: {value}")


def compact_date_text(value) -> str:
    return parse_trade_date(value).strftime("%Y%m%d")


def to_float(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text or text.lower() in ("nan", "none", "null"):
        return None
    try:
        return float(text.replace(",", ""))
    except ValueError:
        return None

