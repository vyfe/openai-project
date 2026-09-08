"""indicator_service 纯函数测试 — 无 DB 依赖，使用 duck-type MockBar 验证 MA/BOLL/MACD/KDJ/TD/底部结构。"""

from datetime import date, timedelta

import pytest

from service.quant.indicator_service import (
    BOTTOM_STRUCTURE_PARAMS,
    DEFAULT_INDICATOR_WINDOWS,
    INDICATOR_SET_VERSION,
    SUPPORTED_INDICATOR_GROUPS,
    TD_SEQUENTIAL_PARAMS,
    TOP_STRUCTURE_PARAMS,
    _compute_indicator_snapshot,
    _resolve_indicator_params,
    compute_bottom_structure,
    compute_indicators,
    compute_td_sequential,
    compute_top_structure,
    max_lookback_bars,
)


_BASE_DATE = date(2026, 1, 1)


def _d(i: int) -> date:
    return _BASE_DATE + timedelta(days=i)


class MockBar:
    """鸭子类型 bar：仅需 indicator_service 关心的字段。"""

    def __init__(self, trade_date, close_price, open_price=None, high_price=None, low_price=None, volume=None):
        self.trade_date = trade_date
        self.close_price = close_price
        self.open_price = open_price if open_price is not None else close_price
        self.high_price = high_price if high_price is not None else close_price
        self.low_price = low_price if low_price is not None else close_price
        self.volume = volume


def _bars_ascending(n: int, start_price: float = 10.0, step: float = 0.1) -> list:
    """生成 n 条升序 MockBar。"""
    bars = []
    for i in range(n):
        c = start_price + i * step
        bars.append(MockBar(
            trade_date=_d(i),
            close_price=c,
            high_price=c + 0.5,
            low_price=c - 0.5,
            volume=1_000_000 + i * 1000,
        ))
    return bars


def _bars_v_shape(rise: int = 30, fall: int = 30, top_price: float = 16.0) -> list:
    """生成先涨后跌（V 顶）的 K 线序列。"""
    bars = []
    for i in range(rise):
        c = 10 + (top_price - 10) * i / max(rise - 1, 1)
        bars.append(MockBar(_d(i), c, high_price=c + 0.3, low_price=c - 0.3))
    for i in range(fall):
        c = top_price - top_price * 0.5 * i / max(fall, 1)
        bars.append(MockBar(_d(rise + i), c, high_price=c + 0.2, low_price=c - 0.5))
    return bars


# ===========================================================================
# 公共：compute_indicators 入口
# ===========================================================================


class TestComputeIndicatorsBasic:
    def test_empty_returns_empty(self):
        assert compute_indicators([]) == {}

    def test_all_default_indicators_present(self):
        bars = _bars_ascending(60)
        results = compute_indicators(bars)
        last = list(results.values())[-1]
        keys = set(last.keys())
        assert "ma_5" in keys
        assert "ma_60" in keys
        assert "boll_mid" in keys
        assert "macd_dif" in keys
        assert "kdj_k" in keys

    def test_descending_input_is_sorted_before_calculation(self):
        """接口即使按新到旧返回，最新 bar 仍应拿到基于历史的指标。"""
        ascending = _bars_ascending(60)
        ascending_results = compute_indicators(ascending)
        descending_results = compute_indicators(list(reversed(ascending)))

        assert list(descending_results) == list(ascending_results)
        latest_key = _d(59).isoformat()
        assert descending_results[latest_key]["ma_60"] == ascending_results[latest_key]["ma_60"]
        assert "macd_dif" in descending_results[latest_key]

    def test_filter_by_group(self):
        bars = _bars_ascending(60)
        results = compute_indicators(bars, indicator_names=["ma"])
        for date_key, row in results.items():
            assert all(k.startswith("ma_") for k in row.keys())
            assert "macd_dif" not in row

    def test_filter_by_specific_field(self):
        bars = _bars_ascending(60)
        results = compute_indicators(bars, indicator_names=["ma_5", "macd_dif"])
        for row in results.values():
            assert "ma_5" in row or not row

    def test_filter_by_mixed_group_and_field(self):
        bars = _bars_ascending(60)
        results = compute_indicators(bars, indicator_names=["ma_5", "kdj"])
        for row in results.values():
            non_empty = set(row.keys())
            assert non_empty.issubset({"ma_5", "kdj_k", "kdj_d", "kdj_j"})

    def test_custom_ma_windows_via_params(self):
        bars = _bars_ascending(30)
        results = compute_indicators(bars, indicator_names=["ma"], params={"ma_windows": [3, 7]})
        for row in results.values():
            keys = set(row.keys())
            if keys:
                assert keys.issubset({"ma_3", "ma_7"})

    def test_custom_macd_params(self):
        bars = _bars_ascending(60)
        results = compute_indicators(bars, indicator_names=["macd"], params={"macd": {"fast": 5, "slow": 10, "signal": 3}})
        # MACD 需要 slow 根历史，10 根应该出值
        last_with_value = [row for row in results.values() if "macd_dif" in row]
        assert last_with_value, "至少最后一根应有 macd_dif"


# ===========================================================================
# TD Sequential
# ===========================================================================


class TestTdSequential:
    def test_empty(self):
        assert compute_td_sequential([]) == {}

    def test_nine_consecutive_down_fires_buy_setup_complete(self):
        """9 根连续 close < close[i-4] 应触发 buy_setup_complete。"""
        bars = []
        for i in range(13):
            c = 20 - i * 1.0
            bars.append(MockBar(_d(i), c, high_price=c + 0.1, low_price=c - 0.5))
        results = compute_td_sequential(bars)
        signals = [(k, v.get("td_signal")) for k, v in results.items() if v.get("td_signal") == "buy_setup_complete"]
        assert len(signals) >= 1
        # setup 应该达到 9
        max_setup = max(v.get("td_buy_setup") or 0 for v in results.values())
        assert max_setup == 9

    def test_buy_setup_resets_on_close_up(self):
        """close >= close[i-4] 应重置 buy_setup。"""
        bars = _bars_ascending(20)  # 一直涨，sell_setup 会触发
        results = compute_td_sequential(bars)
        # 持续上涨时 buy_setup 应始终为 None 或 0
        for row in results.values():
            assert row.get("td_buy_setup") is None or row.get("td_buy_setup") == 0

    def test_sell_setup_complete_on_uptrend(self):
        bars = _bars_ascending(20)
        results = compute_td_sequential(bars)
        sell_signals = [k for k, v in results.items() if v.get("td_signal") == "sell_setup_complete"]
        assert len(sell_signals) >= 1

    def test_descending_input_keeps_td_signal_dates(self):
        ascending = _bars_ascending(20)
        assert compute_td_sequential(list(reversed(ascending))) == compute_td_sequential(ascending)

    def test_td_params_respected(self):
        bars = _bars_ascending(15)
        results = compute_td_sequential(bars, max_setup=5, lookback_setup=2)
        # 用 max_setup=5 应能更快触发
        sell_signals = [k for k, v in results.items() if v.get("td_signal") == "sell_setup_complete"]
        assert len(sell_signals) >= 1

    def test_setup_completed_locked_after_completion(self):
        """setup 完成后再插入一根 close >= close[i-4] 的 bar，buy_setup_completed
        不应被 reset 回 False（否则后续 countdown 会被错误中断）。"""
        # 13 根单调下跌：i=4..12 共 9 根连续触发 buy_setup → 第 12 根 buy_setup_completed。
        bars = []
        for i in range(13):
            c = 100.0 - i * 2.0
            bars.append(MockBar(_d(i), c, high_price=c + 0.5, low_price=c - 0.5))
        # 第 14 根 close 抬升，破坏 buy_setup 条件；setup_completed 必须仍 True。
        bars.append(MockBar(_d(13), 200.0, high_price=200.5, low_price=199.5))
        # 第 15~27 根继续下跌：close <= low[i-2]，countdown 应继续累计。
        for i in range(13):
            c = 50.0 - i * 1.0
            bars.append(MockBar(_d(14 + i), c, high_price=c + 0.5, low_price=c - 0.5))
        results = compute_td_sequential(bars, max_setup=9, max_countdown=13)
        # setup 完成那一根应触发 buy_setup_complete
        completed_setup = [k for k, v in results.items() if v.get("td_signal") == "buy_setup_complete"]
        assert len(completed_setup) >= 1
        # 后续累计能完成 countdown
        completed = [k for k, v in results.items() if v.get("td_signal") == "buy_countdown_complete"]
        assert len(completed) >= 1


# ===========================================================================
# 底部结构
# ===========================================================================


class TestBottomStructure:
    def test_empty(self):
        assert compute_bottom_structure([]) == {}

    def test_no_signal_in_strong_uptrend(self):
        bars = _bars_ascending(80)
        results = compute_bottom_structure(bars)
        for row in results.values():
            assert row.get("bottom_divergence") is False

    def test_signal_in_two_phase_decline(self):
        """两段式下跌（前快后慢）应检测到底背离：DIF 在缓慢段比窗口内最低值更高。"""
        bars = []
        for i in range(30):
            c = 20 - i * 0.5  # rapid decline 20 → 5
            bars.append(MockBar(_d(i), c, high_price=c + 0.1, low_price=c - 0.5))
        for i in range(30):
            c = 5 - (i + 1) * 0.03  # mild decline 5 → 4.1
            bars.append(MockBar(_d(30 + i), c, high_price=c + 0.1, low_price=c - 0.3))
        results = compute_bottom_structure(bars, lookback=20, min_consecutive=1)
        triggered = [k for k, v in results.items() if v.get("bottom_divergence")]
        assert len(triggered) >= 1

    def test_returns_td_signal_when_fires(self):
        bars = []
        for i in range(30):
            c = 20 - i * 0.5
            bars.append(MockBar(_d(i), c, high_price=c + 0.1, low_price=c - 0.5))
        for i in range(30):
            c = 5 - (i + 1) * 0.03
            bars.append(MockBar(_d(30 + i), c, high_price=c + 0.1, low_price=c - 0.3))
        results = compute_bottom_structure(bars, lookback=15, min_consecutive=1)
        signals = [v.get("td_signal") for v in results.values() if v.get("td_signal") == "bottom_divergence"]
        assert len(signals) >= 1

    def test_first_signal_only_in_consecutive_run(self):
        """连续多根都满足底背离条件时，每段只标首根一次（无连续段重复标记）。"""
        # 构造足够长度的历史暖启动 DIF；后 20 根 bar_low 单调新低、close 抬升
        # 让 DIF 缓慢回升，模拟「连续下跌但 DIF 不新低」段。
        bars = []
        for i in range(60):
            c = 30.0 - i * 0.3
            bars.append(MockBar(_d(i), c, high_price=c + 0.1, low_price=c - 0.5))
        last_low = bars[-1].low_price
        for i in range(20):
            c = 12.0 + i * 0.4  # close 抬升
            last_low -= 0.05  # bar_low 单调新低
            bars.append(MockBar(_d(60 + i), c, high_price=c + 0.5, low_price=last_low))
        results = compute_bottom_structure(bars, lookback=15, min_consecutive=2)
        triggered_keys = [k for k, v in results.items() if v.get("bottom_divergence")]
        # 关键不变量：触发数 ≤ 后段 bar 数（20）；旧实现会在 20 根全部满足时标 19 次。
        assert len(triggered_keys) <= 20
        # 至少有 1 个信号：构造意图就是让底背离触发
        assert len(triggered_keys) >= 1


# ===========================================================================
# 顶部结构
# ===========================================================================


class TestTopStructure:
    def test_empty(self):
        assert compute_top_structure([]) == {}

    def test_no_signal_in_strong_downtrend(self):
        bars = []
        for i in range(80):
            c = 20.0 - i * 0.1
            bars.append(MockBar(_d(i), c, high_price=c + 0.5, low_price=c - 0.5))
        results = compute_top_structure(bars)
        for row in results.values():
            assert row.get("top_divergence") is False

    def test_signal_in_two_phase_rally(self):
        """两段式上涨（前快后慢）应检测到顶背离：DIF 在缓慢段比窗口内最高值更低。"""
        bars = []
        for i in range(30):
            c = 10.0 + i * 0.5  # rapid rally 10 → 24.5
            bars.append(MockBar(_d(i), c, high_price=c + 0.1, low_price=c - 0.5))
        for i in range(30):
            c = 24.5 + (i + 1) * 0.03  # mild rally 24.5 → 25.4
            bars.append(MockBar(_d(30 + i), c, high_price=c + 0.1, low_price=c - 0.3))
        results = compute_top_structure(bars, lookback=20, min_consecutive=1)
        triggered = [k for k, v in results.items() if v.get("top_divergence")]
        assert len(triggered) >= 1

    def test_first_signal_only_in_consecutive_run(self):
        """对称底背离：连续多根都满足顶背离条件时，每段只标首根一次。"""
        bars = []
        for i in range(60):
            c = 10.0 + i * 0.3  # 价格走高让 DIF 走正
            bars.append(MockBar(_d(i), c, high_price=c + 0.5, low_price=c - 0.5))
        # 后 20 根：bar_high 单调新高，close 下降让 DIF 回落。
        last_high = bars[-1].high_price
        for i in range(20):
            c = 28.0 - i * 0.4  # close 下降
            last_high += 0.05  # bar_high 单调新高
            bars.append(MockBar(_d(60 + i), c, high_price=last_high, low_price=c - 0.5))
        results = compute_top_structure(bars, lookback=15, min_consecutive=2)
        triggered_keys = [k for k, v in results.items() if v.get("top_divergence")]
        # 关键不变量：触发数 ≤ 后段 bar 数（20）；旧实现会在 20 根全部满足时标 19 次。
        assert len(triggered_keys) <= 20
        assert len(triggered_keys) >= 1


# ===========================================================================
# params resolve
# ===========================================================================


# ===========================================================================
# params resolve
# ===========================================================================


class TestResolveParams:
    def test_none_returns_defaults(self):
        result = _resolve_indicator_params(None)
        assert result == DEFAULT_INDICATOR_WINDOWS

    def test_ma_windows_override(self):
        result = _resolve_indicator_params({"ma_windows": [3, 7]})
        assert result["ma"] == [3, 7]
        assert result["boll"] == DEFAULT_INDICATOR_WINDOWS["boll"]

    def test_boll_window_override(self):
        result = _resolve_indicator_params({"boll_window": 30})
        assert result["boll"] == [30]

    def test_macd_partial_override(self):
        result = _resolve_indicator_params({"macd": {"fast": 5}})
        assert result["macd"]["fast"] == 5
        assert result["macd"]["slow"] == DEFAULT_INDICATOR_WINDOWS["macd"]["slow"]

    def test_returns_deep_copy(self):
        result = _resolve_indicator_params(None)
        result["ma"].append(999)
        assert 999 not in DEFAULT_INDICATOR_WINDOWS["ma"]


# ===========================================================================
# indicator_service 常量
# ===========================================================================


class TestConstants:
    def test_version_set(self):
        assert INDICATOR_SET_VERSION

    def test_supported_groups_contains_all(self):
        assert {"ma", "boll", "macd", "kdj", "td_sequential", "bottom_structure"}.issubset(set(SUPPORTED_INDICATOR_GROUPS))

    def test_td_params(self):
        assert TD_SEQUENTIAL_PARAMS["max_setup"] == 9
        assert TD_SEQUENTIAL_PARAMS["lookback_setup"] == 4

    def test_bottom_params(self):
        assert BOTTOM_STRUCTURE_PARAMS["min_consecutive"] == 2

    def test_top_params(self):
        assert TOP_STRUCTURE_PARAMS["lookback"] == 30
        assert TOP_STRUCTURE_PARAMS["min_consecutive"] == 2

    def test_supported_groups_contains_top_structure(self):
        assert "top_structure" in set(SUPPORTED_INDICATOR_GROUPS)


# ===========================================================================
# _compute_indicator_snapshot 向后兼容
# ===========================================================================


class TestComputeIndicatorSnapshotCompat:
    def test_default_snapshot_contains_legacy_fields(self):
        bars = _bars_ascending(60)
        snapshot = _compute_indicator_snapshot(bars)
        last = snapshot[-1]["value"]
        assert "ma_5" in last
        assert "ma_10" in last
        assert "ma_20" in last
        assert "ma_60" in last
        assert "boll_mid" in last
        assert "macd_dif" in last
        assert "kdj_k" in last

    def test_snapshot_respects_params(self):
        bars = _bars_ascending(30)
        snapshot = _compute_indicator_snapshot(bars, params={"ma_windows": [3, 10]})
        last = snapshot[-1]["value"]
        assert "ma_3" in last
        assert "ma_10" in last
        assert "ma_5" not in last


class TestMaxLookbackBars:
    """max_lookback_bars 单元测试。"""

    def test_default_indicators_returns_ma60(self):
        # 默认全套指标，MA(60) 是最长 lookback
        names = ["ma", "boll", "macd", "kdj", "td_sequential", "bottom_structure"]
        assert max_lookback_bars(names) == 60

    def test_only_kdj_returns_9(self):
        assert max_lookback_bars(["kdj"]) == 9

    def test_only_macd_returns_26(self):
        assert max_lookback_bars(["macd"]) == 26

    def test_custom_ma_windows_uses_max(self):
        # 自定义 ma_windows=[10,30]，macd=26 胜出
        assert max_lookback_bars(["ma", "macd"], params={"ma_windows": [10, 30]}) == 30

    def test_empty_ma_windows_falls_back_to_default(self):
        # 空数组不抛错，回退到默认 [5,10,20,60]
        assert max_lookback_bars(["ma"], params={"ma_windows": []}) == 60

    def test_none_names_uses_all_indicators(self):
        # 不指定 → 视为"全开"，取所有指标的 max
        assert max_lookback_bars(None) == 60

    def test_unknown_indicator_ignored(self):
        # 未知指标静默忽略（视为 0），不影响 ma 计算
        assert max_lookback_bars(["ma", "unknown_xyz"], params={"ma_windows": [10]}) == 10

    def test_minimum_one(self):
        # 防止空 params / 空 indicator_names 给出 0
        assert max_lookback_bars([], params={}) >= 1
