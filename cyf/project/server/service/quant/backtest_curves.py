"""回测指标 / 曲线构建纯函数。

所有函数都是无副作用的：输入 (bars / trades / returns) → 输出 dict。
从 backtest_service.py 拆出，便于单测和未来扩展（5m / 1w 频率只需扩展本文件）。
"""
from __future__ import annotations

import math
from collections import defaultdict
from typing import Optional


def _max_drawdown(curve: list[dict]) -> Optional[float]:
    """净值曲线最大回撤（最大累计跌幅 / 峰值），空曲线返回 None。"""
    if not curve:
        return None
    peak = None
    max_drawdown = 0.0
    for point in curve:
        net_value = float(point["net_value"])
        if peak is None or net_value > peak:
            peak = net_value
        if peak and peak > 0:
            drawdown = (net_value - peak) / peak
            max_drawdown = min(max_drawdown, drawdown)
    return max_drawdown


def _sharpe_ratio(returns: list[float], hold_days: int) -> Optional[float]:
    """年化夏普比率（252 交易日 / hold_days）。returns < 2 或 std == 0 返回 None。"""
    if len(returns) < 2:
        return None
    avg_value = sum(returns) / len(returns)
    variance = sum((item - avg_value) ** 2 for item in returns) / (len(returns) - 1)
    std = math.sqrt(variance)
    if std == 0:
        return None
    annual_factor = math.sqrt(252 / max(hold_days, 1))
    return avg_value / std * annual_factor


def _build_equity_curve(initial_capital: float, trades: list[dict], start_date_text: str) -> list[dict]:
    """策略净值曲线（按平仓日聚合）：每天取当日所有 trade 的平均收益，乘以当前 capital。"""
    grouped_returns = defaultdict(list)
    for trade in trades:
        grouped_returns[trade["exit_date"]].append(float(trade["net_return"]))

    capital = float(initial_capital)
    curve = [{"date": start_date_text, "capital": round(capital, 4), "net_value": 1.0}]
    for exit_date in sorted(grouped_returns):
        avg_return = sum(grouped_returns[exit_date]) / len(grouped_returns[exit_date])
        capital *= 1 + avg_return
        curve.append({
            "date": exit_date,
            "capital": round(capital, 4),
            "net_value": round(capital / initial_capital, 6),
            "avg_return": round(avg_return, 6),
            "closed_trades": len(grouped_returns[exit_date]),
        })
    return curve


def _build_benchmark_curve(benchmark_bars: list, start_date_text: str, end_date_text: str) -> list[dict]:
    """买入持有基准（buy & hold）净值曲线。

    起点：start_date 那天或之后最近的 bar 的 open_price 满仓买入。
    终点：end_date 那天或之前最近的 bar 的 close_price。
    每个 bar 一个点：net_value = close / entry_open。
    起点 bar 自身不算 net_value 点（避免 entry 瞬间的"涨/跌"误算）。

    返回 [{date, net_value, capital}, ...]；空 bars 或日期无交集返回 []。
    """
    if not benchmark_bars:
        return []

    # 取 [start_date, end_date] 区间内的 bars
    candidates = []
    for bar in benchmark_bars:
        bd = bar.trade_date
        bd_text = bd.isoformat() if hasattr(bd, "isoformat") else str(bd)
        if bd_text < start_date_text:
            continue
        if bd_text > end_date_text:
            continue
        candidates.append((bd_text, bar))

    if not candidates:
        # 区间内无 bar → 用"最近邻 anchor"做单点（曲线退化为水平）
        anchor = None
        for bar in benchmark_bars:
            bd_text = bar.trade_date.isoformat() if hasattr(bar.trade_date, "isoformat") else str(bar.trade_date)
            if bd_text >= start_date_text:
                anchor = bar
                break
        if anchor is None:
            return []
        open_price = anchor.open_price or anchor.close_price
        if not open_price:
            return []
        return [{
            "date": start_date_text,
            "net_value": 1.0,
            "capital": round(open_price, 4),
        }]

    entry_open = candidates[0][1].open_price or candidates[0][1].close_price
    if not entry_open:
        return []

    curve = [{"date": start_date_text, "net_value": 1.0, "capital": round(entry_open, 4)}]
    for bd_text, bar in candidates[1:]:
        close = bar.close_price or bar.open_price
        if not close:
            continue
        curve.append({
            "date": bd_text,
            "net_value": round(close / entry_open, 6),
            "capital": round(close, 4),
        })
    return curve


def _benchmark_summary(benchmark_curve: list[dict], total_commission_rate: float) -> dict:
    """基准 buy & hold 收益 + 净收益（双边手续费 + 滑点）。alpha 由 caller 算。"""
    if len(benchmark_curve) < 2:
        return {"benchmark_gross_return": None, "benchmark_net_return": None, "alpha": None}
    gross = float(benchmark_curve[-1]["net_value"]) - 1.0
    net = gross - total_commission_rate * 2
    return {
        "benchmark_gross_return": round(gross, 6),
        "benchmark_net_return": round(net, 6),
        "alpha": None,
    }


def _annualized_return(total_return: float, duration_days: int) -> Optional[float]:
    """365 天年化。total_return <= -1 时无意义返回 None。"""
    if total_return <= -1:
        return None
    return (1 + total_return) ** (365 / max(duration_days, 1)) - 1


def _compute_metrics(
    *,
    initial_capital: float,
    final_capital: float,
    duration_days: int,
    hold_days: int,
    trades: list[dict],
    curve: list[dict],
    bench_summary: dict,
) -> dict:
    """汇总回测指标：胜率 / 收益 / 夏普 / 回撤 / alpha 等。

    返回 dict 与 QuantBacktestRun.metrics_json 字段对应。caller 需传入
    hold_days（用于夏普年化因子）和 bench_summary（_benchmark_summary 输出）。
    """
    returns = [float(item["net_return"]) for item in trades]
    total_return = (final_capital - initial_capital) / initial_capital if initial_capital else 0.0
    win_count = len([r for r in returns if r > 0])
    loss_count = len([r for r in returns if r < 0])
    win_rate = win_count / len(returns) if returns else None
    avg_return = sum(returns) / len(returns) if returns else None
    annualized = _annualized_return(total_return, duration_days)
    sharpe = _sharpe_ratio(returns, hold_days) if returns else None

    return {
        "win_count": win_count,
        "loss_count": loss_count,
        "win_rate": round(win_rate, 6) if win_rate is not None else None,
        "avg_return": round(avg_return, 6) if avg_return is not None else None,
        "total_return": round(total_return, 6),
        "annualized_return": round(annualized, 6) if annualized is not None else None,
        "max_drawdown": round(_max_drawdown(curve), 6) if curve else None,
        "sharpe": round(sharpe, 6) if sharpe is not None else None,
        "final_capital": round(final_capital, 4),
        **bench_summary,
    }
