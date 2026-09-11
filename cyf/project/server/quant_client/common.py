from __future__ import annotations

import os
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
    """从 `code.SUFFIX` / `SUFFIX.code` / `code` 形式中提取纯 code。

    code 部分保留大小写——alpha 代码大小写是有意义的，仅判断 sh/sz/bj 前缀后缀时
    局部忽略大小写。
    """
    symbol = str(raw_symbol or "").strip()
    if not symbol:
        raise ValueError("symbol 不能为空")
    if "." in symbol:
        left, right = symbol.split(".", 1)
        if left.lower() in ("sh", "sz", "bj"):
            return right
        if right.lower() in ("sh", "sz", "bj"):
            return left
    if symbol.lower().endswith((".sh", ".sz", ".bj")):
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


def parse_trade_datetime(value) -> datetime:
    """解析分时 K 线时间戳：支持 datetime / "YYYY-MM-DD HH:MM[:SS]" / "YYYY-MM-DDTHH:MM[:SS]"。"""
    if isinstance(value, datetime):
        return value
    text = str(value or "").strip()
    if not text:
        raise ValueError("trade_datetime 不能为空")
    normalized = text.replace("T", " ").replace("/", "-")
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(normalized, fmt)
        except ValueError:
            continue
    raise ValueError(f"无法解析 trade_datetime: {value}")


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


# ----------------------------------------------------------------------
# 分钟线跳过白名单（指数）
# ----------------------------------------------------------------------
# A 股指数在 baostock / 东方财富的分钟线 API 都不开放；provider 入口 fail-fast，
# 避免给指数重试 3 次 × sleep 60s 浪费 ~120s 纯等待。服务侧 schedule_execution_service
# 也会在 frequency='5m' 时预过滤一遍；两边保持同一份白名单。

_DEFAULT_INDEX_NO_MINUTE: frozenset[str] = frozenset({
    "000001.SH",  # 上证综指
    "000016.SH",  # 上证50
    "000300.SH",  # 沪深300
    "000688.SH",  # 科创50
    "000852.SH",  # 中证1000
    "000905.SH",  # 中证500
    "399001.SZ",  # 深证成指
    "399006.SZ",  # 创业板指
    "399330.SZ",  # 深证100
    "399905.SZ",  # 中证500(深)
    "000680.SZ",  # 科创综指
})


def _load_minute_bar_skiplist() -> frozenset[str]:
    """环境变量 `QUANT_MINUTE_BAR_SKIPLIST` 可在默认基础上追加，逗号/空格分隔。"""
    raw = os.environ.get("QUANT_MINUTE_BAR_SKIPLIST", "").strip()
    if not raw:
        return _DEFAULT_INDEX_NO_MINUTE
    extras = {item.strip() for item in raw.replace(",", " ").split() if item.strip()}
    return _DEFAULT_INDEX_NO_MINUTE | frozenset(extras)


MINUTE_BAR_SKIPLIST: frozenset[str] = _load_minute_bar_skiplist()


def reload_minute_bar_skiplist() -> frozenset[str]:
    """重新读环境变量刷新白名单；返回刷新后的集合。"""
    global MINUTE_BAR_SKIPLIST
    MINUTE_BAR_SKIPLIST = _load_minute_bar_skiplist()
    return MINUTE_BAR_SKIPLIST


def _canonical_symbol(raw_symbol: str) -> Optional[str]:
    """把任意写法 ('600519.SH' / 'sh.600519' / '600519') 归一为 'code.exchange' 大写形式。

    解析失败 / 无法推断交易所返回 None（让上游直接放过、不当作指数）。
    """
    if not raw_symbol:
        return None
    try:
        code = normalize_code(raw_symbol)
    except ValueError:
        return None
    user_exchange = extract_user_exchange(raw_symbol)
    if user_exchange:
        return f"{code}.{user_exchange}"
    try:
        exchange = infer_exchange(code)
    except ValueError:
        return None
    return f"{code}.{exchange}"


def is_minute_bar_skip_symbol(raw_symbol: str) -> bool:
    """判断给定 symbol 是否在分钟线跳过白名单中。空白/无法解析返回 False。"""
    canonical = _canonical_symbol(raw_symbol)
    if canonical is None:
        return False
    return canonical in MINUTE_BAR_SKIPLIST

