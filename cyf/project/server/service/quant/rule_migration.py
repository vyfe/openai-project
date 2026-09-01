"""rule_config v1 → v2 读时迁移。

设计目标：
- 用户库里 strategy 4 的 rule_config_json（13 种 rule_type 的 if-elif 形态）
  在不修改 DB 的前提下，读取时自动转成 v2 表达式形态。
- 迁移等价性（硬门槛）：对同一批 bars，evaluate_strategy_rules(v1)
  与 evaluate_series(migrate(v1))[-1] 的 passed/score 必须完全一致。
- 迁移是幂等的：v2 配置再次走 migrate 不应改变。

接入门户：strategy_service._normalize_rule_config 检测 version == 2 缺失就走迁移。
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional


def _normalize_operator(op: str) -> str:
    """v1 中 '<>' 与 '=' 等价物没有，归一化 ==/!=/>/>=/</<= 的字符串。"""
    if not op:
        return ">="
    return str(op).strip()


def _next_rule_id(used: set) -> str:
    """生成不冲突的规则 id（r1, r2, ...）。"""
    for i in range(1, 1000):
        cand = f"r{i}"
        if cand not in used:
            used.add(cand)
            return cand
    return f"r{uuid.uuid4().hex[:6]}"


def _migrate_field_compare(rule: Dict[str, Any], rid: str) -> Dict[str, Any]:
    field = str(rule.get("field") or "").strip()
    op = _normalize_operator(rule.get("operator", ">="))
    value = rule.get("value", 0)
    label = str(rule.get("label") or f"{field} {op} {value}").strip()
    return {
        "id": rid,
        "label": label,
        "expr": f"{field} {op} {value}",
        "weight": float(rule.get("weight", 1) or 1),
    }


def _migrate_close_above_ma(rule: Dict[str, Any], rid: str) -> Dict[str, Any]:
    window = int(rule.get("window", 5))
    label = str(rule.get("label") or f"收盘>MA{window}").strip()
    return {
        "id": rid,
        "label": label,
        "expr": f"close > ma_{window}",
        "weight": float(rule.get("weight", 1) or 1),
    }


def _migrate_close_below_ma(rule: Dict[str, Any], rid: str) -> Dict[str, Any]:
    window = int(rule.get("window", 5))
    label = str(rule.get("label") or f"收盘<MA{window}").strip()
    return {
        "id": rid,
        "label": label,
        "expr": f"close < ma_{window}",
        "weight": float(rule.get("weight", 1) or 1),
    }


def _migrate_volume_ratio(rule: Dict[str, Any], rid: str) -> Dict[str, Any]:
    window = int(rule.get("window", 5))
    op = _normalize_operator(rule.get("operator", ">="))
    value = rule.get("value", 1)
    label = str(rule.get("label") or f"量比({window}) {op} {value}").strip()
    return {
        "id": rid,
        "label": label,
        "expr": f"vol_ratio_{window} {op} {value}",
        "weight": float(rule.get("weight", 1) or 1),
    }


def _migrate_period_return(rule: Dict[str, Any], rid: str) -> Dict[str, Any]:
    lookback = int(rule.get("lookback", 5))
    op = _normalize_operator(rule.get("operator", ">="))
    value = rule.get("value", 0)
    label = str(rule.get("label") or f"区间收益({lookback}) {op} {value}%").strip()
    return {
        "id": rid,
        "label": label,
        "expr": f"period_return_{lookback} {op} {value}",
        "weight": float(rule.get("weight", 1) or 1),
    }


def _migrate_breakout_high(rule: Dict[str, Any], rid: str) -> Dict[str, Any]:
    window = int(rule.get("window", 20))
    label = str(rule.get("label") or f"突破前{window}日高点").strip()
    # rolling_high 排除当日，与 v1 _breakout_high 对齐。
    return {
        "id": rid,
        "label": label,
        "expr": f"close > rolling_high_{window}",
        "weight": float(rule.get("weight", 1) or 1),
    }


def _migrate_macd_cross(rule: Dict[str, Any], rid: str) -> Dict[str, Any]:
    is_golden = rule.get("rule_type") == "macd_golden_cross"
    label = str(rule.get("label") or ("MACD 金叉" if is_golden else "MACD 死叉")).strip()
    fn = "cross_up" if is_golden else "cross_down"
    return {
        "id": rid,
        "label": label,
        "expr": f"{fn}(macd_dif, macd_dea)",
        "weight": float(rule.get("weight", 1) or 1),
    }


def _migrate_kdj_cross(rule: Dict[str, Any], rid: str) -> Dict[str, Any]:
    is_golden = rule.get("rule_type") == "kdj_golden_cross"
    label = str(rule.get("label") or ("KDJ 金叉" if is_golden else "KDJ 死叉")).strip()
    fn = "cross_up" if is_golden else "cross_down"
    return {
        "id": rid,
        "label": label,
        "expr": f"{fn}(kdj_k, kdj_d)",
        "weight": float(rule.get("weight", 1) or 1),
    }


def _migrate_td_setup(rule: Dict[str, Any], rid: str) -> Dict[str, Any]:
    is_buy = rule.get("rule_type") == "td_buy_setup_complete"
    label = str(rule.get("label") or ("TD 买入 Setup 完成" if is_buy else "TD 卖出 Setup 完成")).strip()
    sig = "buy_setup_complete" if is_buy else "sell_setup_complete"
    return {
        "id": rid,
        "label": label,
        "expr": f'td_signal == "{sig}"',
        "weight": float(rule.get("weight", 1) or 1),
    }


def _migrate_bottom_divergence(rule: Dict[str, Any], rid: str) -> Dict[str, Any]:
    label = str(rule.get("label") or "底背离").strip()
    return {
        "id": rid,
        "label": label,
        # v1 触发条件：signal == "bottom_divergence" OR bottom_divergence flag 为真。
        # 复现为 OR：与 v1 _evaluate_bottom_divergence 完全一致。
        "expr": 'td_signal == "bottom_divergence" or bottom_divergence',
        "weight": float(rule.get("weight", 1) or 1),
    }


_RULE_MIGRATORS = {
    "field_compare": _migrate_field_compare,
    "close_above_ma": _migrate_close_above_ma,
    "close_below_ma": _migrate_close_below_ma,
    "volume_ratio": _migrate_volume_ratio,
    "period_return": _migrate_period_return,
    "breakout_high": _migrate_breakout_high,
    "macd_golden_cross": _migrate_macd_cross,
    "macd_death_cross": _migrate_macd_cross,
    "kdj_golden_cross": _migrate_kdj_cross,
    "kdj_death_cross": _migrate_kdj_cross,
    "td_buy_setup_complete": _migrate_td_setup,
    "td_sell_setup_complete": _migrate_td_setup,
    "bottom_divergence": _migrate_bottom_divergence,
}


def _rule_get_type(rule: Dict[str, Any]) -> str:
    return str(rule.get("rule_type", rule.get("type", ""))).strip()


def migrate_v1_to_v2(v1: Optional[Dict]) -> Dict[str, Any]:
    """v1 配置转 v2。

    - v1 形态：{signal_type, logic, min_score, rules: [{rule_type, params...}]}
    - v2 形态：{version: 2, signal_type, gate: {mode}, min_score, rules: [{id, label, expr, weight}], indicators: [...]}

    已为 v2 时直接浅拷贝并补 indicators 字段（不重复设置 version）。
    无 rules 的空配置也安全返回。
    """
    if not v1 or not isinstance(v1, dict):
        return _empty_v2()

    if v1.get("version") == 2:
        # 已是 v2；只补全 indicators 字段（即使空也保持 schema 稳定）
        result = dict(v1)
        result.setdefault("indicators", [])
        result.setdefault("gate", {"mode": v1.get("logic", "all") or "all"})
        return result

    logic = str(v1.get("logic", "all") or "all").strip().lower()
    if logic not in ("all", "any"):
        logic = "all"

    used_ids: set = set()
    new_rules: List[Dict[str, Any]] = []
    for rule in v1.get("rules") or []:
        if not isinstance(rule, dict):
            continue
        rt = _rule_get_type(rule)
        if not rt:
            continue
        migrator = _RULE_MIGRATORS.get(rt)
        if not migrator:
            # 未知 rule_type：跳过但保留信息（前端 IDE 应避免丢失旧规则）
            rid = _next_rule_id(used_ids)
            label = str(rule.get("label") or rt)
            weight = float(rule.get("weight", 1) or 1)
            new_rules.append({
                "id": rid,
                "label": label,
                "expr": "False",  # 永远不命中，前端 IDE 会看到红字
                "weight": weight,
                "_unsupported_rule_type": rt,
            })
            continue
        rid = _next_rule_id(used_ids)
        migrated = migrator(rule, rid)
        new_rules.append(migrated)

    return {
        "version": 2,
        "signal_type": str(v1.get("signal_type") or "watch"),
        "logic": logic,
        "gate": {"mode": logic},
        "min_score": float(v1.get("min_score", 0) or 0),
        "indicators": [],
        "rules": new_rules,
    }


def _empty_v2() -> Dict[str, Any]:
    return {
        "version": 2,
        "signal_type": "watch",
        "logic": "all",
        "gate": {"mode": "all"},
        "min_score": 0,
        "indicators": [],
        "rules": [],
    }