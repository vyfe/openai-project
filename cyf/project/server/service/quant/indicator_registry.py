"""指标注册表 —— 指标元数据的唯一来源。

设计目标：
- 后端所有"有哪些指标、参数是什么、输出名是什么、最少需要多少 K 线"走这里。
- 前端 `/quant/meta/indicators` 接口直接序列化本模块的 registry 自动生成参数面板。
- 与 `indicator_service.compute_indicators` 一一对应；registry 里写的 output 必须在
  compute 后真的产出，否则单测 `test_indicator_registry.py` 会捕获漂移。

注意：
- 不要在这里写 if-elif 分派，那是 rule_engine 的事。registry 只描述"指标是什么"。
- 新增指标时，三个地方保持同步：register() 的 INDICATOR_REGISTRY 条目、compute 函数、
  以及对应的 _compute_indicators_* 调用路径（indicator_service）。
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Optional


@dataclass(frozen=True)
class ParamSpec:
    """单个参数规格。前端按 type 自动渲染对应表单控件。"""
    name: str
    label: str
    type: str  # "int" | "float" | "int_list" | "bool" | "enum"
    default: Any
    min: Optional[float] = None
    max: Optional[float] = None
    options: Optional[list] = None
    help: str = ""


@dataclass(frozen=True)
class OutputSpec:
    """指标产出名。name 可以是字面量 "macd_dif"，也可以是模板 "ma_{window}"。"""
    name: str
    label: str
    kind: str  # "numeric" | "bool" | "enum"


@dataclass(frozen=True)
class IndicatorSpec:
    """一个指标家族（如 ma、macd、vol_ratio）。

    compute 接受 (bars, params) -> {output_name: value_per_date}，
    其中 value_per_date 是 list[float|None]（与 bars 顺序对齐，新→旧 or 旧→新 均可，
    引擎统一按调用方传入的顺序使用）。
    """
    key: str
    label: str
    category: str  # "trend" | "momentum" | "volume" | "structure" | "volatility"
    params: tuple = ()
    outputs: tuple = ()
    base_lookback: int = 1
    compute: Optional[Callable] = None  # 惰性绑定：模块导入时 indicator_service 未必就绪


def _to_dict(obj):
    if isinstance(obj, (ParamSpec, OutputSpec, IndicatorSpec)):
        return asdict(obj)
    raise TypeError(f"unsupported: {type(obj)}")


# registry 是模块级 dict，indicator_service.compute_indicators 会读取；
# compute 函数绑定在 indicator_service._bind_compute_functions() 里注入。
INDICATOR_REGISTRY: dict[str, IndicatorSpec] = {}


def register(spec: IndicatorSpec) -> None:
    INDICATOR_REGISTRY[spec.key] = spec


def get(key: str) -> IndicatorSpec:
    return INDICATOR_REGISTRY[key]


def all_keys() -> list[str]:
    return list(INDICATOR_REGISTRY.keys())


def all_output_names(include_templates: bool = False) -> set[str]:
    """返回所有指标产出的字面输出名（不含模板）。

    include_templates=True 时也会返回 "ma_{window}" 这类模板字符串，供前端做模板识别。
    """
    names: set[str] = set()
    for spec in INDICATOR_REGISTRY.values():
        for out in spec.outputs:
            if include_templates or "{" not in out.name:
                names.add(out.name)
    return names


def all_groups() -> tuple[str, ...]:
    """所有指标 key（旧 SUPPORTED_INDICATOR_GROUPS 含义）。"""
    return tuple(INDICATOR_REGISTRY.keys())


def all_categories() -> tuple[str, ...]:
    """所有分类（trend/momentum/...），去重保序。"""
    seen: list[str] = []
    for spec in INDICATOR_REGISTRY.values():
        if spec.category not in seen:
            seen.append(spec.category)
    return tuple(seen)


def catalog_payload() -> list[dict]:
    """序列化给前端用。compute 函数不导出。"""
    payload: list[dict] = []
    for spec in INDICATOR_REGISTRY.values():
        item = {
            "key": spec.key,
            "label": spec.label,
            "category": spec.category,
            "base_lookback": spec.base_lookback,
            "params": [_to_dict(p) for p in spec.params],
            "outputs": [_to_dict(o) for o in spec.outputs],
        }
        payload.append(item)
    return payload


def get_spec(key: str) -> IndicatorSpec:
    if key not in INDICATOR_REGISTRY:
        raise KeyError(f"未注册的指标: {key}")
    return INDICATOR_REGISTRY[key]


def params_from_spec(spec: IndicatorSpec, params: Optional[dict]) -> dict:
    """把用户传入的 params 与 spec.defaults 合并，缺位填默认。"""
    out: dict[str, Any] = {}
    for p in spec.params:
        if p.type == "int_list":
            out[p.name] = list(p.default)
        else:
            out[p.name] = p.default
    if params:
        for k, v in params.items():
            if any(p.name == k for p in spec.params):
                out[k] = v
    return out