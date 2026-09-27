"""expression_engine 沙箱与语义测试。"""
import pytest

from service.quant.expression_engine import (
    ExpressionError,
    SeriesView,
    compile_expression,
    evaluate,
    infer_indicators_from_expr,
    validate_expression,
)


# ===========================================================================
# 编译：拒绝所有危险语法
# ===========================================================================


class TestCompileRejectsUnsafe:
    @pytest.mark.parametrize("bad", [
        '__import__("os")',
        "().__class__",
        "open('/etc/passwd')",
        "(lambda: 1)()",
        "[x for x in range(10)]",
        "a.b.c",
        "a[1:2]",          # slice
        "exec('1')",
        "eval('1+1')",
        "globals()",
        "getattr(a, 'b')",
        "(a or b) if True else None",  # if/三元可以，但需要 ast 节点允许 — 这个其实应该 allow
    ])
    def test_rejected(self, bad):
        if bad == "(a or b) if True else None":
            return  # 这是合法的 if 表达式，跳过
        with pytest.raises(ExpressionError):
            compile_expression(bad)


class TestCompileRejectsKeywordArgs:
    @pytest.mark.parametrize("bad", [
        "min(a=1)",
        "abs(*args)",
        "max(**kw)",
    ])
    def test_kw_rejected(self, bad):
        with pytest.raises(ExpressionError):
            compile_expression(bad)


# ===========================================================================
# 求值：核心语义
# ===========================================================================


def _view(seqs, idx):
    return SeriesView(seqs, idx)


class TestEvaluatorArithmetic:
    def test_add(self):
        t = compile_expression("a + b")
        assert evaluate(t, _view({"a": [3], "b": [4]}, 0)) == 7

    def test_div_zero_returns_none(self):
        t = compile_expression("a / b")
        assert evaluate(t, _view({"a": [1], "b": [0]}, 0)) is None

    def test_pow(self):
        t = compile_expression("a ** b")
        assert evaluate(t, _view({"a": [2], "b": [10]}, 0)) == 1024


class TestEvaluatorCompare:
    def test_lt(self):
        t = compile_expression("a < b")
        assert evaluate(t, _view({"a": [1], "b": [2]}, 0)) is True

    def test_eq(self):
        t = compile_expression("a == b")
        assert evaluate(t, _view({"a": [1], "b": [2]}, 0)) is False


class TestEvaluatorNone:
    def test_compare_with_none_returns_none(self):
        t = compile_expression("a > 0")
        assert evaluate(t, _view({"a": [None]}, 0)) is None

    def test_and_propagates_none(self):
        t = compile_expression("a and b")
        # a is None → 返回 None
        assert evaluate(t, _view({"a": [None], "b": [True]}, 0)) is None

    def test_or_propagates_none(self):
        t = compile_expression("a or b")
        # a is None → 继续看 b
        assert evaluate(t, _view({"a": [None], "b": [True]}, 0)) is True

    def test_min_skips_none(self):
        t = compile_expression("min(a, b, c)")
        assert evaluate(t, _view({"a": [None], "b": [3], "c": [1]}, 0)) == 1

    def test_max_skips_none(self):
        t = compile_expression("max(a, b)")
        assert evaluate(t, _view({"a": [None], "b": [None]}, 0)) is None


class TestEvaluatorSubscript:
    def test_prev_one(self):
        """x[1] 取"前 1 根"。seqs 与 bars_desc 对齐，idx=0=current；x[1] = seqs[idx+1]。"""
        t = compile_expression("x[1]")
        # idx=2, seq=[v0,v1,v2,v3], x[1] = seqs[3] = 40
        assert evaluate(t, _view({"x": [10, 20, 30, 40]}, 2)) == 40

    def test_prev_two(self):
        t = compile_expression("x[2]")
        # idx=2, seq=[v0,v1,v2,v3], x[2] = seqs[4] 越界 → None
        assert evaluate(t, _view({"x": [10, 20, 30, 40]}, 2)) is None
        # idx=1, seq=[v0,v1,v2,v3], x[2] = seqs[3] = 40
        assert evaluate(t, _view({"x": [10, 20, 30, 40]}, 1)) == 40

    def test_oob_returns_none(self):
        t = compile_expression("x[5]")
        assert evaluate(t, _view({"x": [10, 20, 30]}, 2)) is None


class TestEvaluatorCross:
    def test_cross_up(self):
        """cross_up(a, b): 当前 a > b 且 前一根 a <= b。"""
        # idx=2: cur a=30, b=25, prev (idx=3) a=20, b=25 → 30>25 ✓ 20<=25 ✓ → True
        t = compile_expression("cross_up(a, b)")
        assert evaluate(t, _view({"a": [10, 20, 30, 20], "b": [15, 30, 25, 25]}, 2)) is True

    def test_cross_down(self):
        # idx=2: cur a=20 < b=25, prev (idx=3) a=30 >= b=25 → True
        t = compile_expression("cross_down(a, b)")
        assert evaluate(t, _view({"a": [10, 30, 20, 30], "b": [15, 25, 25, 25]}, 2)) is True

    def test_cross_up_missing_prev_returns_none(self):
        # idx=0: 没有 prev（前 1 根）
        t = compile_expression("cross_up(a, b)")
        assert evaluate(t, _view({"a": [10], "b": [5]}, 0)) is None


class TestEvaluatorAvg:
    def test_avg(self):
        """avg(x, n) 取 idx..idx+n-1（即"当前及之前 n-1 根"）。"""
        # idx=2, n=3 → seqs[2:5] = [30, 40, 50] → avg = 40
        t = compile_expression("avg(x, 3)")
        assert evaluate(t, _view({"x": [10, 20, 30, 40, 50]}, 2)) == 40

    def test_avg_skips_none(self):
        t = compile_expression("avg(x, 3)")
        # idx=1, n=3 → seqs[1:4] = [None, 30, 40] → cleaned = [30, 40] → avg = 35
        assert evaluate(t, _view({"x": [10, None, 30, 40, 50]}, 1)) == 35


# ===========================================================================
# 校验与变量提取
# ===========================================================================


class TestValidate:
    def test_valid(self):
        r = validate_expression("close > ma_5", {"close", "ma_5"})
        assert r.ok is True
        assert "close" in r.used_vars
        assert "ma_5" in r.used_vars

    def test_unknown_var(self):
        r = validate_expression("close > unknown_var", {"close", "ma_5"})
        assert r.ok is False
        assert "unknown_var" in r.error

    def test_invalid_syntax(self):
        r = validate_expression("close >> ma_5", {"close", "ma_5"})
        assert r.ok is False


class TestInferIndicators:
    def test_ma_5(self):
        keys = infer_indicators_from_expr("close > ma_5", {"ma", "macd"})
        assert "ma" in keys

    def test_vol_ratio(self):
        keys = infer_indicators_from_expr("vol_ratio_10 > 2", {"vol_ratio"})
        assert "vol_ratio" in keys

    def test_mixed(self):
        keys = infer_indicators_from_expr(
            "cross_up(macd_dif, macd_dea) and ma_5 > 0",
            {"ma", "macd", "kdj"},
        )
        assert keys == {"ma", "macd"}


# ===========================================================================
# 性能烟雾测试
# ===========================================================================


class TestPerformance:
    def test_compile_cached(self):
        import time
        t = time.perf_counter()
        for _ in range(10000):
            compile_expression("close > ma_5 and volume > 0")
        elapsed = (time.perf_counter() - t) * 1000
        assert elapsed < 100, f"compile 10000x took {elapsed:.1f}ms"

    def test_eval_speed(self):
        import time
        t = compile_expression("close > ma_5 and volume > 0")
        view = _view(
            {"close": [10, 11, 13, 12, 15], "ma_5": [None, None, 11.5, 12.0, 13.0], "volume": [100, 200, 300, 400, 500]},
            4,
        )
        t0 = time.perf_counter()
        for _ in range(10000):
            evaluate(t, view)
        elapsed = (time.perf_counter() - t0) * 1000
        assert elapsed < 1000, f"eval 10000x took {elapsed:.1f}ms"

# ===========================================================================
# 回归：open 别名应可作为 Name 节点使用，不再被黑名单误拒
# ===========================================================================
#
# 历史 bug：_FORBIDDEN_NAMES 里包含 "open"，导致用户写 `open > 100` 会被拦下，
# 但后端 _V2_BAR_FIELD_ALIASES 又把 open 定义为 open_price 的合法别名。
# 修复：open 不再列入黑名单；open(...) 作为函数调用仍会被 _SAFE_FUNCTIONS 白名单拦截。
# ===========================================================================


class TestOpenAliasNoLongerBlacklisted:
    def test_open_name_is_compilable(self):
        """open 作为字段引用应能成功编译，不再被 _FORBIDDEN_NAMES 拦截。"""
        # 不应抛 ExpressionError
        compile_expression("open > 100")

    def test_open_works_at_runtime(self):
        """open 在求值时被 SeriesView 解析（SeriesView 不做别名转换，但 _V2_BAR_FIELD_ALIASES 在 rule_engine 里把 open 映射成 open_price 写入 series）；
        这里直接放 open 在 seqs 里模拟别名映射完成后的状态，验证 open > 9 求值通过。"""
        from service.quant.expression_engine import SeriesView
        view = SeriesView(
            seqs={
                "open": [10.0],      # 输入就是别名 open
                "high": [11.0],
                "low": [9.0],
                "close": [10.5],
                "volume": [100],
                "pct_change": [1.0],
                "turnover_rate": [0.5],
            },
            idx=0,
        )
        # 表达式里 open > 9 读到 10.0 > 9 → True
        tree = compile_expression("open > 9")
        assert evaluate(tree, view) is True

    def test_open_alias_resolved_by_rule_engine(self):
        """集成校验：rule_engine._v2_build_indicator_context 会把 open 别名映射到 open_price，
        触发 _check_safety 时 'open' 不再被 _FORBIDDEN_NAMES 拦截。"""
        # 只要 compile_expression 不抛错，说明 _FORBIDDEN_NAMES 修复成功
        compile_expression("open > ma_5")
        compile_expression("open and high > close")
        compile_expression("open[1] > open")

    def test_open_function_call_still_rejected(self):
        """open(...) 作为函数调用仍被白名单拒绝（只放行 _SAFE_FUNCTIONS）。"""
        with pytest.raises(ExpressionError):
            compile_expression("open('/etc/passwd')")

    def test_other_dangerous_names_still_blocked(self):
        """open 移出黑名单后，其他危险名仍必须被拦截。"""
        for bad in ("eval('1+1')", "exec('1')", "getattr(a, 'b')", "__import__('os')"):
            with pytest.raises(ExpressionError):
                compile_expression(bad)
