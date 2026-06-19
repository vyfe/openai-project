"""common 工具函数测试 — 验证 symbol 规范化和日期解析。"""

from datetime import date

import pytest

from service.quant.common import (
    normalize_symbol,
    normalize_code,
    infer_exchange,
    to_baostock_symbol,
    parse_trade_date,
    normalize_date_text,
    compact_date_text,
    to_float,
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
    """测试 normalize_symbol — 规范化为 CODE.EXCHANGE 格式。"""

    def test_sz_code(self):
        assert normalize_symbol("000001") == "000001.SZ"

    def test_sh_code(self):
        assert normalize_symbol("600519") == "600519.SH"

    def test_idempotent(self):
        assert normalize_symbol("000001.SZ") == "000001.SZ"
        assert normalize_symbol("600519.SH") == "600519.SH"

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            normalize_symbol("")


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
