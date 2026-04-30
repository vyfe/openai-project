from datetime import date, datetime

from peewee import fn

from quant.entities import (
    QuantBacktestRun,
    QuantDailyBar,
    QuantOperationRecord,
    QuantStrategy,
    QuantStrategyRun,
    QuantStrategySignal,
)
from service.quant.backtest_service import list_backtest_runs
from service.quant.ops_service import list_operation_records
from service.quant.task_dispatch_service import list_tasks


def _today_text() -> str:
    return datetime.now().date().isoformat()


def _build_risk_tips(tasks: list[dict], latest_signals: list[dict], operations: list[dict], backtests: list[dict]) -> list[str]:
    tips = []
    failed_tasks = [item for item in tasks if item.get("status") == "failed"]
    if failed_tasks:
        tips.append(f"有 {len(failed_tasks)} 个客户端数据任务失败，建议先处理数据补采。")

    stale_operations = [item for item in operations if item.get("status") in ("draft", "executed") and not item.get("result_status")]
    if stale_operations:
        tips.append(f"有 {len(stale_operations)} 条人工操作还没有结果回填，复盘闭环还不完整。")

    weak_backtests = [
        item for item in backtests
        if item.get("status") == "success"
        and isinstance(item.get("metrics"), dict)
        and item["metrics"].get("max_drawdown") is not None
        and float(item["metrics"]["max_drawdown"]) <= -0.12
    ]
    if weak_backtests:
        tips.append(f"最近有 {len(weak_backtests)} 次回测最大回撤超过 12%，需要重新评估风控条件。")

    if not latest_signals:
        tips.append("最近没有新的通过信号，可能是数据不完整，也可能是规则过严。")

    if not tips:
        tips.append("当前没有明显风险告警，仍建议结合人工复核后再执行。")
    return tips[:4]


def get_dashboard_overview() -> dict:
    latest_trade_date = QuantDailyBar.select(fn.MAX(QuantDailyBar.trade_date)).scalar()
    active_strategy_count = QuantStrategy.select().where(QuantStrategy.status == "active").count()
    today = _today_text()

    tasks = list_tasks(limit=8)
    operations = list_operation_records(limit=8)
    backtests = list_backtest_runs(limit=6)
    latest_runs = [
        item.to_dict()
        for item in QuantStrategyRun.select().order_by(QuantStrategyRun.id.desc()).limit(6).iterator()
    ]
    latest_signals = [
        item.to_dict()
        for item in (
            QuantStrategySignal.select()
            .where(QuantStrategySignal.passed == True)
            .order_by(QuantStrategySignal.id.desc())
            .limit(8)
        ).iterator()
    ]

    today_operations = QuantOperationRecord.select().where(QuantOperationRecord.trade_date == date.fromisoformat(today)).count()
    success_backtests = QuantBacktestRun.select().where(QuantBacktestRun.status == "success").count()

    return {
        "snapshot": {
            "today": today,
            "latest_trade_date": latest_trade_date.isoformat() if latest_trade_date else None,
            "active_strategies": active_strategy_count,
            "today_operations": today_operations,
            "successful_backtests": success_backtests,
            "pending_tasks": len([item for item in tasks if item.get("status") in ("pending", "leased")]),
        },
        "today_tasks": tasks,
        "latest_signals": latest_signals,
        "recent_runs": latest_runs,
        "recent_operations": operations,
        "recent_backtests": backtests,
        "risk_tips": _build_risk_tips(tasks, latest_signals, operations, backtests),
    }
