"""cron_utils 纯函数测试 — 验证 CronExpression 解析和匹配逻辑。"""

from datetime import datetime

import pytest

from service.quant.cron_utils import CronExpression, cron_matches
from service.quant.trade_calendar_service import resolve_trade_date_for_schedule


class TestCronExpressionParsing:
    """测试 CronExpression 解析。"""

    def test_valid_5_segment(self):
        cron = CronExpression("20 15 * * 1-5")
        assert cron.expression == "20 15 * * 1-5"

    def test_7_segment_raises(self):
        with pytest.raises(ValueError, match="5 段"):
            CronExpression("20 15 * * 1-5 0 0")

    def test_empty_raises(self):
        with pytest.raises(ValueError, match="5 段"):
            CronExpression("")

    def test_wildcard_minute(self):
        cron = CronExpression("* 15 * * 1-5")
        assert 0 in cron.minutes
        assert 59 in cron.minutes

    def test_step_syntax(self):
        cron = CronExpression("*/5 * * * *")
        assert cron.minutes == {0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55}

    def test_range_syntax(self):
        cron = CronExpression("0 9-11 * * *")
        assert cron.hours == {9, 10, 11}

    def test_comma_list(self):
        cron = CronExpression("0 9,15 * * *")
        assert cron.hours == {9, 15}

    def test_weekday_7_mapped_to_0(self):
        """7 在星期字段中应映射为 0（周日）。"""
        cron = CronExpression("0 9 * * 7")
        assert 0 in cron.weekdays

    def test_out_of_range_raises(self):
        with pytest.raises(ValueError, match="越界"):
            CronExpression("60 15 * * *")


class TestCronExpressionMatching:
    """测试 CronExpression.matches() 逻辑。

    注意：cron 标准的 weekday 是 0=周日, 1=周一, ..., 6=周六（与 Python weekday() 错 1）。
    CronExpression.matches() 内部已经把 Python weekday 转成 cron weekday 做匹配，
    所以下面测试里的 Python weekday 索引是反着的。
    """

    def test_weekday_15_matches_weekdays(self):
        """cron 1-5 = 周一到周五（cron 标准语义）。"""
        cron = CronExpression("20 15 * * 1-5")
        # 2025-01-13 是周一
        assert cron.matches(datetime(2025, 1, 13, 15, 20)) is True
        # 2025-01-14 周二
        assert cron.matches(datetime(2025, 1, 14, 15, 20)) is True
        # 2025-01-17 周五
        assert cron.matches(datetime(2025, 1, 17, 15, 20)) is True

    def test_weekday_15_skips_weekend(self):
        """cron 1-5 = 周一到周五 → 周六周日不匹配。"""
        cron = CronExpression("20 15 * * 1-5")
        # 2025-01-18 周六
        assert cron.matches(datetime(2025, 1, 18, 15, 20)) is False
        # 2025-01-19 周日
        assert cron.matches(datetime(2025, 1, 19, 15, 20)) is False

    def test_single_weekday_number_matches(self):
        """cron 0 = 周日；cron 6 = 周六。"""
        cron_sun = CronExpression("0 9 * * 0")
        cron_sat = CronExpression("0 9 * * 6")
        # 2025-01-19 周日
        assert cron_sun.matches(datetime(2025, 1, 19, 9, 0)) is True
        assert cron_sat.matches(datetime(2025, 1, 19, 9, 0)) is False
        # 2025-01-18 周六
        assert cron_sat.matches(datetime(2025, 1, 18, 9, 0)) is True
        assert cron_sun.matches(datetime(2025, 1, 18, 9, 0)) is False

    def test_wrong_minute_no_match(self):
        cron = CronExpression("20 15 * * 1-5")
        dt = datetime(2025, 1, 13, 15, 30)  # 周一但分钟不对
        assert cron.matches(dt) is False

    def test_wrong_hour_no_match(self):
        cron = CronExpression("20 15 * * 1-5")
        dt = datetime(2025, 1, 13, 14, 20)  # 周一但小时不对
        assert cron.matches(dt) is False

    def test_cron_matches_helper(self):
        """cron_matches 便捷函数：1-5 = 周一到周五。"""
        assert cron_matches("20 15 * * 1-5", datetime(2025, 1, 13, 15, 20)) is True   # 周一
        assert cron_matches("20 15 * * 1-5", datetime(2025, 1, 14, 15, 20)) is True   # 周二
        assert cron_matches("20 15 * * 1-5", datetime(2025, 1, 18, 15, 20)) is False  # 周六

    def test_every_5_minutes(self):
        """*/5 分钟步长。"""
        cron = CronExpression("*/5 * * * *")
        assert cron.matches(datetime(2025, 1, 13, 10, 0)) is True
        assert cron.matches(datetime(2025, 1, 13, 10, 5)) is True
        assert cron.matches(datetime(2025, 1, 13, 10, 3)) is False

    def test_monday_does_trigger_regression(self):
        """回归测试：用户的 20 18 * * 1-5 应该在周一正确触发。"""
        cron = CronExpression("20 18 * * 1-5")
        # 2025-01-13 是周一
        assert cron.matches(datetime(2025, 1, 13, 18, 20)) is True


def test_trade_calendar_out_of_range_falls_back_to_weekday():
    assert resolve_trade_date_for_schedule(datetime(2026, 7, 5, 12, 0)).isoformat() == "2026-07-03"
