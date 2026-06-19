"""cron_utils 纯函数测试 — 验证 CronExpression 解析和匹配逻辑。"""

from datetime import datetime

import pytest

from service.quant.cron_utils import CronExpression, cron_matches


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
    """测试 CronExpression.matches() 逻辑。"""

    def test_weekday_15_20_matches(self):
        """cron 1-5 解析为 Python weekday={1,2,3,4,5}（周二到周六）。"""
        cron = CronExpression("20 15 * * 1-5")
        dt = datetime(2025, 1, 14, 15, 20)  # 周二，Python weekday()=1
        assert cron.matches(dt) is True

    def test_weekend_no_match(self):
        """周一 (weekday=0) 不在 1-5 范围内。"""
        cron = CronExpression("20 15 * * 1-5")
        dt = datetime(2025, 1, 13, 15, 20)  # 周一，Python weekday()=0
        assert cron.matches(dt) is False

    def test_wrong_minute_no_match(self):
        cron = CronExpression("20 15 * * 1-5")
        dt = datetime(2025, 1, 14, 15, 30)  # 周二，但分钟不对
        assert cron.matches(dt) is False

    def test_wrong_hour_no_match(self):
        cron = CronExpression("20 15 * * 1-5")
        dt = datetime(2025, 1, 14, 14, 20)  # 周二，但小时不对
        assert cron.matches(dt) is False

    def test_cron_matches_helper(self):
        """cron_matches 便捷函数。"""
        assert cron_matches("20 15 * * 1-5", datetime(2025, 1, 14, 15, 20)) is True   # 周二
        assert cron_matches("20 15 * * 1-5", datetime(2025, 1, 13, 15, 20)) is False  # 周一

    def test_every_5_minutes(self):
        """*/5 分钟步长。"""
        cron = CronExpression("*/5 * * * *")
        assert cron.matches(datetime(2025, 1, 13, 10, 0)) is True
        assert cron.matches(datetime(2025, 1, 13, 10, 5)) is True
        assert cron.matches(datetime(2025, 1, 13, 10, 3)) is False
