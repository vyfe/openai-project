"""expr_llm_service 单元测试：确保 AI 提示词中指标列表与 registry 同步。

回归保护：新增/重命名指标后，AI 生成 expr 时应当自动看到该指标，无需手动改提示词模板。
"""
# indicator_registry 是惰性绑定：必须在 import indicator_service 后才会触发 _bind_registry()
# 把所有 indicator 写入 INDICATOR_REGISTRY dict。
from service.quant import indicator_service  # noqa: F401  触发 _bind_registry()
from service.quant import expr_llm_service as svc
from service.quant import indicator_registry as ireg


def test_build_indicator_list_contains_top_structure():
    """新增 top_structure 后，prompt 必须能列出 top_divergence 输出名。"""
    text = svc._build_indicator_list(["top_structure"])
    assert "top_structure" in text
    assert "top_divergence" in text
    assert "MACD 顶背离" in text


def test_build_indicator_list_contains_known_keys():
    """回归保护：现有指标（ma/rsi/bottom_structure 等）必须仍能列出。"""
    text = svc._build_indicator_list(["ma", "rsi", "bottom_structure", "top_structure"])
    assert "ma_5" in text  # 模板示例：ma_{window} → ma_5
    assert "rsi_5" in text  # 模板示例：rsi_{window} → rsi_5
    assert "bottom_divergence" in text
    assert "top_divergence" in text


def test_build_indicator_list_empty_returns_friendly_message():
    text = svc._build_indicator_list([])
    assert "未启用" in text or "bar 字段" in text


def test_build_indicator_list_unknown_key_ignored():
    """未知 key 应被静默忽略，不抛异常、不污染提示词。"""
    text = svc._build_indicator_list(["non_existent_key"])
    assert "non_existent_key" not in text


def test_catalog_payload_remains_source_of_truth():
    """catalog_payload() 是 LLM 提示词的唯一来源，必须含新指标。"""
    payload = ireg.catalog_payload()
    keys = {item["key"] for item in payload}
    assert "top_structure" in keys
    assert "bottom_structure" in keys
    # output 也必须在 catalog 里暴露
    top = next(p for p in payload if p["key"] == "top_structure")
    out_names = {o["name"] for o in top["outputs"]}
    assert "top_divergence" in out_names