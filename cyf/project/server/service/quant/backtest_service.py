import json
from collections import defaultdict
from datetime import datetime
from typing import Optional

from peewee import fn

from quant.entities import QuantBacktestRun, QuantDailyBar, QuantStrategy
from service.quant.backtest_curves import (
    _benchmark_summary,
    _build_benchmark_curve,
    _build_equity_curve,
    _compute_metrics,
)
from service.quant.common import normalize_symbol, parse_trade_date
from service.quant.rule_engine import evaluate_series, get_required_history_size_v2
from service.quant.rule_migration import migrate_v1_to_v2


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
        raw_rule_config = json.loads(strategy.rule_config_json or "{}")
        rule_config = migrate_v1_to_v2(raw_rule_config)  # v1 自动迁移到 v2
        history_size = get_required_history_size_v2(rule_config)
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

        # v2 路径：对每只 symbol 一次性 evaluate_series 全序列，按日索引取结果。
        # 旧实现按日循环 evaluate_strategy_rules，每天重算一遍指标（O(天数×标的数)）。
        # 新实现按 symbol 循环（O(标的数)），单 symbol 内的指标只算一次。
        for symbol, bars in bars_by_symbol.items():
            trade_date_to_idx = index_by_symbol[symbol]
            # 序列视角：bars 已经是升序；需要降序（新→旧）传给 evaluate_series
            asc_history = bars  # ascending old→new
            desc_history = list(reversed(asc_history))  # descending new→old
            series_results = evaluate_series(rule_config, desc_history)
            for result in series_results:
                if not result.get("passed"):
                    continue
                # signal_type 决定 long/short 分支（默认 watch 走 long）
                signal_type = str(result.get("signal_type") or "watch").strip().lower() or "watch"
                is_short = signal_type == "sell"
                side = "short" if is_short else "long"

                trade_date = result["metrics"]["trade_date"]
                if trade_date is None:
                    continue
                # parse back to date for index lookup
                from datetime import date as _date
                try:
                    dt_obj = _date.fromisoformat(str(trade_date))
                except ValueError:
                    continue
                if dt_obj < resolved_start_date or dt_obj > resolved_end_date:
                    continue
                idx = trade_date_to_idx.get(dt_obj)
                if idx is None:
                    continue
                candidate_signals_total += 1
                entry_idx = idx + 1
                exit_idx = idx + hold_days
                if entry_idx >= len(bars) or exit_idx >= len(bars):
                    skipped_due_to_future += 1
                    continue

                entry_bar = bars[entry_idx]
                exit_bar = bars[exit_idx]

                if is_short:
                    # 做空：entry_idx 开盘价 = 卖出开仓价；exit_idx 开盘价 = 买回平仓价。
                    # 价跌为正收益：open_price - cover_price
                    open_price = entry_bar.open_price or entry_bar.close_price
                    cover_price = exit_bar.open_price or exit_bar.close_price
                    if open_price in (None, 0) or cover_price is None:
                        skipped_due_to_future += 1
                        continue
                    gross_return = (open_price - cover_price) / open_price
                    entry_price = open_price
                    exit_price = cover_price
                else:
                    # 做多（buy / watch）：entry_idx 开盘买入；exit_idx 收盘卖出。
                    # 价涨为正收益：exit_price - entry_price
                    entry_price = entry_bar.open_price or entry_bar.close_price
                    exit_price = exit_bar.close_price or exit_bar.open_price
                    if entry_price in (None, 0) or exit_price is None:
                        skipped_due_to_future += 1
                        continue
                    gross_return = (exit_price - entry_price) / entry_price

                # 手续费 / 滑点双边：开 + 平（不论 long/short 都是 2 笔交易）
                net_return = gross_return - (commission_rate + slippage_rate) * 2
                trades.append(
                    {
                        "symbol": symbol,
                        "signal_date": dt_obj.isoformat(),
                        "entry_date": entry_bar.trade_date.isoformat(),
                        "exit_date": exit_bar.trade_date.isoformat(),
                        "entry_price": round(entry_price, 4),
                        "exit_price": round(exit_price, 4),
                        "gross_return": round(gross_return, 6),
                        "net_return": round(net_return, 6),
                        "score": round(float(result["score"]), 4),
                        "signal_type": result["signal_type"],
                        "side": side,
                        "reasons": result["reasons"],
                        "metrics": result["metrics"],
                    }
                )

        # 按 (signal_date, symbol) 取每天 top_n（保持与旧实现一致的语义）
        from collections import defaultdict
        by_date: dict[str, list] = defaultdict(list)
        for t in trades:
            by_date[t["signal_date"]].append(t)
        trades = []
        for signal_date in sorted(by_date):
            by_date[signal_date].sort(key=lambda item: (-item["score"], item["symbol"]))
            trades.extend(by_date[signal_date][:top_n])

        trades.sort(key=lambda item: (item["exit_date"], item["entry_date"], item["symbol"]))
        curve = _build_equity_curve(initial_capital, trades, resolved_start_date.isoformat())
        final_capital = curve[-1]["capital"] if curve else initial_capital
        # 基准 buy & hold 净值曲线（按用户配置的基准标的）
        benchmark_bars = _load_bars_for_symbol(record.benchmark_symbol, resolved_end_date) if record.benchmark_symbol else []
        benchmark_curve = (
            _build_benchmark_curve(benchmark_bars, resolved_start_date.isoformat(), resolved_end_date.isoformat())
            if benchmark_bars else []
        )
        bench_summary = _benchmark_summary(benchmark_curve, commission_rate + slippage_rate)
        # alpha = 策略净收益 - 基准净收益
        if bench_summary["benchmark_net_return"] is not None:
            total_return = (final_capital - initial_capital) / initial_capital if initial_capital else 0.0
            bench_summary["alpha"] = round(total_return - bench_summary["benchmark_net_return"], 6)
        duration_days = max((resolved_end_date - resolved_start_date).days, 1)
        metrics = _compute_metrics(
            initial_capital=initial_capital,
            final_capital=final_capital,
            duration_days=duration_days,
            hold_days=hold_days,
            trades=trades,
            curve=curve,
            bench_summary=bench_summary,
        )
        # 拼接 run 流程相关计数（不在 _compute_metrics 里，因为是 run 控制流数据）
        metrics["signals_total"] = candidate_signals_total
        metrics["trades_total"] = len(trades)
        metrics["skipped_due_to_future"] = skipped_due_to_future
        summary = {
            "strategy_name": strategy.name,
            "mode": "event_study",
            "universe_size": len(resolved_symbols),
            "trade_window": f"{resolved_start_date.isoformat()} ~ {resolved_end_date.isoformat()}",
            "benchmark_symbol": record.benchmark_symbol,
            "benchmark_gross_return": bench_summary["benchmark_gross_return"],
            "benchmark_net_return": bench_summary["benchmark_net_return"],
            "alpha": bench_summary["alpha"],
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
        record.benchmark_curve_json = json.dumps(benchmark_curve, ensure_ascii=False)
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
