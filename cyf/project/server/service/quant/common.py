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

    code 部分**保留大小写**——alpha 代码（如 ETF / 测试用符号 "WARMUP.SH"）的
    大小写是有意义的，不能被 `.lower()` 一刀切。仅在判断 sh/sz/bj 前缀后缀时
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


# ----------------------------------------------------------------------
# 分钟线跳过白名单（指数）
# ----------------------------------------------------------------------
# A 股指数在 baostock / 东方财富的分钟线 API 都不开放（指数只到日线级别），
# 历史上一直重试 3 次 × sleep 60s 才放弃，单个指数 × 单 provider 要吃满 120s 纯等待。
# 改为在调度生成 client_task 和 provider 入口处 fail-fast 跳过指数。

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
    """环境变量 `QUANT_MINUTE_BAR_SKIPLIST` 可覆盖默认白名单。

    格式：逗号/空格分隔的 symbol 列表，例如
        QUANT_MINUTE_BAR_SKIPLIST="000001.SH,399001.SZ 399006.SZ"
    与默认集合取并集——不会清空默认值。
    """
    raw = os.environ.get("QUANT_MINUTE_BAR_SKIPLIST", "").strip()
    if not raw:
        return _DEFAULT_INDEX_NO_MINUTE
    extras = {item.strip() for item in raw.replace(",", " ").split() if item.strip()}
    return _DEFAULT_INDEX_NO_MINUTE | frozenset(extras)


# 模块级常量，进程启动时读一次环境变量；如需运行时调整，调用 reload_minute_bar_skiplist()。
MINUTE_BAR_SKIPLIST: frozenset[str] = _load_minute_bar_skiplist()


def reload_minute_bar_skiplist() -> frozenset[str]:
    """重新读环境变量刷新白名单；返回刷新后的集合。"""
    global MINUTE_BAR_SKIPLIST
    MINUTE_BAR_SKIPLIST = _load_minute_bar_skiplist()
    return MINUTE_BAR_SKIPLIST


def _canonical_symbol(raw_symbol: str) -> Optional[str]:
    """把任意写法 ('600519.SH' / 'sh.600519' / '600519') 归一为 'code.exchange' 大写形式。

    已知指数（KNOWN_INDICES 收录）的纯 code 会优先用 KNOWN_INDICES 里的交易所，
    避免 000300 被 infer_exchange 强行推断成 SZ 后漏匹配白名单。
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
    known = KNOWN_INDICES.get(code)
    if known:
        return f"{code}.{known}"
    try:
        exchange = infer_exchange(code)
    except ValueError:
        return None
    return f"{code}.{exchange}"


def is_minute_bar_skip_symbol(raw_symbol: str) -> bool:
    """判断给定 symbol 是否在分钟线跳过白名单中。

    兼容 '600519.SH' / 'sh.600519' / '600519' 等多种写法；空白/无法解析返回 False。
    """
    canonical = _canonical_symbol(raw_symbol)
    if canonical is None:
        return False
    return canonical in MINUTE_BAR_SKIPLIST


def filter_minute_bar_symbols(symbols: list[str] | tuple[str, ...]) -> list[str]:
    """过滤掉分钟线跳过白名单内的 symbol，返回剩余列表（不去重，保留原顺序）。

    主要在 schedule_execution_service.execute_data_sync 的 frequency='5m' 分支使用——
    不在白名单内的 symbol 原样透传；白名单内的全部丢弃（不抛错，指数本来就拉不到）。
    """
    if not symbols:
        return []
    return [item for item in symbols if not is_minute_bar_skip_symbol(item)]


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
    """解析分时 K 线时间戳：datetime / "YYYY-MM-DD HH:MM[:SS]" / "YYYY-MM-DDTHH:MM[:SS]"。"""
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

