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
    """从 "code.SUFFIX" / "SUFFIX.code" / "code.sh" 形式中提取用户显式给的 exchange；大小写不敏感。

    返回大写（"SH" / "SZ" / "BJ"），没显式给 suffix 则返回 None。
    用于 `normalize_symbol` 优先信任用户输入的 suffix，避免 `infer_exchange` 强行改写沪深300/上证综指/科创50
    这类"code 以0 开头但实际属于上交所"的特殊标的。
    """
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


# 沪深主要指数 → 交易所映射。仅列"在沪深都有合法股票 code 撞车"的指数，避免误伤个股。
# 注意：000001 在 SZ 是平安银行、在 SH 是上证综指——所以 000001 不在这里（保持二义性，交给用户 suffix）。
KNOWN_INDICES: dict[str, str] = {
    # 上交所指数
    "000016": "SH",  # 上证50
    "000300": "SH",  # 沪深300
    "000688": "SH",  # 科创50
    "000852": "SH",  # 中证1000
    "000905": "SH",  # 中证500
    # 深交所指数
    "399001": "SZ",  # 深证成指
    "399006": "SZ",  # 创业板指
    "399330": "SZ",  # 深证100
    "399905": "SZ",  # 中证500 (深)
}


def correct_known_index_exchange(symbol: str) -> Optional[str]:
    """如果 symbol 是已知指数且 suffix 与正确交易所不符，返回纠正后的 symbol；否则返回 None。

    用于 execute_data_sync 在 normalization 之前自动修复历史脏数据：
      000300.SZ → 000300.SH  (correct)
      000300.SH → None        (already correct, no need to "correct")
      000001.SZ → None        (ambiguous: 既可能是平安银行又可能是上证综指，不动)
      600519.SH → None        (not an index)
    """
    try:
        code = normalize_code(symbol)
    except ValueError:
        return None
    expected = KNOWN_INDICES.get(code)
    if not expected:
        return None
    user_exchange = extract_user_exchange(symbol)
    if user_exchange == expected:
        return None
    if user_exchange is None:
        # 用户没给 suffix，按已知交易所补全
        return f"{code}.{expected}"
    # 用户给的 suffix 跟已知不符 → 纠正
    return f"{code}.{expected}"


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


def normalize_date_text(value) -> str:
    return parse_trade_date(value).isoformat()


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

