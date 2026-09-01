"""预设策略模板 —— v2 形态，供前端 IDE 一键回填。

说明：
- 不进 DB。等出现"用户自定义模板"需求再考虑持久化。
- 与前端 useQuantWorkbench.ts:387-407 的两个老模板等价改写 + 补充 3 个常见形态。
"""
from __future__ import annotations


STRATEGY_TEMPLATES: list[dict] = [
    {
        "key": "trend_volume",
        "title": "趋势放量",
        "summary": "短期走强的日线标的：涨幅+站上均线+量比放大",
        "category": "trend",
        "rule_config": {
            "version": 2,
            "signal_type": "watch",
            "logic": "all",
            "gate": {"mode": "all"},
            "min_score": 2,
            "indicators": [
                {"key": "ma", "params": {"windows": [5]}},
                {"key": "vol_ratio", "params": {"window": 5}},
            ],
            "rules": [
                {
                    "id": "r1",
                    "label": "涨跌幅至少 2%",
                    "expr": "pct_change >= 2",
                    "weight": 1,
                },
                {
                    "id": "r2",
                    "label": "收盘站上 5 日线",
                    "expr": "close > ma_5",
                    "weight": 1,
                },
                {
                    "id": "r3",
                    "label": "量比至少 1.2",
                    "expr": "vol_ratio_5 >= 1.2",
                    "weight": 1,
                },
            ],
        },
    },
    {
        "key": "breakout",
        "title": "突破观察",
        "summary": "放量突破前高的观察名单",
        "category": "trend",
        "rule_config": {
            "version": 2,
            "signal_type": "watch",
            "logic": "all",
            "gate": {"mode": "all"},
            "min_score": 3,
            "indicators": [
                {"key": "rolling_high_low", "params": {"window": 20}},
                {"key": "vol_ratio", "params": {"window": 5}},
            ],
            "rules": [
                {
                    "id": "r1",
                    "label": "突破前 20 日高点",
                    "expr": "close > rolling_high_20",
                    "weight": 1,
                },
                {
                    "id": "r2",
                    "label": "换手率至少 1%",
                    "expr": "turnover_rate >= 1",
                    "weight": 1,
                },
                {
                    "id": "r3",
                    "label": "量比至少 1.5",
                    "expr": "vol_ratio_5 >= 1.5",
                    "weight": 1,
                },
            ],
        },
    },
    {
        "key": "macd_golden",
        "title": "MACD 金叉",
        "summary": "MACD 出现金叉信号",
        "category": "momentum",
        "rule_config": {
            "version": 2,
            "signal_type": "buy",
            "logic": "all",
            "gate": {"mode": "all"},
            "min_score": 1,
            "indicators": [{"key": "macd"}],
            "rules": [
                {
                    "id": "r1",
                    "label": "MACD 金叉",
                    "expr": "cross_up(macd_dif, macd_dea)",
                    "weight": 1,
                },
            ],
        },
    },
    {
        "key": "kdj_oversold",
        "title": "KDJ 超卖反弹",
        "summary": "KDJ 的 K/D 上穿，常见超卖反转点",
        "category": "momentum",
        "rule_config": {
            "version": 2,
            "signal_type": "buy",
            "logic": "all",
            "gate": {"mode": "all"},
            "min_score": 2,
            "indicators": [{"key": "kdj"}],
            "rules": [
                {
                    "id": "r1",
                    "label": "KDJ 金叉",
                    "expr": "cross_up(kdj_k, kdj_d)",
                    "weight": 2,
                },
                {
                    "id": "r2",
                    "label": "K 在 30 以下超卖区",
                    "expr": "kdj_k < 30",
                    "weight": 1,
                },
            ],
        },
    },
    {
        "key": "td_buy_setup",
        "title": "TD 九转完成",
        "summary": "TD 买入 Setup 完成（连续 9 根收盘低于 4 根前）",
        "category": "structure",
        "rule_config": {
            "version": 2,
            "signal_type": "watch",
            "logic": "all",
            "gate": {"mode": "all"},
            "min_score": 1,
            "indicators": [{"key": "td_sequential"}],
            "rules": [
                {
                    "id": "r1",
                    "label": "TD 买入 Setup 完成",
                    "expr": 'td_signal == "buy_setup_complete"',
                    "weight": 1,
                },
            ],
        },
    },
]