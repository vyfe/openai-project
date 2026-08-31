from typing import Any, Dict, List, Optional, Tuple

from quant.entities import QuantDailyBar


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
