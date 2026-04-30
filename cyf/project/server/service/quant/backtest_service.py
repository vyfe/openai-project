import json
import math
from collections import defaultdict
from datetime import datetime
from typing import Optional

from peewee import fn

from quant.entities import QuantBacktestRun, QuantDailyBar, QuantStrategy
from service.quant.common import normalize_symbol, parse_trade_date
from service.quant.rule_engine import evaluate_strategy_rules, get_required_history_size


def _safe_float(value, default: float) -> float:
    if value in (None, ""):
        return float(default)
    return float(value)


def _safe_int(value, default: int) -> int:
    if value in (None, ""):
        return int(default)
    return int(value)


def list_backtest_runs(strategy_id: Optional[int] = None, status: Optional[str] = None, limit: int = 50) -> list[dict]:
    query = QuantBacktestRun.select()
    if strategy_id:
        query = query.where(QuantBacktestRun.strategy_id == strategy_id)
    if status:
        query = query.where(QuantBacktestRun.status == status)
    query = query.order_by(QuantBacktestRun.id.desc()).limit(limit)
    items = []
    for item in query.iterator():
        payload = item.to_dict()
        payload.pop("equity_curve", None)
        payload.pop("trades", None)
        payload.pop("strategy_snapshot", None)
        items.append(payload)
    return items


def get_backtest_run(backtest_id: int) -> dict:
    return QuantBacktestRun.get_by_id(backtest_id).to_dict()


def delete_backtest_run(backtest_id: int) -> bool:
    record = QuantBacktestRun.get_by_id(backtest_id)
    record.delete_instance()
    return True


def _load_strategy(strategy_id: int) -> QuantStrategy:
    return QuantStrategy.get_by_id(strategy_id)


def _resolve_symbols(strategy: QuantStrategy, override_symbols=None) -> list[str]:
    if override_symbols:
        if isinstance(override_symbols, str):
            override_symbols = [item.strip() for item in override_symbols.split(",") if item.strip()]
        return [normalize_symbol(item) for item in override_symbols]
    symbols = json.loads(strategy.symbols_json or "[]")
    return [normalize_symbol(item) for item in symbols if str(item).strip()]


def _load_bars_for_symbol(symbol: str, end_date) -> list[QuantDailyBar]:
    query = (
        QuantDailyBar.select()
        .where((QuantDailyBar.symbol == symbol) & (QuantDailyBar.trade_date <= end_date))
        .order_by(QuantDailyBar.trade_date.asc())
    )
    return list(query)


def _max_drawdown(curve: list[dict]) -> Optional[float]:
    peak = None
    max_drawdown = 0.0
    for point in curve:
        net_value = float(point["net_value"])
        if peak is None or net_value > peak:
            peak = net_value
        if peak and peak > 0:
            drawdown = (net_value - peak) / peak
            max_drawdown = min(max_drawdown, drawdown)
    return max_drawdown if curve else None


def _sharpe_ratio(returns: list[float], hold_days: int) -> Optional[float]:
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
    grouped_returns = defaultdict(list)
    for trade in trades:
        grouped_returns[trade["exit_date"]].append(float(trade["net_return"]))

    capital = float(initial_capital)
    curve = [{"date": start_date_text, "capital": round(capital, 4), "net_value": 1.0}]
    for exit_date in sorted(grouped_returns):
        avg_return = sum(grouped_returns[exit_date]) / len(grouped_returns[exit_date])
        capital *= 1 + avg_return
        curve.append(
            {
                "date": exit_date,
                "capital": round(capital, 4),
                "net_value": round(capital / initial_capital, 6),
                "avg_return": round(avg_return, 6),
                "closed_trades": len(grouped_returns[exit_date]),
            }
        )
    return curve


def _latest_data_version(symbols: list[str], end_date) -> str:
    query = (
        QuantDailyBar.select(QuantDailyBar.data_source_version)
        .where((QuantDailyBar.symbol.in_(symbols)) & (QuantDailyBar.trade_date <= end_date))
        .where(QuantDailyBar.data_source_version != "")
        .group_by(QuantDailyBar.data_source_version)
        .order_by(fn.MAX(QuantDailyBar.trade_date).desc())
        .limit(4)
    )
    versions = [item.data_source_version for item in query.iterator() if item.data_source_version]
    return ",".join(versions)


def run_backtest(
    *,
    strategy_id: int,
    start_date,
    end_date,
    top_n: int = 3,
    hold_days: int = 5,
    initial_capital: float = 100000.0,
    commission_rate: float = 0.001,
    slippage_rate: float = 0.0005,
    benchmark_symbol: str = "",
    symbols=None,
) -> dict:
    strategy = _load_strategy(strategy_id)
    resolved_start_date = parse_trade_date(start_date)
    resolved_end_date = parse_trade_date(end_date)
    if resolved_start_date > resolved_end_date:
        raise ValueError("start_date 不能晚于 end_date")

    resolved_symbols = _resolve_symbols(strategy, symbols)
    if not resolved_symbols:
        raise ValueError("回测需要明确股票池，请先给策略配置 symbols")

    top_n = max(1, min(_safe_int(top_n, 3), len(resolved_symbols)))
    hold_days = max(1, min(_safe_int(hold_days, 5), 60))
    initial_capital = max(1000.0, _safe_float(initial_capital, 100000.0))
    commission_rate = max(0.0, _safe_float(commission_rate, 0.001))
    slippage_rate = max(0.0, _safe_float(slippage_rate, 0.0005))

    strategy_snapshot = strategy.to_dict()
    now = datetime.now()
    record = QuantBacktestRun.create(
        strategy_id=strategy.id,
        strategy_name=strategy.name,
        status="running",
        mode="event_study",
        start_date=resolved_start_date,
        end_date=resolved_end_date,
        benchmark_symbol=normalize_symbol(benchmark_symbol) if str(benchmark_symbol or "").strip() else "",
        hold_days=hold_days,
        top_n=top_n,
        initial_capital=initial_capital,
        commission_rate=commission_rate,
        slippage_rate=slippage_rate,
        strategy_snapshot_json=json.dumps(strategy_snapshot, ensure_ascii=False),
        code_version=f"rule-engine-v1|strategy-updated:{strategy.updated_at.isoformat() if strategy.updated_at else ''}",
        created_at=now,
    )

    try:
        rule_config = json.loads(strategy.rule_config_json or "{}")
        history_size = get_required_history_size(rule_config)
        bars_by_symbol = {}
        index_by_symbol = {}
        all_trade_dates = set()

        for symbol in resolved_symbols:
            bars = _load_bars_for_symbol(symbol, resolved_end_date)
            if not bars:
                continue
            bars_by_symbol[symbol] = bars
            index_by_symbol[symbol] = {bar.trade_date: idx for idx, bar in enumerate(bars)}
            for bar in bars:
                if resolved_start_date <= bar.trade_date <= resolved_end_date:
                    all_trade_dates.add(bar.trade_date)

        if not bars_by_symbol:
            raise ValueError("回测区间内没有可用行情数据")

        trades = []
        candidate_signals_total = 0
        skipped_due_to_future = 0

        for trade_date in sorted(all_trade_dates):
            candidates = []
            for symbol, bars in bars_by_symbol.items():
                idx = index_by_symbol[symbol].get(trade_date)
                if idx is None:
                    continue
                history_start = max(0, idx - max(history_size, 2) + 1)
                history = list(reversed(bars[history_start : idx + 1]))
                if not history or history[0].trade_date != trade_date:
                    continue

                result = evaluate_strategy_rules(rule_config, history)
                if not result["passed"]:
                    continue

                candidate_signals_total += 1
                next_idx = idx + 1
                exit_idx = idx + hold_days
                if next_idx >= len(bars) or exit_idx >= len(bars):
                    skipped_due_to_future += 1
                    continue

                entry_bar = bars[next_idx]
                exit_bar = bars[exit_idx]
                entry_price = entry_bar.open_price or entry_bar.close_price
                exit_price = exit_bar.close_price or exit_bar.open_price
                if entry_price in (None, 0) or exit_price is None:
                    skipped_due_to_future += 1
                    continue

                gross_return = (exit_price - entry_price) / entry_price
                net_return = gross_return - (commission_rate + slippage_rate) * 2
                candidates.append(
                    {
                        "symbol": symbol,
                        "signal_date": trade_date.isoformat(),
                        "entry_date": entry_bar.trade_date.isoformat(),
                        "exit_date": exit_bar.trade_date.isoformat(),
                        "entry_price": round(entry_price, 4),
                        "exit_price": round(exit_price, 4),
                        "gross_return": round(gross_return, 6),
                        "net_return": round(net_return, 6),
                        "score": round(float(result["score"]), 4),
                        "signal_type": result["signal_type"],
                        "reasons": result["reasons"],
                        "metrics": result["metrics"],
                    }
                )

            candidates.sort(key=lambda item: (-item["score"], item["symbol"]))
            trades.extend(candidates[:top_n])

        trades.sort(key=lambda item: (item["exit_date"], item["entry_date"], item["symbol"]))
        returns = [float(item["net_return"]) for item in trades]
        curve = _build_equity_curve(initial_capital, trades, resolved_start_date.isoformat())
        final_capital = curve[-1]["capital"] if curve else initial_capital
        total_return = (final_capital - initial_capital) / initial_capital if initial_capital else 0.0
        duration_days = max((resolved_end_date - resolved_start_date).days, 1)
        annualized_return = None
        if total_return > -1:
            annualized_return = (1 + total_return) ** (365 / duration_days) - 1
        win_count = len([item for item in returns if item > 0])
        loss_count = len([item for item in returns if item < 0])
        win_rate = win_count / len(returns) if returns else None
        avg_return = sum(returns) / len(returns) if returns else None
        metrics = {
            "signals_total": candidate_signals_total,
            "trades_total": len(trades),
            "win_count": win_count,
            "loss_count": loss_count,
            "win_rate": round(win_rate, 6) if win_rate is not None else None,
            "avg_return": round(avg_return, 6) if avg_return is not None else None,
            "total_return": round(total_return, 6),
            "annualized_return": round(annualized_return, 6) if annualized_return is not None else None,
            "max_drawdown": round(_max_drawdown(curve), 6) if curve else None,
            "sharpe": round(_sharpe_ratio(returns, hold_days), 6) if returns else None,
            "final_capital": round(final_capital, 4),
            "skipped_due_to_future": skipped_due_to_future,
        }
        summary = {
            "strategy_name": strategy.name,
            "mode": "event_study",
            "universe_size": len(resolved_symbols),
            "trade_window": f"{resolved_start_date.isoformat()} ~ {resolved_end_date.isoformat()}",
            "benchmark_symbol": record.benchmark_symbol,
            "limitations": [
                "当前回测为轻量事件回测，依赖策略已配置的明确股票池。",
                "收益曲线按平仓日聚合，不等同于真实逐日持仓净值。",
                "盘中成交、停牌、滑点冲击和仓位约束未完整模拟。",
            ],
        }

        record.status = "success"
        record.signals_total = candidate_signals_total
        record.trades_total = len(trades)
        record.summary_json = json.dumps(summary, ensure_ascii=False)
        record.metrics_json = json.dumps(metrics, ensure_ascii=False)
        record.equity_curve_json = json.dumps(curve, ensure_ascii=False)
        record.trades_json = json.dumps(trades, ensure_ascii=False)
        record.data_source_version = _latest_data_version(resolved_symbols, resolved_end_date)
        record.finished_at = datetime.now()
        record.save()
        return record.to_dict()
    except Exception as exc:
        record.status = "failed"
        record.error_message = str(exc)
        record.finished_at = datetime.now()
        record.save()
        raise
