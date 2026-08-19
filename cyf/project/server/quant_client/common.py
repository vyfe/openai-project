from __future__ import annotations

from datetime import date, datetime
from typing import NamedTuple, Optional


class MarketInfo(NamedTuple):
    """统一表达一个 A 股标的的市场信息，供 provider 拼 URL/字段名使用。

    - code: 纯数字 code，如 "000300"
    - exchange: 大写交易所，"SH" / "SZ" / "BJ"
    - market_prefix: 小写前缀，用于拼接 URL：
        baostock → `f"{market_prefix}.{code}"`  e.g. `sh.000300`
        腾讯 / 新浪 → `f"{market_prefix}{code}"`  e.g. `sh000300`
    """
    code: str
    exchange: str
    market_prefix: str


def resolve_market_info(raw_symbol: str) -> MarketInfo:
    """从用户输入的 raw_symbol 解析出 (code, exchange, market_prefix)。

    优先信任用户给的 suffix（避免 `000300.SH` 被错误归类为 SZ），没给时才按 code 前缀推断。
    统一 baostock / 腾讯 / 新浪三个 provider 的解析路径。
    """
    code = normalize_code(raw_symbol)
    exchange = extract_user_exchange(raw_symbol) or infer_exchange(code)
    market_prefix = exchange.lower() if exchange else ""
    return MarketInfo(code=code, exchange=exchange, market_prefix=market_prefix)


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


def extract_user_exchange(raw_symbol: str) -> Optional[str]:
    """从 "code.SUFFIX" / "SUFFIX.code" / "code.sh" 形式中提取用户显式给的 exchange；大小写不敏感。"""
    text = str(raw_symbol or "").strip().lower()
    if not text:
        return None
    if "." in text:
        left, right = text.split(".", 1)
        if left in ("sh", "sz", "bj"):
            return left.upper()
        if right in ("sh", "sz", "bj"):
            return right.upper()
    return None


def normalize_symbol(raw_symbol: str) -> str:
    code = normalize_code(raw_symbol)
    user_exchange = extract_user_exchange(raw_symbol)
    if user_exchange:
        return f"{code}.{user_exchange}"
    exchange = infer_exchange(code)
    return f"{code}.{exchange}"


def to_baostock_symbol(raw_symbol: str) -> str:
    code = normalize_code(raw_symbol)
    exchange = extract_user_exchange(raw_symbol) or infer_exchange(code)
    return f"{exchange.lower()}.{code}"


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

