"""common 工具函数测试 — 验证 symbol 规范化和日期解析。"""

from datetime import date

import pytest

from service.quant.common import (
    normalize_symbol,
    normalize_code,
    infer_exchange,
    extract_user_exchange,
    resolve_market_info,
    correct_known_index_exchange,
    KNOWN_INDICES,
    to_baostock_symbol,
    parse_trade_date,
    normalize_date_text,
    compact_date_text,
    to_float,
    MINUTE_BAR_SKIPLIST,
    is_minute_bar_skip_symbol,
    filter_minute_bar_symbols,
    reload_minute_bar_skiplist,
)


class TestNormalizeCode:
    """测试 normalize_code — 提取纯数字代码。"""

    def test_sz_code_with_suffix(self):
        assert normalize_code("000001.SZ") == "000001"

    def test_sh_code_with_suffix(self):
        assert normalize_code("600519.SH") == "600519"

    def test_code_with_prefix(self):
        assert normalize_code("SZ.000001") == "000001"

    def test_pure_code(self):
        assert normalize_code("000001") == "000001"

    def test_empty_raises(self):
        with pytest.raises(ValueError, match="不能为空"):
            normalize_code("")

    def test_none_raises(self):
        with pytest.raises(ValueError, match="不能为空"):
            normalize_code(None)


class TestInferExchange:
    """测试 infer_exchange — 根据代码推断交易所。"""

    def test_sh_code(self):
        assert infer_exchange("600519") == "SH"

    def test_sz_code(self):
        assert infer_exchange("000001") == "SZ"

    def test_sz_code_2(self):
        assert infer_exchange("002594") == "SZ"

    def test_sz_code_3(self):
        assert infer_exchange("300750") == "SZ"

    def test_bj_code(self):
        assert infer_exchange("430047") == "BJ"

    def test_bj_code_8(self):
        assert infer_exchange("830946") == "BJ"

    def test_sh_code_9(self):
        assert infer_exchange("900901") == "SH"


class TestNormalizeSymbol:
    """测试 normalize_symbol — 规范化为 CODE.EXCHANGE 格式。

    优先信任用户给的 suffix：000300.SH/000001.SH/000688.SH 这些"code 以 0 开头但
    实际属于上交所"的标的，不能被 infer_exchange 强行改写成 .SZ。
    """

    def test_sz_code(self):
        assert normalize_symbol("000001") == "000001.SZ"

    def test_sh_code(self):
        assert normalize_symbol("600519") == "600519.SH"

    def test_idempotent(self):
        assert normalize_symbol("000001.SZ") == "000001.SZ"
        assert normalize_symbol("600519.SH") == "600519.SH"

    def test_shanghai_index_keeps_sh(self):
        """000001.SH（上证综指）必须保留 .SH，不能被 infer_exchange 改写。"""
        assert normalize_symbol("000001.SH") == "000001.SH"

    def test_hs300_keeps_sh(self):
        """000300.SH（沪深300）必须保留 .SH。"""
        assert normalize_symbol("000300.SH") == "000300.SH"

    def test_star50_keeps_sh(self):
        """000688.SH（科创50）必须保留 .SH。"""
        assert normalize_symbol("000688.SH") == "000688.SH"

    def test_lowercase_suffix(self):
        assert normalize_symbol("000300.sh") == "000300.SH"

    def test_prefix_form(self):
        assert normalize_symbol("SH.000300") == "000300.SH"

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            normalize_symbol("")


class TestExtractUserExchange:
    """测试 extract_user_exchange — 提取用户显式给的 suffix。"""

    def test_suffix_form(self):
        assert extract_user_exchange("000300.SH") == "SH"

    def test_prefix_form(self):
        assert extract_user_exchange("SH.000300") == "SH"

    def test_no_suffix_returns_none(self):
        assert extract_user_exchange("000300") is None

    def test_lowercase_returns_upper(self):
        assert extract_user_exchange("000300.sh") == "SH"

    def test_empty_returns_none(self):
        assert extract_user_exchange("") is None

    def test_none_returns_none(self):
        assert extract_user_exchange(None) is None

    def test_random_dot_returns_none(self):
        assert extract_user_exchange("abc.def") is None


class TestCorrectKnownIndexExchange:
    """correct_known_index_exchange — 把已知指数的 suffix 纠正成正确交易所。"""

    def test_hs300_sz_corrected_to_sh(self):
        assert correct_known_index_exchange("000300.SZ") == "000300.SH"

    def test_star50_sz_corrected_to_sh(self):
        assert correct_known_index_exchange("000688.SZ") == "000688.SH"

    def test_shanghai_50_corrected(self):
        assert correct_known_index_exchange("000016.SZ") == "000016.SH"

    def test_chinext_kept(self):
        assert correct_known_index_exchange("399006.SZ") is None

    def test_already_correct_returns_none(self):
        assert correct_known_index_exchange("000300.SH") is None

    def test_ambiguous_000001_not_corrected(self):
        """000001 在 SZ 是平安银行、SH 是上证综指，二义性保留，不动。"""
        assert KNOWN_INDICES.get("000001") is None
        assert correct_known_index_exchange("000001.SZ") is None
        assert correct_known_index_exchange("000001.SH") is None

    def test_no_suffix_added_when_known_index(self):
        assert correct_known_index_exchange("000300") == "000300.SH"
        assert correct_known_index_exchange("000688") == "000688.SH"

    def test_non_index_unchanged(self):
        assert correct_known_index_exchange("600519.SH") is None
        assert correct_known_index_exchange("000657.SZ") is None
        assert correct_known_index_exchange("688825.SH") is None


class TestKnownIndicesMap:
    """KNOWN_INDICES 表的正确性。"""

    def test_hs300_is_sh(self):
        assert KNOWN_INDICES["000300"] == "SH"

    def test_chinext_is_sz(self):
        assert KNOWN_INDICES["399006"] == "SZ"

    def test_no_ambiguous_000001(self):
        assert "000001" not in KNOWN_INDICES


class TestResolveMarketInfo:
    """resolve_market_info — 统一 provider 的 code/exchange/market_prefix 解析。"""

    def test_shanghai_stock_with_suffix(self):
        info = resolve_market_info("600519.SH")
        assert info.code == "600519"
        assert info.exchange == "SH"
        assert info.market_prefix == "sh"

    def test_shenzhen_stock_with_suffix(self):
        info = resolve_market_info("000001.SZ")
        assert info.code == "000001"
        assert info.exchange == "SZ"
        assert info.market_prefix == "sz"

    def test_shanghai_index_keeps_sh(self):
        """000300.SH / 000001.SH 必须保留 .SH，不能被 infer_exchange 改写。"""
        info = resolve_market_info("000300.SH")
        assert info.code == "000300"
        assert info.exchange == "SH"  # 不是 SZ
        assert info.market_prefix == "sh"

    def test_pure_code_infers_from_prefix(self):
        info = resolve_market_info("600519")
        assert info.code == "600519"
        assert info.exchange == "SH"

    def test_lowercase_suffix(self):
        info = resolve_market_info("000300.sh")
        assert info.exchange == "SH"
        assert info.market_prefix == "sh"

    def test_prefix_form_sh_000300(self):
        info = resolve_market_info("SH.000300")
        assert info.code == "000300"
        assert info.exchange == "SH"
        assert info.market_prefix == "sh"

    def test_beijing_stock(self):
        info = resolve_market_info("830946.BJ")
        assert info.code == "830946"
        assert info.exchange == "BJ"
        assert info.market_prefix == "bj"


class TestToBaostockSymbol:
    """测试 to_baostock_symbol — 转换为 baostock 格式。"""

    def test_sz_code(self):
        assert to_baostock_symbol("000001.SZ") == "sz.000001"

    def test_sh_code(self):
        assert to_baostock_symbol("600519") == "sh.600519"


class TestParseTradeDate:
    """测试 parse_trade_date — 多格式日期解析。"""

    def test_iso_format(self):
        assert parse_trade_date("2025-01-15") == date(2025, 1, 15)

    def test_compact_format(self):
        assert parse_trade_date("20250115") == date(2025, 1, 15)

    def test_slash_format(self):
        assert parse_trade_date("2025/01/15") == date(2025, 1, 15)

    def test_date_passthrough(self):
        d = date(2025, 1, 15)
        assert parse_trade_date(d) is d

    def test_empty_raises(self):
        with pytest.raises(ValueError, match="不能为空"):
            parse_trade_date("")

    def test_invalid_format_raises(self):
        with pytest.raises(ValueError, match="无法解析"):
            parse_trade_date("not-a-date")


class TestDateHelpers:
    """测试 normalize_date_text / compact_date_text。"""

    def test_normalize_date_text(self):
        assert normalize_date_text("20250115") == "2025-01-15"

    def test_compact_date_text(self):
        assert compact_date_text("2025-01-15") == "20250115"


class TestToFloat:
    """测试 to_float — 容错浮点转换。"""

    def test_none_returns_none(self):
        assert to_float(None) is None

    def test_int_to_float(self):
        assert to_float(10) == 10.0

    def test_string_with_comma(self):
        assert to_float("1,234.56") == 1234.56

    def test_nan_string(self):
        assert to_float("nan") is None

    def test_empty_string(self):
        assert to_float("") is None


class TestMinuteBarSkiplist:
    """MINUTE_BAR_SKIPLIST + is_minute_bar_skip_symbol + filter_minute_bar_symbols。"""

    def test_default_contains_main_indices(self):
        """默认白名单覆盖主流指数（上证/沪深/科创/创业等）。"""
        expected = {
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
        }
        assert expected.issubset(MINUTE_BAR_SKIPLIST)

    def test_stocks_not_in_skiplist(self):
        """普通股票不在白名单里。"""
        assert is_minute_bar_skip_symbol("600519.SH") is False
        assert is_minute_bar_skip_symbol("000001.SZ") is False  # 平安银行
        assert is_minute_bar_skip_symbol("300750.SZ") is False

    def test_main_indices_in_skiplist(self):
        assert is_minute_bar_skip_symbol("000001.SH") is True   # 上证综指
        assert is_minute_bar_skip_symbol("000300.SH") is True   # 沪深300
        assert is_minute_bar_skip_symbol("399001.SZ") is True   # 深证成指
        assert is_minute_bar_skip_symbol("399006.SZ") is True   # 创业板指

    def test_case_insensitive_suffix(self):
        """小写 .sh / .sz 也应能命中。"""
        assert is_minute_bar_skip_symbol("000300.sh") is True
        assert is_minute_bar_skip_symbol("sh.000300") is True
        assert is_minute_bar_skip_symbol("399006.sz") is True

    def test_pure_code_uses_inferred_exchange(self):
        """纯 code (000300) 走 infer_exchange → SH，再命中白名单。"""
        assert is_minute_bar_skip_symbol("000300") is True
        assert is_minute_bar_skip_symbol("399006") is True
        # 000001 推断为 SZ（平安银行），不在白名单
        assert is_minute_bar_skip_symbol("000001") is False

    def test_empty_or_invalid_returns_false(self):
        """空字符串 / None / 无法解析返回 False（不当指数处理）。"""
        assert is_minute_bar_skip_symbol("") is False
        assert is_minute_bar_skip_symbol(None) is False
        assert is_minute_bar_skip_symbol("not-a-symbol") is False

    def test_filter_keeps_stocks_drops_indices(self):
        symbols = ["600519.SH", "000300.SH", "300750.SZ", "399006.SZ", "000001.SZ"]
        result = filter_minute_bar_symbols(symbols)
        assert result == ["600519.SH", "300750.SZ", "000001.SZ"]

    def test_filter_preserves_order(self):
        symbols = ["399006.SZ", "600519.SH", "000300.SH", "300750.SZ"]
        result = filter_minute_bar_symbols(symbols)
        assert result == ["600519.SH", "300750.SZ"]

    def test_filter_empty_input(self):
        assert filter_minute_bar_symbols([]) == []
        assert filter_minute_bar_symbols(None) == []

    def test_env_var_extends_skiplist(self, monkeypatch):
        """环境变量追加新 symbol；不影响默认集合。"""
        monkeypatch.setenv("QUANT_MINUTE_BAR_SKIPLIST", "830946.BJ, 600000.SH")
        try:
            updated = reload_minute_bar_skiplist()
            assert "830946.BJ" in updated
            assert "600000.SH" in updated
            # 默认的 000300.SH 仍然在
            assert "000300.SH" in updated
            # 调用 is_minute_bar_skip_symbol 也能命中新增项
            assert is_minute_bar_skip_symbol("830946.BJ") is True
        finally:
            monkeypatch.delenv("QUANT_MINUTE_BAR_SKIPLIST", raising=False)
            reload_minute_bar_skiplist()
