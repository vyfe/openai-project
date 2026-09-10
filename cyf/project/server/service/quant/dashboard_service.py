from datetime import date, datetime

from peewee import fn

from quant.entities import (
    QuantBacktestRun,
    QuantDailyBar,
    QuantInstrument,
    QuantOperationRecord,
    QuantReportRecord,
    QuantStrategy,
    QuantStrategyRun,
    QuantStrategySignal,
)
from service.quant.backtest_service import list_backtest_runs
from service.quant.memory_service import list_memory_files
from service.quant.ops_service import list_operation_records
from service.quant.task_dispatch_service import list_tasks


def _today_text() -> str:
    return datetime.now().date().isoformat()


def _bulk_lookup_names(symbols: list[str]) -> dict[str, str]:
    """批量查 quant_instrument 的显示名：custom_name 优先，回退 name。

    委托给 instrument_display_service.bulk_lookup_display_names 统一处理。
    """
    from service.quant.instrument_display_service import bulk_lookup_display_names
    return bulk_lookup_display_names(symbols)


def _bulk_lookup_records(symbols: list[str]) -> dict[str, dict]:
    """批量查 quant_instrument 三件套 {name, custom_name, display_name}。

    委托给 instrument_display_service.bulk_lookup_instrument_records。
    """
    from service.quant.instrument_display_service import bulk_lookup_instrument_records
    return bulk_lookup_instrument_records(symbols)


def _attach_names(records: list[dict], record_map: dict[str, dict]) -> list[dict]:
    """把批量查出的 name / custom_name / display_name 三件套挂到 records 的每条上。

    仅当字段未设置时才写入（不覆盖已有值，避免与子模块自带字段冲突）。
    """
    if not records:
        return records
    for item in records:
        sym = item.get("symbol")
        if not sym:
            continue
        info = record_map.get(sym) or {"name": "", "custom_name": "", "display_name": ""}
        if "name" not in item:
            item["name"] = info["name"]
        if "custom_name" not in item:
            item["custom_name"] = info["custom_name"]
        if "display_name" not in item:
            item["display_name"] = info["display_name"]
    return records


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
    recent_reports = [
        item.to_dict()
        for item in QuantReportRecord.select().order_by(QuantReportRecord.id.desc()).limit(6).iterator()
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
    memory_files = list_memory_files(limit=6)

    # 批量补 name / custom_name / display_name 三件套：一次 in_ 查询覆盖 signals / operations / memory
    all_symbols = (
        [s.get("symbol") for s in latest_signals if s.get("symbol")]
        + [op.get("symbol") for op in operations if op.get("symbol")]
        + [m.get("symbol") for m in memory_files if m.get("symbol")]
    )
    record_map = _bulk_lookup_records(all_symbols)
    _attach_names(latest_signals, record_map)
    _attach_names(operations, record_map)
    _attach_names(memory_files, record_map)

    return {
        "snapshot": {
            "today": today,
            "latest_trade_date": latest_trade_date.isoformat() if latest_trade_date else None,
            "active_strategies": active_strategy_count,
            "today_operations": today_operations,
            "successful_backtests": success_backtests,
            "pending_tasks": len([item for item in tasks if item.get("status") in ("pending", "leased")]),
            "recent_reports": len(recent_reports),
            "memory_files": len(memory_files),
        },
        "today_tasks": tasks,
        "latest_signals": latest_signals,
        "recent_runs": latest_runs,
        "recent_operations": operations,
        "recent_backtests": backtests,
        "recent_reports": recent_reports,
        "recent_memory_files": memory_files,
        "risk_tips": _build_risk_tips(tasks, latest_signals, operations, backtests),
    }
