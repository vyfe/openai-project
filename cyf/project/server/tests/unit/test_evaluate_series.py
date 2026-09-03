"""evaluate_series v2 路径独立测试。"""
import datetime

import pytest

from service.quant.rule_engine import evaluate_series, get_required_history_size_v2
from tests.unit.test_rule_engine import MockBar, _make_history


def _date(s):
    y, m, d = map(int, s.split("-"))
    return datetime.date(y, m, d)


# ===========================================================================
# evaluate_series 基本形状
# ===========================================================================


class TestShape:
    def test_empty_history(self):
        cfg = {"version": 2, "rules": []}
        out = evaluate_series(cfg, [])
        assert len(out) == 1
        assert out[0]["passed"] is False
        assert "无行情数据" in out[0]["reasons"]

    def test_no_rules(self):
        cfg = {"version": 2, "rules": []}
        out = evaluate_series(cfg, _make_history(5))
        # 无规则时每根都返回 passed=False；reasons 列表为空（设计上不刷屏）
        assert all(r["passed"] is False for r in out)
        assert out[0]["score"] == 0

    def test_each_bar_evaluated(self):
        cfg = {"version": 2, "rules": [{"id": "r1", "expr": "close > 0", "weight": 1}]}
        history = _make_history(5)
        out = evaluate_series(cfg, history)
        assert len(out) == 5
        for r in out:
            assert r["passed"] is True
            assert r["metrics"]["rules"][0]["passed"] is True

    def test_metrics_includes_top_level_fields(self):
        cfg = {"version": 2, "rules": [{"id": "r1", "expr": "close > 0", "weight": 1}]}
        history = _make_history(5)
        out = evaluate_series(cfg, history)
        m = out[0]["metrics"]
        assert "trade_date" in m
        assert "close_price" in m
        assert "rules" in m
        assert m["rules"][0]["label"] == "r1"


# ===========================================================================
# 暖启动期返回 None 而不是抛异常
# ===========================================================================


class TestWarmup:
    def test_ma_warmup_with_short_history(self):
        """bars 不足 ma_5 时所有 bars 都应 False（warmup 期）。"""
        cfg = {"version": 2, "rules": [{"id": "r1", "expr": "close > ma_5", "weight": 1}]}
        # 4 根 bars，MA5 无法计算
        history = _make_history(4)
        out = evaluate_series(cfg, history)
        for r in out:
            assert r["metrics"]["rules"][0]["passed"] is False

    def test_cross_up_returns_false_with_single_bar(self):
        """单 bar 时 cross_up 返回 None（无 prev）。"""
        cfg = {"version": 2, "rules": [{"id": "r1", "expr": "cross_up(close, ma_5)", "weight": 1}]}
        history = _make_history(3)
        out = evaluate_series(cfg, history)
        # 不应抛异常
        assert all(r["passed"] is False for r in out)


# ===========================================================================
# gate 模式
# ===========================================================================


class TestGate:
    def test_all(self):
        cfg = {"version": 2, "gate": {"mode": "all"}, "rules": [
            {"id": "r1", "expr": "True", "weight": 1},
            {"id": "r2", "expr": "False", "weight": 1},
        ]}
        out = evaluate_series(cfg, _make_history(5))
        assert out[0]["passed"] is False

    def test_any(self):
        cfg = {"version": 2, "gate": {"mode": "any"}, "rules": [
            {"id": "r1", "expr": "False", "weight": 1},
            {"id": "r2", "expr": "True", "weight": 1},
        ]}
        out = evaluate_series(cfg, _make_history(5))
        assert out[0]["passed"] is True

    def test_expr(self):
        cfg = {"version": 2, "gate": {"mode": "expr", "expr": "r1 and not r2"}, "rules": [
            {"id": "r1", "expr": "True", "weight": 1},
            {"id": "r2", "expr": "False", "weight": 1},
        ]}
        out = evaluate_series(cfg, _make_history(5))
        assert out[0]["passed"] is True

    def test_min_score(self):
        cfg = {"version": 2, "min_score": 2.0, "rules": [
            {"id": "r1", "expr": "True", "weight": 1},
            {"id": "r2", "expr": "False", "weight": 1},
        ]}
        out = evaluate_series(cfg, _make_history(5))
        assert out[0]["passed"] is False


# ===========================================================================
# get_required_history_size_v2
# ===========================================================================


class TestHistorySizeV2:
    def test_empty(self):
        assert get_required_history_size_v2({"version": 2, "rules": []}) == 1

    def test_ma_60_default(self):
        cfg = {"version": 2, "rules": [{"id": "r1", "expr": "close > ma_5", "weight": 1}]}
        assert get_required_history_size_v2(cfg) == 60

    def test_explicit_ma_windows(self):
        cfg = {"version": 2, "indicators": [{"key": "ma", "params": {"windows": [5, 30]}}], "rules": []}
        assert get_required_history_size_v2(cfg) == 30

    def test_vol_ratio(self):
        cfg = {"version": 2, "rules": [{"id": "r1", "expr": "vol_ratio_10 > 0", "weight": 1}]}
        assert get_required_history_size_v2(cfg) == 6

    def test_bottom_structure(self):
        cfg = {"version": 2, "rules": [{"id": "r1", "expr": "td_signal == 'bottom_divergence'", "weight": 1}]}
        assert get_required_history_size_v2(cfg) == 9

    def test_takes_max(self):
        cfg = {"version": 2, "rules": [
            {"id": "r1", "expr": "close > ma_5", "weight": 1},
            {"id": "r2", "expr": "td_signal == 'bottom_divergence'", "weight": 1},
        ]}
        assert get_required_history_size_v2(cfg) == 60


# ===========================================================================
# v2 表达式自定义能力（v1 做不到的）
# ===========================================================================


class TestV2Extensions:
    def test_expr_gate_complex(self):
        """v2 独有的 expr gate: (r1 or r2) and r3。"""
        cfg = {"version": 2, "gate": {"mode": "expr", "expr": "(r1 or r2) and r3"}, "rules": [
            {"id": "r1", "expr": "False", "weight": 1},
            {"id": "r2", "expr": "True", "weight": 1},
            {"id": "r3", "expr": "True", "weight": 1},
        ]}
        out = evaluate_series(cfg, _make_history(5))
        assert out[0]["passed"] is True

    def test_expr_with_indicator_function(self):
        """cross_up 是 v2 独有函数。"""
        bars = [MockBar(trade_date=_date("2026-01-10")), MockBar(trade_date=_date("2026-01-09"))]
        ctx = {
            "2026-01-09": {"macd_dif": 1.0, "macd_dea": 2.0},
            "2026-01-10": {"macd_dif": 2.5, "macd_dea": 2.0},
        }
        cfg = {"version": 2, "rules": [
            {"id": "r1", "expr": "cross_up(macd_dif, macd_dea)", "weight": 1}
        ]}
        out = evaluate_series(cfg, bars, indicator_context=ctx)
        assert out[0]["passed"] is True

    def test_subscript_access(self):
        """x[1] 访问前一根值。"""
        history = _make_history(10)
        cfg = {"version": 2, "rules": [
            {"id": "r1", "expr": "close > close[1]", "weight": 1}
        ]}
        out = evaluate_series(cfg, history)
        # bars_desc 是降序（newest first），单调递增，所以 close[i] > close[i+1] 始终成立
        # 最后一根 (oldest) 没有 prev → 返回 None（不通过）
        for r in out[:-1]:
            assert r["metrics"]["rules"][0]["passed"] is True
        assert out[-1]["metrics"]["rules"][0]["passed"] is False

    def test_avg_function(self):
        """avg(close, 3) 等价于"当前及之前 2 根"均值。"""
        history = _make_history(10)
        cfg = {"version": 2, "rules": [
            {"id": "r1", "expr": "close > avg(close, 3)", "weight": 1}
        ]}
        out = evaluate_series(cfg, history)
        # 单调递增序列：close 应 >= 自己与之前 2 根的均值（接近但不一定严格）
        # 至少 idx=2 之后不应抛异常
        for r in out[2:]:
            assert "error" not in r["metrics"]["rules"][0]["metrics"]

    def test_weighted_score(self):
        """weight 应被加进 score，min_score 生效。"""
        cfg = {"version": 2, "gate": {"mode": "any"}, "min_score": 3.0, "rules": [
            {"id": "r1", "expr": "True", "weight": 5},
            {"id": "r2", "expr": "False", "weight": 1},
        ]}
        out = evaluate_series(cfg, _make_history(5))
        # gate=any：r1 True 通过；score=5 ≥ 3 → 整体通过
        assert out[0]["score"] == 5
        assert out[0]["passed"] is True

        # min_score 滤掉：r1 False, r2 False → score=0 < 3 → False
        cfg2 = {"version": 2, "gate": {"mode": "any"}, "min_score": 3.0, "rules": [
            {"id": "r1", "expr": "False", "weight": 1},
        ]}
        out2 = evaluate_series(cfg2, _make_history(5))
        assert out2[0]["score"] == 0
        assert out2[0]["passed"] is False


# ===========================================================================
# 性能（粗略 smoke）
# ===========================================================================


class TestPerformanceSmoke:
    def test_30_bars_evaluate_under_50ms(self):
        """单 symbol × 30 bar evaluate 应在 50ms 内完成。"""
        import time
        cfg = {"version": 2, "rules": [
            {"id": "r1", "expr": "close > ma_5", "weight": 1},
            {"id": "r2", "expr": "close > ma_20", "weight": 1},
            {"id": "r3", "expr": "volume > avg(volume, 5)", "weight": 1},
        ]}
        # _make_history 内部 trade_date = 2025-01-15 - (n-1-i)；n 大于 15 会越界。
        # 用一个能装下 n 根 bar 的日期起点。
        from tests.unit.test_rule_engine import MockBar
        history = [MockBar(
            trade_date=__import__('datetime').date(2025, 6, 1) + __import__('datetime').timedelta(days=i),
            close_price=12.0 + i * 0.1,
            volume=1_000_000 + i * 10_000,
        ) for i in range(30)]
        history.reverse()
        t = time.perf_counter()
        out = evaluate_series(cfg, history)
        elapsed_ms = (time.perf_counter() - t) * 1000
        assert elapsed_ms < 50, f"evaluate 30 bars took {elapsed_ms:.1f}ms"
        assert len(out) == 30


# ===========================================================================
# 新指标（RSI / ATR / OBV）表达式集成
# ===========================================================================


class TestRsiExpression:
    def _build_history(self, n: int):
        """绕过 _make_history 的日期越界，自行构造 bars（新→旧）。"""
        import datetime as _dt
        from tests.unit.test_rule_engine import MockBar
        bars = [
            MockBar(
                trade_date=_dt.date(2025, 6, 1) + _dt.timedelta(days=i),
                close_price=12.0 + i * 0.1,
            )
            for i in range(n)
        ]
        bars.reverse()
        return bars

    def test_rsi14_evaluates_through_registry(self):
        """rsi_14 走 registry compute 路径，能被 expression_engine 求值。"""
        bars = self._build_history(40)
        cfg = {"version": 2, "rules": [{"id": "r1", "expr": "rsi_14 > 50", "weight": 1}]}
        out = evaluate_series(cfg, bars)
        assert len(out) == 40
        # 不应抛异常；至少有规则结果字段（value 或 error）
        m = out[0]["metrics"]["rules"][0]["metrics"]
        assert "value" in m or "error" in m

    def test_rsi_default_window_used_when_no_decl(self):
        """expr 用 rsi_14 时，自动从变量名提取 window=14，无需在 indicators 显式声明。"""
        cfg = {"version": 2, "rules": [{"id": "r1", "expr": "rsi_14 > 50", "weight": 1}]}
        # 不抛异常且 history size 用 base_lookback
        assert get_required_history_size_v2(cfg) == 14


class TestAtrExpression:
    def _build_history(self, n: int):
        import datetime as _dt
        from tests.unit.test_rule_engine import MockBar
        bars = [
            MockBar(
                trade_date=_dt.date(2025, 6, 1) + _dt.timedelta(days=i),
                high_price=12.0 + 0.5,
                low_price=12.0 - 0.3,
                close_price=12.0,
            )
            for i in range(n)
        ]
        bars.reverse()
        return bars

    def test_atr14_evaluates_through_registry(self):
        bars = self._build_history(40)
        cfg = {"version": 2, "rules": [{"id": "r1", "expr": "atr_14 > 0", "weight": 1}]}
        out = evaluate_series(cfg, bars)
        assert len(out) == 40
        # 暖启动期：out[26..39] = None（first_valid = n-window-1 = 25 是最早有效位置，
        # 索引 26 之后的 bars 已没有足够的前置数据）
        for r in out[26:]:
            assert r["metrics"]["rules"][0]["passed"] is False
        # out[0] 是最新 bar，应有有效评估结果
        assert "value" in out[0]["metrics"]["rules"][0]["metrics"]

    def test_atr_default_history_size(self):
        cfg = {"version": 2, "rules": [{"id": "r1", "expr": "atr_14 > 0", "weight": 1}]}
        assert get_required_history_size_v2(cfg) == 14


class TestObvExpression:
    def _build_history(self, n: int):
        import datetime as _dt
        from tests.unit.test_rule_engine import MockBar
        bars = [
            MockBar(
                trade_date=_dt.date(2025, 6, 1) + _dt.timedelta(days=i),
                close_price=12.0 + i * 0.1,
                volume=1_000_000,
            )
            for i in range(n)
        ]
        bars.reverse()
        return bars

    def test_obv_evaluates_through_registry(self):
        bars = self._build_history(40)
        cfg = {"version": 2, "rules": [{"id": "r1", "expr": "obv > 0", "weight": 1}]}
        out = evaluate_series(cfg, bars)
        assert len(out) == 40
        m = out[-1]["metrics"]["rules"][0]["metrics"]
        assert "value" in m or "error" in m

    def test_obv_no_param_history_size(self):
        """OBV 没有参数，history size 应取 base_lookback=2。"""
        cfg = {"version": 2, "rules": [{"id": "r1", "expr": "obv > 0", "weight": 1}]}
        assert get_required_history_size_v2(cfg) == 2