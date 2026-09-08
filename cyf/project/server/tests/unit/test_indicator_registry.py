"""indicator_registry 元数据一致性测试。"""
import pytest

from service.quant import indicator_registry as ireg
from service.quant import indicator_service as isvc
from routes.quant import data_routes


def _all_concrete_output_names():
    return data_routes._INDICATOR_FIELD_NAMES


def test_all_keys_registered():
    """registry 的 key 与 indicator_service 内部 hard-coded groups 一致。"""
    expected = {"ma", "boll", "macd", "kdj", "td_sequential", "bottom_structure", "top_structure",
                "vol_ratio", "period_return", "rolling_high_low",
                "rsi", "atr", "obv"}
    assert expected.issubset(set(ireg.all_keys()))


def test_base_lookback_matches_legacy():
    """registry base_lookback 与旧 INDICATOR_BASE_LOOKBACK 一致（不破坏 max_lookback_bars 行为）。"""
    assert ireg.get_spec("ma").base_lookback == 60
    assert ireg.get_spec("boll").base_lookback == 20
    assert ireg.get_spec("macd").base_lookback == 26
    assert ireg.get_spec("kdj").base_lookback == 9
    assert ireg.get_spec("td_sequential").base_lookback == 9
    assert ireg.get_spec("bottom_structure").base_lookback == 30
    assert ireg.get_spec("top_structure").base_lookback == 30


def test_max_lookback_unchanged_for_known_groups():
    """max_lookback_bars 数值与历史完全一致。"""
    # 显式为空 → 1
    assert isvc.max_lookback_bars([]) == 1
    # 全部 None → 取 max
    assert isvc.max_lookback_bars() == 60
    # 单个 ma
    assert isvc.max_lookback_bars(["ma"]) == 60
    # ma 自定义 windows
    assert isvc.max_lookback_bars(["ma"], {"ma_windows": [5, 30]}) == 30
    # macd
    assert isvc.max_lookback_bars(["macd"]) == 26


def test_concrete_output_names_includes_legacy_set():
    """_concrete_output_names 必须覆盖旧 _INDICATOR_FIELD_NAMES 的全部条目。"""
    legacy = {
        "ma_5", "ma_10", "ma_20", "ma_60",
        "boll_mid", "boll_upper", "boll_lower",
        "macd_dif", "macd_dea", "macd_bar",
        "kdj_k", "kdj_d", "kdj_j",
        "td_buy_setup", "td_buy_countdown",
        "td_sell_setup", "td_sell_countdown", "td_signal",
        "bottom_divergence",
        "top_divergence",
    }
    assert legacy.issubset(_all_concrete_output_names())


def test_top_structure_metadata():
    """top_structure 元数据：key/label/category/base_lookback/compute 绑定齐全。"""
    spec = ireg.get_spec("top_structure")
    assert spec.key == "top_structure"
    assert spec.category == "structure"
    assert spec.base_lookback == 30
    assert spec.compute is not None
    out_names = {o.name for o in spec.outputs}
    assert "top_divergence" in out_names


def test_new_indicators_rsi_atr_obv_concrete_outputs():
    """RSI/ATR/OBV 的默认参数展开必须出现在 _INDICATOR_FIELD_NAMES。"""
    names = _all_concrete_output_names()
    assert "rsi_14" in names
    assert "atr_14" in names
    assert "obv" in names


def test_new_indicators_rsi_atr_obv_metadata():
    """RSI/ATR/OBV 的 base_lookback / category / compute 绑定必须正确。"""
    rsi = ireg.get_spec("rsi")
    assert rsi.category == "momentum"
    assert rsi.base_lookback == 14
    assert rsi.compute is not None

    atr = ireg.get_spec("atr")
    assert atr.category == "volatility"
    assert atr.base_lookback == 14
    assert atr.compute is not None

    obv = ireg.get_spec("obv")
    assert obv.category == "volume"
    assert obv.base_lookback == 2
    assert obv.compute is not None


def test_max_lookback_for_new_indicators():
    """max_lookback_bars 对 RSI/ATR 必须返回 base_lookback，OBV 返回 2。"""
    assert isvc.max_lookback_bars(["rsi"]) == 14
    assert isvc.max_lookback_bars(["atr"]) == 14
    assert isvc.max_lookback_bars(["obv"]) == 2


def test_catalog_payload_shape():
    """catalog_payload 输出形态稳定。"""
    payload = ireg.catalog_payload()
    assert isinstance(payload, list)
    sample = next(p for p in payload if p["key"] == "ma")
    assert sample["category"] == "trend"
    assert any(p["name"] == "windows" for p in sample["params"])
    assert any("ma_" in o["name"] for o in sample["outputs"])


def test_registry_known_output_keys_actually_produced():
    """registry outputs 不能骗前端：compute_indicators 真要产出对应字段。"""
    from tests.unit.test_rule_engine import _make_history
    history = _make_history(10)
    asc = list(reversed(history))
    ctx = isvc.compute_indicators(asc)
    # 至少 ma_5 必须出现
    assert "ma_5" in {f for d in ctx.values() for f in d.keys()} or len(history) < 5


def test_new_indicators_compute_functions_work():
    """compute_vol_ratio / period_return / rolling_high_low 可调用并返回正确结构。"""
    from tests.unit.test_rule_engine import MockBar, _make_history
    history = _make_history(10)
    out = isvc.compute_vol_ratio(history, window=5)
    assert "vol_ratio_5" in out
    assert len(out["vol_ratio_5"]) == 10

    out = isvc.compute_period_return(history, lookback=5)
    assert "period_return_5" in out
    assert len(out["period_return_5"]) == 10

    out = isvc.compute_rolling_high_low(history, window=5)
    assert "rolling_high_5" in out
    assert "rolling_low_5" in out


def test_rolling_high_excludes_current_bar():
    """关键不变量：rolling_high_N 排除当前 bar，与 v1 _breakout_high 语义一致。"""
    from service.quant.indicator_service import compute_rolling_high_low
    from tests.unit.test_rule_engine import MockBar
    bars = [MockBar(close_price=12.0, high_price=30.0, low_price=30.0)] + [
        MockBar(close_price=20.0, high_price=20.0, low_price=19.7) for _ in range(5)
    ]
    # bars[0] 高 30（如果错误地包含当前 bar，会被选 max）；只看 bars[1..5] 的 high=20 → max=20
    out = compute_rolling_high_low(bars, window=5)
    assert out["rolling_high_5"][0] == 20.0
    assert out["rolling_low_5"][0] == 19.7


def test_vol_ratio_matches_v1_semantics():
    """vol_ratio 与 v1 _evaluate_one_rule.volume_ratio 在典型场景下数值一致。"""
    from service.quant.indicator_service import compute_vol_ratio
    from tests.unit.test_rule_engine import MockBar
    history = [MockBar(volume=500_000) for _ in range(6)]
    history[0] = MockBar(volume=3_000_000)
    out = compute_vol_ratio(history, window=5)
    # v1: avg(vol[1..5]) = 500000, cur=3000000, ratio=6.0
    assert abs(out["vol_ratio_5"][0] - 6.0) < 1e-9