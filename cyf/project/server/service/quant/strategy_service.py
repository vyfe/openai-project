import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional

from peewee import fn

from quant.db import quant_db
from quant.entities import (
    QuantDailyBar,
    QuantInstrument,
    QuantStrategy,
    QuantStrategyRun,
    QuantStrategySignal,
)
from service.quant.common import normalize_symbol, parse_trade_date
from service.quant.rule_engine import evaluate_strategy_rules, get_required_history_size


def _normalize_symbols(raw_symbols) -> List[str]:
    symbols = raw_symbols or []
    if isinstance(symbols, str):
        symbols = [item.strip() for item in symbols.split(",") if item.strip()]
    return [normalize_symbol(item) for item in symbols]


def _normalize_rule_config(rule_config) -> Dict:
    if rule_config is None:
        return {}
    if isinstance(rule_config, str):
        return json.loads(rule_config)
    if isinstance(rule_config, dict):
        return rule_config
    raise ValueError("rule_config 格式不正确")


def list_strategies(status: Optional[str] = None) -> List[dict]:
    query = QuantStrategy.select().order_by(QuantStrategy.id.desc())
    if status:
        query = query.where(QuantStrategy.status == status)
    return [item.to_dict() for item in query.iterator()]


def get_strategy(strategy_id: int) -> dict:
    return QuantStrategy.get_by_id(strategy_id).to_dict()


def create_strategy(name: str, description: str = "", symbols=None, rule_config=None, status: str = "active") -> dict:
    strategy = QuantStrategy.create(
        name=name.strip(),
        description=description or "",
        market="A_SHARE",
        status=status or "active",
        symbols_json=json.dumps(_normalize_symbols(symbols), ensure_ascii=False),
        rule_config_json=json.dumps(_normalize_rule_config(rule_config), ensure_ascii=False),
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    return strategy.to_dict()


def update_strategy(strategy_id: int, **updates) -> dict:
    strategy = QuantStrategy.get_by_id(strategy_id)
    if "name" in updates:
        strategy.name = str(updates["name"]).strip()
    if "description" in updates:
        strategy.description = str(updates["description"] or "")
    if "status" in updates:
        strategy.status = str(updates["status"] or "active")
    if "symbols" in updates:
        strategy.symbols_json = json.dumps(_normalize_symbols(updates["symbols"]), ensure_ascii=False)
    if "rule_config" in updates:
        strategy.rule_config_json = json.dumps(_normalize_rule_config(updates["rule_config"]), ensure_ascii=False)
    strategy.updated_at = datetime.now()
    strategy.save()
    return strategy.to_dict()


def delete_strategy(strategy_id: int) -> bool:
    strategy = QuantStrategy.get_by_id(strategy_id)
    run_ids = [item.id for item in QuantStrategyRun.select(QuantStrategyRun.id).where(QuantStrategyRun.strategy_id == strategy_id)]
    with quant_db.atomic():
        if run_ids:
            QuantStrategySignal.delete().where(QuantStrategySignal.run_id.in_(run_ids)).execute()
        QuantStrategyRun.delete().where(QuantStrategyRun.strategy_id == strategy_id).execute()
        strategy.delete_instance()
    return True


def _resolve_trade_date(explicit_trade_date: Optional[str] = None):
    if explicit_trade_date:
        return parse_trade_date(explicit_trade_date)
    query = QuantDailyBar.select(fn.MAX(QuantDailyBar.trade_date).alias("latest_trade_date"))
    latest_trade_date = query.scalar()
    if not latest_trade_date:
        raise ValueError("当前无可用行情数据")
    return latest_trade_date


def _resolve_universe(strategy: QuantStrategy, trade_date) -> List[str]:
    symbols = json.loads(strategy.symbols_json or "[]")
    if symbols:
        return [normalize_symbol(item) for item in symbols]
    query = (
        QuantDailyBar.select(QuantDailyBar.symbol)
        .where(QuantDailyBar.trade_date == trade_date)
        .group_by(QuantDailyBar.symbol)
        .order_by(QuantDailyBar.symbol.asc())
    )
    return [item.symbol for item in query.iterator()]


def _load_history(symbol: str, trade_date, limit: int) -> List[QuantDailyBar]:
    query = (
        QuantDailyBar.select()
        .where((QuantDailyBar.symbol == symbol) & (QuantDailyBar.trade_date <= trade_date))
        .order_by(QuantDailyBar.trade_date.desc())
        .limit(limit)
    )
    return list(query)


def run_strategy(strategy_id: int, trade_date: Optional[str] = None, save_all_signals: bool = True) -> dict:
    strategy = QuantStrategy.get_by_id(strategy_id)
    if strategy.status != "active":
        raise ValueError("策略未启用")

    resolved_trade_date = _resolve_trade_date(trade_date)
    rule_config = json.loads(strategy.rule_config_json or "{}")
    history_size = get_required_history_size(rule_config)
    universe = _resolve_universe(strategy, resolved_trade_date)
    run_key = f"strategy-{strategy.id}-{resolved_trade_date.isoformat()}-{uuid.uuid4().hex[:8]}"
    now = datetime.now()

    strategy_run = QuantStrategyRun.create(
        strategy_id=strategy.id,
        run_key=run_key,
        trade_date=resolved_trade_date,
        status="running",
        symbols_total=len(universe),
        signals_total=0,
        summary_json="{}",
        created_at=now,
    )

    passed_rows = 0
    signal_rows = []
    try:
        for symbol in universe:
            history = _load_history(symbol, resolved_trade_date, max(history_size, 2))
            if not history or history[0].trade_date != resolved_trade_date:
                continue
            result = evaluate_strategy_rules(rule_config, history)
            if result["passed"]:
                passed_rows += 1
            if save_all_signals or result["passed"]:
                signal_rows.append(
                    {
                        "run_id": strategy_run.id,
                        "strategy_id": strategy.id,
                        "symbol": symbol,
                        "trade_date": resolved_trade_date,
                        "passed": result["passed"],
                        "score": result["score"],
                        "signal_type": result["signal_type"],
                        "reasons_json": json.dumps(result["reasons"], ensure_ascii=False),
                        "metrics_json": json.dumps(result["metrics"], ensure_ascii=False),
                        "created_at": now,
                    }
                )

        with quant_db.atomic():
            if signal_rows:
                QuantStrategySignal.insert_many(signal_rows).execute()

        summary = {
            "strategy_name": strategy.name,
            "trade_date": resolved_trade_date.isoformat(),
            "symbols_total": len(universe),
            "signals_total": passed_rows,
            "rule_count": len(rule_config.get("rules", [])),
        }
        strategy_run.status = "success"
        strategy_run.signals_total = passed_rows
        strategy_run.summary_json = json.dumps(summary, ensure_ascii=False)
        strategy_run.finished_at = datetime.now()
        strategy_run.save()
        return strategy_run.to_dict()
    except Exception as exc:
        strategy_run.status = "failed"
        strategy_run.error_message = str(exc)
        strategy_run.finished_at = datetime.now()
        strategy_run.save()
        raise


def list_strategy_runs(strategy_id: Optional[int] = None, limit: int = 50) -> List[dict]:
    query = QuantStrategyRun.select()
    if strategy_id:
        query = query.where(QuantStrategyRun.strategy_id == strategy_id)
    query = query.order_by(QuantStrategyRun.id.desc()).limit(limit)
    return [item.to_dict() for item in query.iterator()]


def list_strategy_signals(
    strategy_id: Optional[int] = None,
    run_id: Optional[int] = None,
    passed_only: bool = False,
    limit: int = 200,
) -> List[dict]:
    query = QuantStrategySignal.select()
    if strategy_id:
        query = query.where(QuantStrategySignal.strategy_id == strategy_id)
    if run_id:
        query = query.where(QuantStrategySignal.run_id == run_id)
    if passed_only:
        query = query.where(QuantStrategySignal.passed == True)
    query = query.order_by(QuantStrategySignal.id.desc()).limit(limit)
    return [item.to_dict() for item in query.iterator()]


def list_available_symbols(limit: int = 500) -> List[dict]:
    query = QuantInstrument.select().where(QuantInstrument.status == "active").order_by(QuantInstrument.symbol.asc()).limit(limit)
    return [
        {
            "symbol": item.symbol,
            "code": item.code,
            "exchange": item.exchange,
            "market": item.market,
            "name": item.name,
        }
        for item in query.iterator()
    ]
