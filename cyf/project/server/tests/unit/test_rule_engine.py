"""rule_engine 纯函数测试 — 无 IO 依赖，验证策略规则评估核心逻辑。"""

import pytest
from datetime import date

from service.quant.rule_engine import (
    evaluate_strategy_rules,
    get_required_history_size,
    _evaluate_one_rule,
    _ma,
    _period_return,
    _breakout_high,
)


# ---------------------------------------------------------------------------
# 辅助：构造 mock QuantDailyBar
# ---------------------------------------------------------------------------

class MockBar:
    """轻量 mock，模拟 QuantDailyBar 的字段。"""
    def __init__(self, **kwargs):
        self.symbol = kwargs.get("symbol", "000001.SZ")
        self.trade_date = kwargs.get("trade_date", date(2025, 1, 15))
        self.close_price = kwargs.get("close_price", 12.0)
        self.open_price = kwargs.get("open_price", 11.8)
        self.high_price = kwargs.get("high_price", 12.5)
        self.low_price = kwargs.get("low_price", 11.5)
        self.pct_change = kwargs.get("pct_change", 1.5)
        self.volume = kwargs.get("volume", 1_000_000)
        self.amount = kwargs.get("amount", 10_000_000)
        self.turnover_rate = kwargs.get("turnover_rate", 1.5)


def _make_history(n: int, close_base: float = 12.0, **overrides) -> list:
    """生成 n 条从旧到新的 MockBar，history[0] 是最新。"""
    bars = []
    for i in range(n):
        bars.append(MockBar(
            trade_date=date(2025, 1, 15 - (n - 1 - i)),
            close_price=close_base + i * 0.1,
            volume=1_000_000 + i * 10_000,
            high_price=close_base + i * 0.1 + 0.5,
            low_price=close_base + i * 0.1 - 0.3,
            **overrides,
        ))
    # 让 index 0 为最新（反转）
    bars.reverse()
    return bars


# ===========================================================================
# evaluate_strategy_rules 入口测试
# ===========================================================================


class TestEvaluateStrategyRules:
    """测试 evaluate_strategy_rules 主入口。"""

    def test_empty_history_returns_not_passed(self):
        result = evaluate_strategy_rules({"rules": [{"rule_type": "field_compare"}]}, [])
        assert result["passed"] is False
        assert "无行情数据" in result["reasons"]

    def test_no_rules_returns_not_passed(self):
        history = _make_history(5)
        result = evaluate_strategy_rules({"rules": []}, history)
        assert result["passed"] is False
        assert "未配置规则" in result["reasons"]

    def test_none_rules_returns_not_passed(self):
        history = _make_history(5)
        result = evaluate_strategy_rules({}, history)
        assert result["passed"] is False
        assert "未配置规则" in result["reasons"]


# ===========================================================================
# field_compare 规则
# ===========================================================================


class TestFieldCompare:
    """测试 field_compare 规则类型。"""

    def test_pct_change_gte_threshold(self):
        history = _make_history(5, pct_change=3.0)
        rule = {"rule_type": "field_compare", "field": "pct_change", "operator": ">=", "value": 2.0}
        passed, metrics, label = _evaluate_one_rule(rule, history[0], history)
        assert passed is True
        assert metrics["actual"] == 3.0

    def test_pct_change_below_threshold(self):
        history = _make_history(5, pct_change=1.0)
        rule = {"rule_type": "field_compare", "field": "pct_change", "operator": ">=", "value": 2.0}
        passed, metrics, label = _evaluate_one_rule(rule, history[0], history)
        assert passed is False

    def test_field_is_none(self):
        bar = MockBar(pct_change=None)
        rule = {"rule_type": "field_compare", "field": "pct_change", "operator": ">=", "value": 2.0}
        passed, metrics, label = _evaluate_one_rule(rule, bar, [bar])
        assert passed is False


# ===========================================================================
# close_above_ma / close_below_ma 规则
# ===========================================================================


class TestCloseAboveBelowMA:
    """测试均线突破规则。"""

    def test_close_above_ma5(self):
        # 5 条 bar, index 0 最新。close_price 远高于其他，确保高于 MA5
        bars = [MockBar(close_price=12.0)] + [MockBar(close_price=11.0) for _ in range(4)]
        # bars 已经是 [newest=12.0, 11.0, 11.0, 11.0, 11.0]
        # MA5 = (12 + 11*4) / 5 = 11.2
        # 12.0 > 11.2 → True
        rule = {"rule_type": "close_above_ma", "window": 5}
        passed, metrics, _ = _evaluate_one_rule(rule, bars[0], bars)
        assert passed is True

    def test_close_below_ma5(self):
        # 5 条 bar, index 0 最新。close_price 远低于其他，确保低于 MA5
        bars = [MockBar(close_price=10.0)] + [MockBar(close_price=11.0) for _ in range(4)]
        # bars 已经是 [newest, ..., oldest]
        # MA5 = (10 + 11 + 11 + 11 + 11) / 5 = 10.8
        # 10.0 < 10.8 → True
        rule = {"rule_type": "close_below_ma", "window": 5}
        passed, metrics, _ = _evaluate_one_rule(rule, bars[0], bars)
        assert passed is True


# ===========================================================================
# volume_ratio 规则
# ===========================================================================


class TestVolumeRatio:
    """测试成交量比率规则。"""

    def test_volume_ratio_above_threshold(self):
        # 构造当前量远大于历史均量
        history = [MockBar(volume=500_000) for _ in range(6)]
        history[0] = MockBar(volume=3_000_000)  # 最新，6倍
        rule = {"rule_type": "volume_ratio", "window": 5, "operator": ">=", "value": 2.0}
        passed, metrics, _ = _evaluate_one_rule(rule, history[0], history)
        assert passed is True
        assert metrics["actual"] >= 2.0


# ===========================================================================
# period_return 规则
# ===========================================================================


class TestPeriodReturn:
    """测试区间收益率规则。"""

    def test_period_return_above_threshold(self):
        # 5 日收益 > 3%
        bars = [MockBar(close_price=10.0 + i * 0.5) for i in range(7)]
        bars.reverse()  # index 0 最新 13.0, index 5 = 10.5 → return ≈ 23.8%
        rule = {"rule_type": "period_return", "lookback": 5, "operator": ">=", "value": 3.0}
        passed, metrics, _ = _evaluate_one_rule(rule, bars[0], bars)
        assert passed is True
        assert metrics["actual"] > 3.0


# ===========================================================================
# breakout_high 规则
# ===========================================================================


class TestBreakoutHigh:
    """测试突破高点规则。"""

    def test_breakout_high(self):
        # 当前 bar (index 0) 的 close_price 超过之前 5 根 bar 的最高价
        bars_before = [MockBar(high_price=10.0 + i * 0.1) for i in range(5)]
        bars_before.append(MockBar(close_price=12.0, high_price=12.0))
        history = list(reversed(bars_before))
        # history = [newest(close=12,high=12), high=10.4, high=10.3, high=10.2, high=10.1, high=10.0]
        # max(h[1:6].high) = 10.4, bars[0].close=12 > 10.4 → True
        rule = {"rule_type": "breakout_high", "window": 5}
        passed, metrics, _ = _evaluate_one_rule(rule, history[0], history)
        assert passed is True


# ===========================================================================
# logic / min_score / signal_type
# ===========================================================================


class TestLogicAndScore:
    """测试 logic 组合和 min_score 过滤。"""

    def test_logic_all_all_pass(self):
        history = _make_history(10, pct_change=3.0)
        rule_config = {
            "logic": "all",
            "rules": [
                {"rule_type": "field_compare", "field": "pct_change", "operator": ">=", "value": 2.0},
                {"rule_type": "field_compare", "field": "turnover_rate", "operator": ">=", "value": 1.0},
            ],
        }
        result = evaluate_strategy_rules(rule_config, history)
        assert result["passed"] is True

    def test_logic_all_one_fail(self):
        history = _make_history(10, pct_change=0.5)
        rule_config = {
            "logic": "all",
            "rules": [
                {"rule_type": "field_compare", "field": "pct_change", "operator": ">=", "value": 2.0},
                {"rule_type": "field_compare", "field": "turnover_rate", "operator": ">=", "value": 1.0},
            ],
        }
        result = evaluate_strategy_rules(rule_config, history)
        assert result["passed"] is False

    def test_logic_any_one_pass(self):
        history = _make_history(10, pct_change=0.5)
        rule_config = {
            "logic": "any",
            "rules": [
                {"rule_type": "field_compare", "field": "pct_change", "operator": ">=", "value": 2.0},
                {"rule_type": "field_compare", "field": "turnover_rate", "operator": ">=", "value": 1.0},
            ],
        }
        result = evaluate_strategy_rules(rule_config, history)
        assert result["passed"] is True

    def test_min_score_filters(self):
        history = _make_history(10, pct_change=3.0)
        rule_config = {
            "logic": "all",
            "min_score": 5.0,  # 只有一条规则，weight=1，score=1
            "rules": [
                {"rule_type": "field_compare", "field": "pct_change", "operator": ">=", "value": 2.0},
            ],
        }
        result = evaluate_strategy_rules(rule_config, history)
        assert result["passed"] is False  # score 1 < min_score 5

    def test_signal_type_propagated(self):
        history = _make_history(5, pct_change=3.0)
        rule_config = {
            "signal_type": "buy",
            "rules": [
                {"rule_type": "field_compare", "field": "pct_change", "operator": ">=", "value": 2.0},
            ],
        }
        result = evaluate_strategy_rules(rule_config, history)
        assert result["signal_type"] == "buy"


# ===========================================================================
# 异常输入
# ===========================================================================


class TestInvalidInput:
    """测试非法输入。"""

    def test_unsupported_operator_raises(self):
        bar = MockBar(pct_change=3.0)
        rule = {"rule_type": "field_compare", "field": "pct_change", "operator": "~~", "value": 2.0}
        with pytest.raises(ValueError, match="不支持的 operator"):
            _evaluate_one_rule(rule, bar, [bar])

    def test_unsupported_rule_type_raises(self):
        bar = MockBar()
        rule = {"rule_type": "unknown_type"}
        with pytest.raises(ValueError, match="不支持的规则类型"):
            _evaluate_one_rule(rule, bar, [bar])


# ===========================================================================
# get_required_history_size
# ===========================================================================


class TestRequiredHistorySize:
    """测试 get_required_history_size 计算历史窗口。"""

    def test_close_above_ma(self):
        config = {"rules": [{"rule_type": "close_above_ma", "window": 10}]}
        assert get_required_history_size(config) == 10

    def test_volume_ratio(self):
        config = {"rules": [{"rule_type": "volume_ratio", "window": 5}]}
        assert get_required_history_size(config) == 6  # window + 1

    def test_period_return(self):
        config = {"rules": [{"rule_type": "period_return", "lookback": 20}]}
        assert get_required_history_size(config) == 21  # lookback + 1

    def test_breakout_high(self):
        config = {"rules": [{"rule_type": "breakout_high", "window": 30}]}
        assert get_required_history_size(config) == 31  # window + 1

    def test_multiple_rules_takes_max(self):
        config = {"rules": [
            {"rule_type": "close_above_ma", "window": 5},
            {"rule_type": "breakout_high", "window": 20},
        ]}
        assert get_required_history_size(config) == 21

    def test_empty_rules(self):
        assert get_required_history_size({"rules": []}) == 1
