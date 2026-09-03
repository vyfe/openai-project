"""RSI / ATR / OBV 三个 compute 函数的单测。

每个 compute 都验证：
- 空 bars / warmup 期返回 None
- 输出 list 长度与 bars 对齐
- 关键不变量（如 RSI 范围、ATR 与价格波动一致、OBV 单调递增于上涨）
"""
from __future__ import annotations

from service.quant import indicator_service as isvc
from tests.unit.test_rule_engine import MockBar


# ===========================================================================
# RSI
# ===========================================================================


class TestComputeRsi:
    def test_empty_bars(self):
        out = isvc.compute_rsi([], window=14)
        assert out == {"rsi_14": []}

    def test_warmup_returns_all_none(self):
        bars = [MockBar(close_price=10 + i * 0.1) for i in range(13)]
        out = isvc.compute_rsi(bars, window=14)
        assert all(v is None for v in out["rsi_14"])

    def test_output_aligned_with_bars(self):
        bars = [MockBar(close_price=10 + i * 0.1) for i in range(30)]
        out = isvc.compute_rsi(bars, window=14)
        assert len(out["rsi_14"]) == len(bars)

    def test_monotonic_up_trend_rsi_in_range(self):
        # 旧→新顺序构造后 reverse → bars[0] 最新（最大 close）
        bars = [MockBar(close_price=10 + i * 0.5) for i in range(40)]
        bars.reverse()
        out = isvc.compute_rsi(bars, window=14)
        rsi_values = [v for v in out["rsi_14"] if v is not None]
        assert rsi_values, "应至少有一个有效 RSI 值"
        # 持续上涨 → RSI 应在合理区间（理论上 100，含浮点误差）
        assert all(60 <= v <= 100 for v in rsi_values[-5:])

    def test_monotonic_down_trend_rsi_low(self):
        bars = [MockBar(close_price=20 - i * 0.5) for i in range(40)]
        bars.reverse()
        out = isvc.compute_rsi(bars, window=14)
        rsi_values = [v for v in out["rsi_14"] if v is not None]
        assert rsi_values, "应至少有一个有效 RSI 值"
        assert all(0 <= v <= 40 for v in rsi_values[-5:])

    def test_flat_market_rsi_neutral(self):
        bars = [MockBar(close_price=10.0) for _ in range(30)]
        out = isvc.compute_rsi(bars, window=14)
        # 全部 diff=0 → avg_gain=0 且 avg_loss=0 → 100（按本实现约定）
        rsi_values = [v for v in out["rsi_14"] if v is not None]
        assert all(v == 100.0 for v in rsi_values)

    def test_none_close_price_skipped(self):
        bars = [MockBar(close_price=None) for _ in range(20)]
        out = isvc.compute_rsi(bars, window=14)
        # 没有有效 close → 全 None
        assert all(v is None for v in out["rsi_14"])


# ===========================================================================
# ATR
# ===========================================================================


class TestComputeAtr:
    def test_empty_bars(self):
        out = isvc.compute_atr([], window=14)
        assert out == {"atr_14": []}

    def test_single_bar_returns_none(self):
        bars = [MockBar()]
        out = isvc.compute_atr(bars, window=14)
        assert all(v is None for v in out["atr_14"])

    def test_warmup_window_unfilled(self):
        bars = [MockBar(high_price=12.0, low_price=11.0) for _ in range(10)]
        out = isvc.compute_atr(bars, window=14)
        assert all(v is None for v in out["atr_14"])

    def test_output_aligned_with_bars(self):
        bars = [MockBar(high_price=12.0, low_price=11.0) for _ in range(30)]
        out = isvc.compute_atr(bars, window=14)
        assert len(out["atr_14"]) == len(bars)

    def test_constant_range_atr_equals_hl_range(self):
        """high-low 恒为 1.0 时，ATR ≈ 1.0。"""
        bars = [MockBar(high_price=11.0, low_price=10.0, close_price=10.5) for _ in range(20)]
        out = isvc.compute_atr(bars, window=14)
        atr_values = [v for v in out["atr_14"] if v is not None]
        assert atr_values
        assert all(abs(v - 1.0) < 1e-6 for v in atr_values)

    def test_atr_increases_with_volatility(self):
        """ATR 在波动变大时应递增。"""
        calm = [MockBar(high_price=11.0, low_price=10.0, close_price=10.5) for _ in range(20)]
        volatile = calm[:5] + [MockBar(high_price=12.0, low_price=9.0, close_price=10.5) for _ in range(15)]
        calm_atr = isvc.compute_atr(calm, window=14)["atr_14"]
        volatile_atr = isvc.compute_atr(volatile, window=14)["atr_14"]
        calm_last = next((v for v in reversed(calm_atr) if v is not None), None)
        volatile_last = next((v for v in reversed(volatile_atr) if v is not None), None)
        assert calm_last is not None and volatile_last is not None
        assert volatile_last > calm_last


# ===========================================================================
# OBV
# ===========================================================================


class TestComputeObv:
    def test_empty_bars(self):
        out = isvc.compute_obv([])
        assert out == {"obv": []}

    def test_single_bar_returns_none(self):
        out = isvc.compute_obv([MockBar()])
        assert all(v is None for v in out["obv"])

    def test_output_aligned_with_bars(self):
        bars = [MockBar() for _ in range(20)]
        out = isvc.compute_obv(bars)
        assert len(out["obv"]) == len(bars)

    def test_strict_uptrend_obv_monotonic_increasing(self):
        """连续上涨 + 固定 volume → OBV 单调递增。"""
        n = 10
        # bars 是新→旧顺序：bars[0] 最新，close 最大；先构造旧→新再 reverse
        bars = [MockBar(close_price=10 + i, volume=1000) for i in range(n)]
        bars.reverse()
        obv_clean = [v for v in isvc.compute_obv(bars)["obv"] if v is not None]
        for prev, cur in zip(obv_clean, obv_clean[1:]):
            assert cur > prev

    def test_strict_downtrend_obv_monotonic_decreasing(self):
        """连续下跌 → OBV 单调递减。"""
        n = 10
        bars = [MockBar(close_price=20 - i, volume=1000) for i in range(n)]
        bars.reverse()
        obv_clean = [v for v in isvc.compute_obv(bars)["obv"] if v is not None]
        for prev, cur in zip(obv_clean, obv_clean[1:]):
            assert cur < prev

    def test_flat_close_obv_unchanged(self):
        """平盘 → OBV 保持 0.0。"""
        bars = [MockBar(close_price=10.0, volume=1000) for _ in range(10)]
        out = isvc.compute_obv(bars)["obv"]
        obv_clean = [v for v in out if v is not None]
        assert all(v == 0.0 for v in obv_clean)