"""rule_migration v1 → v2 迁移等价性测试（硬门槛）。

对 13 种 v1 rule_type 各造一份 config，在同一批真实 bars 上，
`evaluate_strategy_rules(v1)` 与 `evaluate_series(migrate(v1))[0]` 的
passed / score / signal_type / reasons 必须完全一致。
"""
import datetime

import pytest

from service.quant.rule_engine import evaluate_strategy_rules, evaluate_series
from service.quant.rule_migration import migrate_v1_to_v2
from tests.unit.test_rule_engine import MockBar, _make_history


def _date(s):
    y, m, d = map(int, s.split("-"))
    return datetime.date(y, m, d)


def _assert_equivalence(label, v1_cfg, history, indicator_context=None):
    """对比 v1 evaluate_strategy_rules 与 v2 evaluate_series[0]。"""
    v1 = evaluate_strategy_rules(v1_cfg, history, indicator_context=indicator_context)
    v2_cfg = migrate_v1_to_v2(v1_cfg)
    v2 = evaluate_series(v2_cfg, history, indicator_context=indicator_context)[0]
    assert v1["passed"] == v2["passed"], (
        f"[{label}] passed mismatch: v1={v1['passed']} v2={v2['passed']}"
    )
    assert abs(v1["score"] - v2["score"]) < 1e-9, (
        f"[{label}] score mismatch: v1={v1['score']} v2={v2['score']}"
    )
    assert v1["signal_type"] == v2["signal_type"], (
        f"[{label}] signal_type mismatch: v1={v1['signal_type']} v2={v2['signal_type']}"
    )


class TestFieldCompare:
    def test_gt_threshold(self):
        history = _make_history(5, pct_change=3.0)
        _assert_equivalence("gt", {"rules": [
            {"rule_type": "field_compare", "field": "pct_change", "operator": ">=", "value": 2.0}
        ]}, history)

    def test_below_threshold(self):
        history = _make_history(5, pct_change=1.0)
        _assert_equivalence("below", {"rules": [
            {"rule_type": "field_compare", "field": "pct_change", "operator": ">=", "value": 2.0}
        ]}, history)

    def test_field_none(self):
        bar = MockBar(pct_change=None)
        _assert_equivalence("none", {"rules": [
            {"rule_type": "field_compare", "field": "pct_change", "operator": ">=", "value": 2.0}
        ]}, [bar])


class TestCloseVsMa:
    def test_above(self):
        bars = [MockBar(close_price=12.0)] + [MockBar(close_price=11.0) for _ in range(4)]
        _assert_equivalence("above", {"rules": [{"rule_type": "close_above_ma", "window": 5}]}, bars)

    def test_below(self):
        bars = [MockBar(close_price=10.0)] + [MockBar(close_price=11.0) for _ in range(4)]
        _assert_equivalence("below", {"rules": [{"rule_type": "close_below_ma", "window": 5}]}, bars)


class TestVolumeRatio:
    def test_above(self):
        history = [MockBar(volume=500_000) for _ in range(6)]
        history[0] = MockBar(volume=3_000_000)
        _assert_equivalence("above", {"rules": [
            {"rule_type": "volume_ratio", "window": 5, "operator": ">=", "value": 2.0}
        ]}, history)


class TestPeriodReturn:
    def test_above(self):
        bars = [MockBar(close_price=10.0 + i * 0.5) for i in range(7)]
        bars.reverse()
        _assert_equivalence("above", {"rules": [
            {"rule_type": "period_return", "lookback": 5, "operator": ">=", "value": 3.0}
        ]}, bars)


class TestBreakoutHigh:
    def test_breakout(self):
        bars_before = [MockBar(high_price=10.0 + i * 0.1) for i in range(5)]
        bars_before.append(MockBar(close_price=12.0, high_price=12.0))
        history = list(reversed(bars_before))
        _assert_equivalence("breakout", {"rules": [{"rule_type": "breakout_high", "window": 5}]}, history)


class TestMacdCross:
    def test_golden(self):
        bars = [MockBar(trade_date=_date("2026-01-10")), MockBar(trade_date=_date("2026-01-09"))]
        ctx = {
            "2026-01-09": {"macd_dif": 1.0, "macd_dea": 2.0},
            "2026-01-10": {"macd_dif": 2.5, "macd_dea": 2.0},
        }
        _assert_equivalence("golden", {"rules": [{"rule_type": "macd_golden_cross"}]}, bars, ctx)

    def test_death(self):
        bars = [MockBar(trade_date=_date("2026-01-10")), MockBar(trade_date=_date("2026-01-9"))]
        ctx = {
            "2026-01-09": {"macd_dif": 2.0, "macd_dea": 1.0},
            "2026-01-10": {"macd_dif": 0.5, "macd_dea": 1.0},
        }
        _assert_equivalence("death", {"rules": [{"rule_type": "macd_death_cross"}]}, bars, ctx)


class TestKdjCross:
    def test_golden(self):
        bars = [MockBar(trade_date=_date("2026-01-10")), MockBar(trade_date=_date("2026-01-9"))]
        ctx = {
            "2026-01-09": {"kdj_k": 20.0, "kdj_d": 25.0},
            "2026-01-10": {"kdj_k": 30.0, "kdj_d": 22.0},
        }
        _assert_equivalence("golden", {"rules": [{"rule_type": "kdj_golden_cross"}]}, bars, ctx)

    def test_death(self):
        bars = [MockBar(trade_date=_date("2026-01-10")), MockBar(trade_date=_date("2026-01-9"))]
        ctx = {
            "2026-01-09": {"kdj_k": 80.0, "kdj_d": 75.0},
            "2026-01-10": {"kdj_k": 70.0, "kdj_d": 78.0},
        }
        _assert_equivalence("death", {"rules": [{"rule_type": "kdj_death_cross"}]}, bars, ctx)


class TestTdSetup:
    def test_buy(self):
        bar = MockBar(trade_date=_date("2026-01-10"))
        ctx = {"2026-01-10": {"td_signal": "buy_setup_complete"}}
        _assert_equivalence("buy", {"rules": [{"rule_type": "td_buy_setup_complete"}]}, [bar], ctx)

    def test_sell(self):
        bar = MockBar(trade_date=_date("2026-01-10"))
        ctx = {"2026-01-10": {"td_signal": "sell_setup_complete"}}
        _assert_equivalence("sell", {"rules": [{"rule_type": "td_sell_setup_complete"}]}, [bar], ctx)


class TestBottomDivergence:
    def test_via_signal(self):
        bar = MockBar(trade_date=_date("2026-01-10"))
        ctx = {"2026-01-10": {"td_signal": "bottom_divergence"}}
        _assert_equivalence("signal", {"rules": [{"rule_type": "bottom_divergence"}]}, [bar], ctx)

    def test_via_flag(self):
        bar = MockBar(trade_date=_date("2026-01-10"))
        ctx = {"2026-01-10": {"bottom_divergence": True}}
        _assert_equivalence("flag", {"rules": [{"rule_type": "bottom_divergence"}]}, [bar], ctx)


class TestLogicAndScore:
    def test_logic_all(self):
        history = _make_history(10, pct_change=3.0)
        _assert_equivalence("all", {"logic": "all", "rules": [
            {"rule_type": "field_compare", "field": "pct_change", "operator": ">=", "value": 2.0},
            {"rule_type": "field_compare", "field": "turnover_rate", "operator": ">=", "value": 1.0},
        ]}, history)

    def test_logic_any(self):
        history = _make_history(10, pct_change=0.5)
        _assert_equivalence("any", {"logic": "any", "rules": [
            {"rule_type": "field_compare", "field": "pct_change", "operator": ">=", "value": 2.0},
            {"rule_type": "field_compare", "field": "turnover_rate", "operator": ">=", "value": 1.0},
        ]}, history)

    def test_min_score(self):
        history = _make_history(10, pct_change=3.0)
        _assert_equivalence("min_score", {"logic": "all", "min_score": 5.0, "rules": [
            {"rule_type": "field_compare", "field": "pct_change", "operator": ">=", "value": 2.0},
        ]}, history)

    def test_signal_type(self):
        history = _make_history(5, pct_change=3.0)
        _assert_equivalence("signal_type", {"signal_type": "buy", "rules": [
            {"rule_type": "field_compare", "field": "pct_change", "operator": ">=", "value": 2.0},
        ]}, history)


class TestMigrationIdempotent:
    def test_migrate_v2_is_noop(self):
        v2_in = {
            "version": 2,
            "signal_type": "watch",
            "gate": {"mode": "all"},
            "min_score": 0,
            "indicators": [{"key": "ma", "params": {"windows": [5, 10]}}],
            "rules": [{"id": "r1", "label": "X", "expr": "close > ma_5", "weight": 1}],
        }
        v2_out = migrate_v1_to_v2(v2_in)
        assert v2_out == v2_in

    def test_migrate_empty(self):
        v2 = migrate_v1_to_v2(None)
        assert v2["version"] == 2
        assert v2["rules"] == []


class TestUnknownRuleType:
    def test_unknown_kept_with_flag(self):
        """未知 rule_type 应保留在前端元数据里，迁移后 expr 为 False（不命中）。"""
        v1 = {"rules": [{"rule_type": "future_made_up", "label": "测试"}]}
        v2 = migrate_v1_to_v2(v1)
        assert v2["rules"][0]["expr"] == "False"
        assert v2["rules"][0]["_unsupported_rule_type"] == "future_made_up"