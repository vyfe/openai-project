import copy
import ast
from typing import Any, Dict, List, Optional, Tuple

from quant.entities import QuantDailyBar
from service.quant import indicator_registry as ireg
from service.quant.expression_engine import (
    ExpressionError,
    SeriesView,
    compile_expression,
    evaluate as eval_expression,
)
from service.quant.rule_migration import migrate_v1_to_v2
from service.quant import indicator_service as isvc


SUPPORTED_OPERATORS = {
    ">": lambda a, b: a is not None and a > b,
    ">=": lambda a, b: a is not None and a >= b,
    "<": lambda a, b: a is not None and a < b,
    "<=": lambda a, b: a is not None and a <= b,
    "==": lambda a, b: a is not None and a == b,
}

INDICATOR_RULE_TYPES = {
    "macd_golden_cross",
    "macd_death_cross",
    "kdj_golden_cross",
    "kdj_death_cross",
    "td_buy_setup_complete",
    "td_sell_setup_complete",
    "bottom_divergence",
}

INDICATOR_HISTORY_SIZES = {
    "macd_golden_cross": 2,
    "macd_death_cross": 2,
    "kdj_golden_cross": 2,
    "kdj_death_cross": 2,
    "td_buy_setup_complete": 30,
    "td_sell_setup_complete": 30,
    "bottom_divergence": 60,
}


def _avg(values: List[Optional[float]]) -> Optional[float]:
    cleaned = [float(item) for item in values if item is not None]
    if not cleaned:
        return None
    return sum(cleaned) / len(cleaned)


def _safe_ratio(numerator: Optional[float], denominator: Optional[float]) -> Optional[float]:
    if numerator is None or denominator in (None, 0):
        return None
    return numerator / denominator


def _get_current_field(current_bar: QuantDailyBar, field_name: str) -> Optional[float]:
    return getattr(current_bar, field_name, None)


def _ma(history: List[QuantDailyBar], window: int, field_name: str = "close_price") -> Optional[float]:
    sample = history[:window]
    return _avg([getattr(item, field_name, None) for item in sample])


def _period_return(history: List[QuantDailyBar], lookback: int) -> Optional[float]:
    if len(history) <= lookback:
        return None
    current_close = history[0].close_price
    past_close = history[lookback].close_price
    if current_close is None or past_close in (None, 0):
        return None
    return (current_close - past_close) / past_close * 100


def _breakout_high(history: List[QuantDailyBar], window: int) -> Optional[float]:
    if len(history) <= window:
        return None
    previous_highs = [item.high_price for item in history[1 : window + 1] if item.high_price is not None]
    if not previous_highs:
        return None
    return max(previous_highs)


def _date_key(date_value) -> str:
    if hasattr(date_value, "isoformat"):
        return date_value.isoformat()
    return str(date_value) if date_value is not None else ""


def _indicator_lookup(indicator_context: Optional[Dict[str, Dict[str, Any]]], bar: QuantDailyBar, name: str) -> Any:
    if not indicator_context:
        return None
    return indicator_context.get(_date_key(bar.trade_date), {}).get(name)


def _evaluate_macd_cross(rule_type: str, current_bar: QuantDailyBar, history: List[QuantDailyBar], indicator_context: Optional[Dict[str, Dict[str, Any]]]) -> Tuple[bool, Dict[str, Any], str]:
    is_golden = rule_type == "macd_golden_cross"
    cur_dif = _indicator_lookup(indicator_context, current_bar, "macd_dif")
    cur_dea = _indicator_lookup(indicator_context, current_bar, "macd_dea")
    if len(history) < 2:
        return False, {"dif": cur_dif, "dea": cur_dea}, rule_type
    prev_bar = history[1]
    prev_dif = _indicator_lookup(indicator_context, prev_bar, "macd_dif")
    prev_dea = _indicator_lookup(indicator_context, prev_bar, "macd_dea")
    if None in (cur_dif, cur_dea, prev_dif, prev_dea):
        return False, {"dif": cur_dif, "dea": cur_dea}, rule_type
    passed = (prev_dif <= prev_dea and cur_dif > cur_dea) if is_golden else (prev_dif >= prev_dea and cur_dif < cur_dea)
    metrics = {"dif": cur_dif, "dea": cur_dea, "prev_dif": prev_dif, "prev_dea": prev_dea, "cross": "golden" if is_golden else "death"}
    return passed, metrics, rule_type


def _evaluate_kdj_cross(rule_type: str, current_bar: QuantDailyBar, history: List[QuantDailyBar], indicator_context: Optional[Dict[str, Dict[str, Any]]]) -> Tuple[bool, Dict[str, Any], str]:
    is_golden = rule_type == "kdj_golden_cross"
    cur_k = _indicator_lookup(indicator_context, current_bar, "kdj_k")
    cur_d = _indicator_lookup(indicator_context, current_bar, "kdj_d")
    if len(history) < 2:
        return False, {"k": cur_k, "d": cur_d}, rule_type
    prev_bar = history[1]
    prev_k = _indicator_lookup(indicator_context, prev_bar, "kdj_k")
    prev_d = _indicator_lookup(indicator_context, prev_bar, "kdj_d")
    if None in (cur_k, cur_d, prev_k, prev_d):
        return False, {"k": cur_k, "d": cur_d}, rule_type
    passed = (prev_k <= prev_d and cur_k > cur_d) if is_golden else (prev_k >= prev_d and cur_k < cur_d)
    metrics = {"k": cur_k, "d": cur_d, "prev_k": prev_k, "prev_d": prev_d, "cross": "golden" if is_golden else "death"}
    return passed, metrics, rule_type


def _evaluate_td_setup_complete(rule_type: str, current_bar: QuantDailyBar, indicator_context: Optional[Dict[str, Dict[str, Any]]]) -> Tuple[bool, Dict[str, Any], str]:
    is_buy = rule_type == "td_buy_setup_complete"
    signal = _indicator_lookup(indicator_context, current_bar, "td_signal")
    expected = "buy_setup_complete" if is_buy else "sell_setup_complete"
    passed = signal == expected
    metrics = {"signal": signal, "expected": expected}
    return passed, metrics, rule_type


def _evaluate_bottom_divergence(rule_type: str, current_bar: QuantDailyBar, indicator_context: Optional[Dict[str, Dict[str, Any]]]) -> Tuple[bool, Dict[str, Any], str]:
    signal = _indicator_lookup(indicator_context, current_bar, "td_signal")
    bottom_flag = _indicator_lookup(indicator_context, current_bar, "bottom_divergence")
    passed = bool(signal == "bottom_divergence" or bottom_flag)
    metrics = {"signal": signal, "bottom_divergence": bottom_flag}
    return passed, metrics, rule_type


def _evaluate_one_rule(rule: Dict[str, Any], current_bar: QuantDailyBar, history: List[QuantDailyBar], indicator_context: Optional[Dict[str, Dict[str, Any]]] = None) -> Tuple[bool, Dict[str, Any], str]:
    rule_type = str(rule.get("rule_type", rule.get("type", ""))).strip()
    label = str(rule.get("label", rule_type or "rule")).strip()
    operator = str(rule.get("operator", ">=")).strip()
    if operator not in SUPPORTED_OPERATORS:
        raise ValueError(f"不支持的 operator: {operator}")
    compare_fn = SUPPORTED_OPERATORS[operator]

    if rule_type == "field_compare":
        field_name = str(rule.get("field", "")).strip()
        expected = float(rule.get("value"))
        actual = _get_current_field(current_bar, field_name)
        passed = compare_fn(actual, expected)
        return passed, {"actual": actual, "expected": expected, "field": field_name, "operator": operator}, label

    if rule_type == "close_above_ma":
        window = int(rule.get("window", 5))
        expected = _ma(history, window)
        actual = current_bar.close_price
        passed = actual is not None and expected is not None and actual > expected
        return passed, {"actual": actual, "expected": expected, "window": window, "operator": ">"}, label

    if rule_type == "close_below_ma":
        window = int(rule.get("window", 5))
        expected = _ma(history, window)
        actual = current_bar.close_price
        passed = actual is not None and expected is not None and actual < expected
        return passed, {"actual": actual, "expected": expected, "window": window, "operator": "<"}, label

    if rule_type == "volume_ratio":
        window = int(rule.get("window", 5))
        expected = float(rule.get("value"))
        avg_volume = _avg([item.volume for item in history[1 : window + 1]])
        actual = _safe_ratio(current_bar.volume, avg_volume)
        passed = compare_fn(actual, expected)
        return passed, {"actual": actual, "expected": expected, "window": window, "operator": operator}, label

    if rule_type == "period_return":
        lookback = int(rule.get("lookback", 5))
        expected = float(rule.get("value"))
        actual = _period_return(history, lookback)
        passed = compare_fn(actual, expected)
        return passed, {"actual": actual, "expected": expected, "lookback": lookback, "operator": operator}, label

    if rule_type == "breakout_high":
        window = int(rule.get("window", 20))
        breakout_line = _breakout_high(history, window)
        actual = current_bar.close_price
        passed = actual is not None and breakout_line is not None and actual > breakout_line
        return passed, {"actual": actual, "expected": breakout_line, "window": window, "operator": ">"}, label

    if rule_type in ("macd_golden_cross", "macd_death_cross"):
        return _evaluate_macd_cross(rule_type, current_bar, history, indicator_context)

    if rule_type in ("kdj_golden_cross", "kdj_death_cross"):
        return _evaluate_kdj_cross(rule_type, current_bar, history, indicator_context)

    if rule_type in ("td_buy_setup_complete", "td_sell_setup_complete"):
        return _evaluate_td_setup_complete(rule_type, current_bar, indicator_context)

    if rule_type == "bottom_divergence":
        return _evaluate_bottom_divergence(rule_type, current_bar, indicator_context)

    raise ValueError(f"不支持的规则类型: {rule_type}")


def get_required_history_size(rule_config: Dict[str, Any]) -> int:
    size = 1
    for rule in rule_config.get("rules", []):
        rule_type = str(rule.get("rule_type", rule.get("type", ""))).strip()
        if rule_type in ("close_above_ma", "close_below_ma"):
            size = max(size, int(rule.get("window", 5)))
        elif rule_type == "volume_ratio":
            size = max(size, int(rule.get("window", 5)) + 1)
        elif rule_type == "period_return":
            size = max(size, int(rule.get("lookback", 5)) + 1)
        elif rule_type == "breakout_high":
            size = max(size, int(rule.get("window", 20)) + 1)
        elif rule_type in INDICATOR_RULE_TYPES:
            size = max(size, INDICATOR_HISTORY_SIZES[rule_type])
    return size


def evaluate_strategy_rules(rule_config: Dict[str, Any], history: List[QuantDailyBar], indicator_context: Optional[Dict[str, Dict[str, Any]]] = None) -> Dict[str, Any]:
    if not history:
        return {
            "passed": False,
            "score": 0.0,
            "signal_type": str(rule_config.get("signal_type", "watch") or "watch"),
            "reasons": ["无行情数据"],
            "metrics": {},
        }

    current_bar = history[0]
    logic = str(rule_config.get("logic", "all") or "all").strip().lower()
    min_score = float(rule_config.get("min_score", 0) or 0)
    signal_type = str(rule_config.get("signal_type", "watch") or "watch")
    rules = rule_config.get("rules") or []

    if not isinstance(rules, list) or not rules:
        return {
            "passed": False,
            "score": 0.0,
            "signal_type": signal_type,
            "reasons": ["未配置规则"],
            "metrics": {},
        }

    evaluations = []
    score = 0.0
    for rule in rules:
        passed, metrics, label = _evaluate_one_rule(rule, current_bar, history, indicator_context=indicator_context)
        weight = float(rule.get("weight", 1) or 1)
        if passed:
            score += weight
        evaluations.append(
            {
                "label": label,
                "passed": passed,
                "metrics": metrics,
                "weight": weight,
            }
        )

    pass_flags = [item["passed"] for item in evaluations]
    if logic == "any":
        passed = any(pass_flags)
    else:
        passed = all(pass_flags)

    passed = passed and score >= min_score
    reasons = [
        f"{item['label']}: {'通过' if item['passed'] else '未通过'}"
        for item in evaluations
    ]
    metrics = {
        "trade_date": current_bar.trade_date.isoformat() if current_bar.trade_date else None,
        "close_price": current_bar.close_price,
        "pct_change": current_bar.pct_change,
        "turnover_rate": current_bar.turnover_rate,
        "rules": evaluations,
    }
    return {
        "passed": passed,
        "score": score,
        "signal_type": signal_type,
        "reasons": reasons,
        "metrics": metrics,
    }


# ===========================================================================
# v2 路径：表达式引擎 + 注册表驱动的指标计算
# ===========================================================================
# 与 v1 的区别：
# - 不再有 if-elif 分派；规则统一为 "expr" 字符串，走 expression_engine 求值。
# - bar 字段 + 注册表指标的产出序列一次性构建，逐 bar 求表达式。
# - 输出 metrics.rules[].metrics 与 v1 形态一致（含 'value' 字段供 IDE 显示实际数值）。
# ===========================================================================

# 当前 v1 metrics dict 内常用的 key；v2 内置一份以保留格式。
_V2_BAR_FIELD_NAMES = (
    "open_price", "high_price", "low_price", "close_price",
    "volume", "amount", "pct_change", "turnover_rate",
)

# 别名：用户写 `close` 就当 close_price；这是表达式语法的甜头，
# 配套声明在 catalog payload 里供前端 IDE 提示。
_V2_BAR_FIELD_ALIASES = {
    "open": "open_price",
    "high": "high_price",
    "low": "low_price",
    "close": "close_price",
    "vol": "volume",
    "amt": "amount",
    "pct": "pct_change",
    "turnover": "turnover_rate",
}


def _v2_indicator_name_is_ma(name: str) -> bool:
    """indicator_context 里 ma 字段以 ma_ 形式给出（ma_5/ma_10/...）。"""
    return name.startswith("ma_")


def _v2_extract_indicator_names_from_expr(expr: str) -> set[str]:
    """从表达式提取被引用的所有指标名（包括 ma_5、macd_dif、rolling_high_20、td_signal、bottom_divergence 等）。"""
    try:
        tree = compile_expression(expr)
    except ExpressionError:
        return set()
    used: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id not in _V2_BAR_FIELD_NAMES:
            used.add(node.id)
        elif isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name):
            used.add(node.value.id)
        elif isinstance(node, ast.Call):
            for a in node.args:
                if isinstance(a, ast.Name):
                    used.add(a.id)
    return used


def _v2_extract_params_from_expr(expr: str) -> Dict[str, Dict[str, Any]]:
    """从 expr 提取参数化指标的 window/lookback 等具体值。

    例：`vol_ratio_10` → {vol_ratio: {window: 10}}，`period_return_5` → {period_return: {lookback: 5}}，
        `rolling_high_20` → {rolling_high_low: {window: 20}}，`ma_5` → {ma: {windows: [5]}}。

    返回的 dict 在 evaluate_series 中用于覆盖 v2_cfg.indicators 里的 params。
    """
    try:
        tree = compile_expression(expr)
    except ExpressionError:
        return {}
    out: Dict[str, Dict[str, Any]] = {}
    for node in ast.walk(tree):
        names = []
        if isinstance(node, ast.Name):
            names.append(node.id)
        elif isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name):
            names.append(node.value.id)
        elif isinstance(node, ast.Call):
            for a in node.args:
                if isinstance(a, ast.Name):
                    names.append(a.id)
        for name in names:
            m = _PARAM_NAME_PATTERNS["ma"].match(name)
            if m and "ma" not in out:
                w = int(m.group(1))
                out["ma"] = {"windows": [w]}
            m = _PARAM_NAME_PATTERNS["vol_ratio"].match(name)
            if m and "vol_ratio" not in out:
                out["vol_ratio"] = {"window": int(m.group(1))}
            m = _PARAM_NAME_PATTERNS["period_return"].match(name)
            if m and "period_return" not in out:
                out["period_return"] = {"lookback": int(m.group(1))}
            m = _PARAM_NAME_PATTERNS["rolling_high_low"].match(name)
            if m and "rolling_high_low" not in out:
                out["rolling_high_low"] = {"window": int(m.group(1))}
            m = _PARAM_NAME_PATTERNS["rsi"].match(name)
            if m and "rsi" not in out:
                out["rsi"] = {"window": int(m.group(1))}
            m = _PARAM_NAME_PATTERNS["atr"].match(name)
            if m and "atr" not in out:
                out["atr"] = {"window": int(m.group(1))}
    return out


import re as _re
_PARAM_NAME_PATTERNS = {
    "ma": _re.compile(r"^ma_(\d+)$"),
    "vol_ratio": _re.compile(r"^vol_ratio_(\d+)$"),
    "period_return": _re.compile(r"^period_return_(\d+)$"),
    "rolling_high_low": _re.compile(r"^rolling_(?:high|low)_(\d+)$"),
    "rsi": _re.compile(r"^rsi_(\d+)$"),
    "atr": _re.compile(r"^atr_(\d+)$"),
}


def _v2_resolve_indicator_keys(used_names: set[str]) -> set[str]:
    """把 expr 引用的输出名（ma_5、macd_dif、vol_ratio_10 等）映射回 registry key。

    规则：
    - ma_{w} / boll_{mid|upper|lower} / macd_{...} / kdj_{...} / td_*
      / bottom_divergence → 走 compute_indicators 的统一入口（key 由前缀决定）
    - vol_ratio_{w} / period_return_{lb} / rolling_high_{w} / rolling_low_{w}
      → 走 registry.compute
    """
    keys: set[str] = set()
    for name in used_names:
        if name in ireg.INDICATOR_REGISTRY:
            keys.add(name)
            continue
        if name.startswith("ma_"):
            keys.add("ma")
        elif name.startswith("boll_"):
            keys.add("boll")
        elif name.startswith("macd_"):
            keys.add("macd")
        elif name.startswith("kdj_"):
            keys.add("kdj")
        elif name.startswith("td_"):
            keys.add("td_sequential")
        elif name == "bottom_divergence":
            keys.add("bottom_structure")
        elif name.startswith("vol_ratio_"):
            keys.add("vol_ratio")
        elif name.startswith("period_return_"):
            keys.add("period_return")
        elif name.startswith("rolling_high_") or name.startswith("rolling_low_"):
            keys.add("rolling_high_low")
        elif name.startswith("rsi_"):
            keys.add("rsi")
        elif name.startswith("atr_"):
            keys.add("atr")
    return keys


def _v2_new_indicator_names(v2_cfg: Dict[str, Any]) -> set[str]:
    """从 v2 rules.indicators / expressions 推出需要算的指标 key 集合。"""
    from service.quant.indicator_registry import INDICATOR_REGISTRY
    out: set[str] = set()
    declared = v2_cfg.get("indicators") or []
    for ind in declared:
        if not isinstance(ind, dict):
            continue
        key = str(ind.get("key") or "").strip()
        if key:
            out.add(key)
    used_names: set[str] = set()
    for rule in v2_cfg.get("rules") or []:
        if not isinstance(rule, dict):
            continue
        used_names.update(_v2_extract_indicator_names_from_expr(str(rule.get("expr") or "")))
    out |= _v2_resolve_indicator_keys(used_names)
    return out


def _v2_compute_new_indicators(bars_desc: List[QuantDailyBar], new_keys: set[str], v2_cfg: Optional[Dict[str, Any]] = None, expr_params: Optional[Dict[str, Dict[str, Any]]] = None) -> Dict[str, List]:
    """调用 registry 注册的 compute 函数，统一输出为 {output_name: list[desc]}。

    bars_desc 是新→旧顺序（与 evaluate_strategy_rules 约定一致）。
    compute 函数返回的 list 与输入 bars 顺序对齐，所以这里直接消费。

    params 解析优先级：
      1. v2_cfg.indicators 显式声明
      2. expr_params（从 expr 变量名提取的 window/lookback）
      3. registry 默认
    """
    out: Dict[str, List] = {}
    declared_map: Dict[str, Dict[str, Any]] = {}
    for ind in (v2_cfg or {}).get("indicators") or []:
        if isinstance(ind, dict) and ind.get("key"):
            declared_map[str(ind["key"]).strip()] = ind.get("params") or {}
    expr_params = expr_params or {}
    for key in new_keys:
        if key not in ireg.INDICATOR_REGISTRY:
            continue
        spec = ireg.INDICATOR_REGISTRY[key]
        if not spec.compute:
            continue
        kwargs: Dict[str, Any] = {}
        user_params = {**(expr_params.get(key) or {}), **(declared_map.get(key) or {})}
        for p in spec.params:
            kwargs[p.name] = user_params.get(p.name, p.default)
        out.update(spec.compute(bars_desc, **kwargs))
    return out


def _v2_indicator_series_from_context(bars_desc: List[QuantDailyBar], indicator_context: Optional[Dict[str, Dict[str, Any]]]) -> Dict[str, List]:
    """从 indicator_context（{date_key: {field: value}}）按 bars_desc 顺序抽出每个字段的降序 list。

    字段名来源：
      1. registry 中所有字面 output 名（即使 indicator_context 里没有也建一个全 None 序列，
         避免 expr 引用"今天恰好没产出"的字段时报"未知变量"）
      2. indicator_context 里实际出现的所有字段

    缺位的字段填充 None（与 None 传播规则一致）。
    """
    all_fields: set[str] = set()
    for spec in ireg.INDICATOR_REGISTRY.values():
        for out in spec.outputs:
            if "{" not in out.name:
                all_fields.add(out.name)
    if indicator_context:
        for row in indicator_context.values():
            if isinstance(row, dict):
                all_fields.update(row.keys())
    out: Dict[str, List] = {}
    for field in sorted(all_fields):
        out[field] = [_indicator_lookup(indicator_context, bar, field) for bar in bars_desc]
    return out


def _v2_evaluate_rule(rule: Dict[str, Any], view: SeriesView) -> Tuple[bool, Dict[str, Any], str]:
    """求值单条 v2 规则，返回 (passed, metrics_dict, label)。"""
    label = str(rule.get("label") or rule.get("id") or "rule").strip()
    expr_text = str(rule.get("expr") or "").strip()
    if not expr_text:
        return False, {"error": "表达式为空"}, label
    try:
        tree = compile_expression(expr_text)
    except ExpressionError as exc:
        return False, {"error": str(exc)}, label
    try:
        value = eval_expression(tree, view)
    except ExpressionError as exc:
        return False, {"error": str(exc)}, label
    if value is None:
        return False, {"value": None, "reason": "数据预热期或表达式求值为 None"}, label
    passed = bool(value)
    return passed, {"value": value}, label


def _v2_apply_gate(rule_evaluations: List[Dict[str, Any]], gate: Dict[str, Any]) -> Tuple[bool, bool]:
    """根据 gate 决定 passed：返回 (passed, is_or)。

    gate.mode: "all" | "any" | "expr"
    gate.expr 仅在 mode=="expr" 时使用，引用 rule id。
    """
    from service.quant.expression_engine import _Evaluator

    mode = str(gate.get("mode", "all") or "all").strip().lower()
    flags = [item["passed"] for item in rule_evaluations]
    id_map = {item["id"]: item for item in rule_evaluations if item.get("id")}

    if mode == "any":
        return (any(flags) if flags else False), True
    if mode == "expr":
        expr_text = str(gate.get("expr") or "").strip()
        if not expr_text:
            return False, False
        try:
            tree = compile_expression(expr_text)
        except ExpressionError:
            return False, False
        new_tree = copy.deepcopy(tree)
        for n in ast.walk(new_tree):
            if isinstance(n, ast.Name) and n.id in id_map:
                _replace_with_constant(n, bool(id_map[n.id]["passed"]))
        try:
            v = _Evaluator(SeriesView({}, 0), {}).eval(new_tree)
        except ExpressionError:
            return False, False
        if v is None:
            return False, False
        return bool(v), False
    # default: all
    return (all(flags) if flags else False), False


def _replace_with_constant(node, value):
    """把 AST Name 节点原地替换为 Constant（用于 gate.expr 求值）。"""
    node.__class__ = ast.Constant
    node.value = value
    node.id = None
    node.ctx = None


def evaluate_series(rule_config: Dict[str, Any], bars_desc: List[QuantDailyBar], indicator_context: Optional[Dict[str, Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    """v2 路径入口：对 bars_desc（新→旧）逐根求值。

    返回 list，长度 = len(bars_desc)，每项是 {passed, score, signal_type, reasons, metrics}，
    其中 reasons/metrics 与 v1 形态一致，便于上层拼接。

    当调用方不提供 indicator_context 时，本函数会按"用得到的"原则自动调用 compute_indicators
    计算默认 6 组指标；上层也可显式提供以复用缓存或限定计算范围。
    """
    v2 = rule_config if rule_config.get("version") == 2 else migrate_v1_to_v2(rule_config)
    n = len(bars_desc)
    if n == 0:
        return [{
            "passed": False,
            "score": 0.0,
            "signal_type": str(v2.get("signal_type", "watch") or "watch"),
            "reasons": ["无行情数据"],
            "metrics": {},
        }]

    rules = v2.get("rules") or []
    signal_type = str(v2.get("signal_type") or "watch")
    min_score = float(v2.get("min_score", 0) or 0)
    gate = v2.get("gate") or {"mode": v2.get("logic", "all") or "all"}

    # 1. 准备 bar 字段序列（含别名 close/open/high/low/vol/...）
    bar_series: Dict[str, List] = {}
    for f in _V2_BAR_FIELD_NAMES:
        bar_series[f] = [getattr(bar, f, None) for bar in bars_desc]
    for alias, real in _V2_BAR_FIELD_ALIASES.items():
        bar_series[alias] = bar_series[real]

    # 2. 推断需要哪些 registry key，按 key 分桶
    needed_keys = _v2_new_indicator_names(v2)
    legacy_keys = needed_keys & {"ma", "boll", "macd", "kdj", "td_sequential", "bottom_structure"}
    compute_keys = needed_keys - legacy_keys  # vol_ratio / period_return / rolling_high_low

    # 3. 若需要 legacy 指标且没传 indicator_context，自动 compute_indicators 兜底
    if legacy_keys and not indicator_context:
        asc_bars = list(reversed(bars_desc))
        indicator_context = isvc.compute_indicators(asc_bars, indicator_names=sorted(legacy_keys))

    # 4. 准备 indicator_context 序列
    ind_ctx_series = _v2_indicator_series_from_context(bars_desc, indicator_context)

    # 5. 准备新指标序列（params 从 expr 变量名 + v2_cfg.indicators 合并）
    expr_params: Dict[str, Dict[str, Any]] = {}
    for rule in rules:
        if isinstance(rule, dict):
            expr_params.update(_v2_extract_params_from_expr(str(rule.get("expr") or "")))
    new_indicator_series = _v2_compute_new_indicators(bars_desc, compute_keys, v2_cfg=v2, expr_params=expr_params)

    # 6. 预编译每条规则的表达式（避免循环里重复 compile）
    compiled_rules: List[Dict[str, Any]] = []
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        rid = str(rule.get("id") or "")
        try:
            tree = compile_expression(str(rule.get("expr") or ""))
        except ExpressionError as exc:
            compiled_rules.append({
                "id": rid,
                "label": str(rule.get("label") or rid),
                "weight": float(rule.get("weight", 1) or 1),
                "tree": None,
                "error": str(exc),
            })
        else:
            compiled_rules.append({
                "id": rid,
                "label": str(rule.get("label") or rid),
                "weight": float(rule.get("weight", 1) or 1),
                "tree": tree,
                "error": None,
            })

    # 7. 逐 bar 求值
    results: List[Dict[str, Any]] = []
    for idx in range(n):
        seqs: Dict[str, List] = {}
        seqs.update(bar_series)
        seqs.update(ind_ctx_series)
        seqs.update(new_indicator_series)
        view = SeriesView(seqs, idx)
        evaluations = []
        score = 0.0
        for cr in compiled_rules:
            if cr["tree"] is None:
                passed, m = False, {"error": cr["error"]}
            else:
                try:
                    value = eval_expression(cr["tree"], view)
                except ExpressionError as exc:
                    passed, m = False, {"error": str(exc)}
                else:
                    if value is None:
                        passed, m = False, {"value": None, "reason": "预热期或求值为 None"}
                    else:
                        passed = bool(value)
                        m = {"value": value}
            if passed:
                score += cr["weight"]
            evaluations.append({
                "id": cr["id"],
                "label": cr["label"],
                "passed": passed,
                "metrics": m,
                "weight": cr["weight"],
            })

        passed_gate, _ = _v2_apply_gate(evaluations, gate)
        passed = passed_gate and score >= min_score
        reasons = [
            f"{e['label']}: {'通过' if e['passed'] else '未通过'}" for e in evaluations
        ]
        cur_bar = bars_desc[idx]
        metrics = {
            "trade_date": cur_bar.trade_date.isoformat() if cur_bar.trade_date else None,
            "close_price": getattr(cur_bar, "close_price", None),
            "pct_change": getattr(cur_bar, "pct_change", None),
            "turnover_rate": getattr(cur_bar, "turnover_rate", None),
            "rules": evaluations,
        }
        results.append({
            "passed": passed,
            "score": score,
            "signal_type": signal_type,
            "reasons": reasons,
            "metrics": metrics,
        })
    return results


def get_required_history_size_v2(rule_config: Dict[str, Any]) -> int:
    """v2 配置的历史窗口大小：从 registry.indicators 与 expr 引用推出。"""
    v2 = rule_config if rule_config.get("version") == 2 else migrate_v1_to_v2(rule_config)
    declared = v2.get("indicators") or []
    size = 1
    for ind in declared:
        if not isinstance(ind, dict):
            continue
        key = str(ind.get("key") or "").strip()
        if not key:
            continue
        try:
            spec = ireg.get_spec(key)
        except KeyError:
            continue
        # base_lookback 已经隐含在 spec.params 的 default 里；不再加一次。
        max_w = 0
        user_params = ind.get("params") or {}
        for p in spec.params:
            if p.type in ("int", "int_list"):
                v = user_params.get(p.name, p.default)
                if isinstance(v, list):
                    if v:
                        max_w = max(max_w, max(v))
                elif isinstance(v, (int, float)):
                    max_w = max(max_w, int(v))
        size = max(size, max_w)
    used_names: set[str] = set()
    for rule in v2.get("rules") or []:
        if not isinstance(rule, dict):
            continue
        used_names.update(_v2_extract_indicator_names_from_expr(str(rule.get("expr") or "")))
    for key in _v2_resolve_indicator_keys(used_names):
        try:
            size = max(size, ireg.get_spec(key).base_lookback)
        except KeyError:
            pass
    return size
