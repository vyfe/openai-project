import json
import logging
import uuid
from datetime import datetime
from typing import Dict, Iterable, List, Optional

from peewee import fn

from quant.db import quant_db


logger = logging.getLogger("quant.strategy")
from quant.entities import (
    QuantDailyBar,
    QuantInstrument,
    QuantStrategy,
    QuantStrategyRun,
    QuantStrategySignal,
)
from service.quant.common import normalize_symbol, parse_trade_date
from service.quant.indicator_service import compute_indicators
from service.quant.rule_engine import (
    INDICATOR_RULE_TYPES,
    evaluate_series,
    evaluate_strategy_rules,
    get_required_history_size_v2,
)
from service.quant.rule_migration import migrate_v1_to_v2


def _normalize_symbols(raw_symbols) -> List[str]:
    symbols = raw_symbols or []
    if isinstance(symbols, str):
        symbols = [item.strip() for item in symbols.split(",") if item.strip()]
    return [normalize_symbol(item) for item in symbols]


def _normalize_rule_config(rule_config) -> Dict:
    """读时迁移：DB 里 v1 配置自动转 v2（不写库，用户下次保存才落 v2）。

    已在 v2 时直接返回（幂等）。
    """
    if rule_config is None:
        return migrate_v1_to_v2({})
    if isinstance(rule_config, str):
        return migrate_v1_to_v2(json.loads(rule_config))
    if isinstance(rule_config, dict):
        return migrate_v1_to_v2(rule_config)
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


def _rule_config_uses_indicators(rule_config: Dict) -> bool:
    rules = rule_config.get("rules") or []
    if not isinstance(rules, list):
        return False
    # v2 形态：expr 字符串里引用了 macd_/kdj_/td_/bottom_divergence 任一即算
    for r in rules:
        if not isinstance(r, dict):
            continue
        expr = str(r.get("expr") or "")
        if any(token in expr for token in ("macd_", "kdj_", "td_signal", "bottom_divergence")):
            return True
    return any(str(r.get("rule_type", r.get("type", ""))).strip() in INDICATOR_RULE_TYPES for r in rules)


def _build_indicator_context(history: List[QuantDailyBar], rule_config: Dict) -> Dict[str, Dict]:
    """按 v2 表达式实际引用的指标精确计算（不再硬编码 macd/kdj/td/bottom 全算）。"""
    if not history:
        return {}
    asc_history = list(reversed(history))
    names: list[str] = []
    expr_blob = " ".join(str(r.get("expr") or "") for r in (rule_config.get("rules") or []))
    if "macd_" in expr_blob:
        names.append("macd")
    if "kdj_" in expr_blob:
        names.append("kdj")
    if "td_signal" in expr_blob:
        names.append("td_sequential")
    if "bottom_divergence" in expr_blob:
        names.append("bottom_structure")
    return compute_indicators(asc_history, indicator_names=names or None)


def run_strategy(strategy_id: int, trade_date: Optional[str] = None, save_all_signals: bool = True) -> dict:
    strategy = QuantStrategy.get_by_id(strategy_id)
    if strategy.status != "active":
        raise ValueError("策略未启用")

    resolved_trade_date = _resolve_trade_date(trade_date)
    raw_rule_config = json.loads(strategy.rule_config_json or "{}")
    rule_config = _normalize_rule_config(raw_rule_config)  # v1 自动迁移到 v2
    history_size = get_required_history_size_v2(rule_config)
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
    needs_indicator_context = _rule_config_uses_indicators(rule_config)
    try:
        for symbol in universe:
            history = _load_history(symbol, resolved_trade_date, max(history_size, 2))
            if not history or history[0].trade_date != resolved_trade_date:
                continue
            indicator_context = _build_indicator_context(history, rule_config) if needs_indicator_context else None
            # 走 v2 路径：一次算全序列（单 symbol 也享受 v2 表达式能力）
            series_results = evaluate_series(rule_config, history, indicator_context=indicator_context)
            result = series_results[0] if series_results else {
                "passed": False, "score": 0.0, "signal_type": "watch", "reasons": [], "metrics": {},
            }
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


def list_available_symbols(limit: int = 500, offset: int = 0, keyword: Optional[str] = None) -> List[dict]:
    """股票池列表（active）。支持 keyword 模糊匹配（symbol/code/name/custom_name）和 offset 分页。

    每条返回里都带 display_name（custom_name 优先，空时回退到 name），
    供前端 el-select / 列表展示用。
    """
    from service.quant.instrument_display_service import resolve_display_name
    query = QuantInstrument.select().where(QuantInstrument.status == "active")
    if keyword:
        kw = f"%{keyword.strip()}%"
        query = query.where(
            (QuantInstrument.symbol ** kw) |
            (QuantInstrument.code ** kw) |
            (QuantInstrument.name ** kw) |
            (QuantInstrument.custom_name ** kw)
        )
    query = query.order_by(QuantInstrument.symbol.asc()).limit(limit).offset(offset)
    results = []
    for item in query.iterator():
        name = item.name or ""
        custom_name = item.custom_name or ""
        results.append({
            "symbol": item.symbol,
            "code": item.code,
            "exchange": item.exchange,
            "market": item.market,
            "name": name,
            "custom_name": custom_name,
            "display_name": resolve_display_name(item.symbol, custom_name, name),
            "source": item.source,
            "status": item.status,
            "created_at": item.created_at.isoformat() if item.created_at else None,
            "updated_at": item.updated_at.isoformat() if item.updated_at else None,
        })
    return results


def count_available_symbols(keyword: Optional[str] = None) -> int:
    """股票池总数，配合 list_available_symbols 做分页。

    keyword 搜索条件必须与 list_available_symbols 保持完全一致（否则 count 与 list 不一致）。
    """
    query = QuantInstrument.select().where(QuantInstrument.status == "active")
    if keyword:
        kw = f"%{keyword.strip()}%"
        query = query.where(
            (QuantInstrument.symbol ** kw) |
            (QuantInstrument.code ** kw) |
            (QuantInstrument.name ** kw) |
            (QuantInstrument.custom_name ** kw)
        )
    return query.count()


def soft_delete_instrument(symbol: str) -> bool:
    """软删除单个股票池条目。返回是否真正改了状态（false 表示已经是 deleted）。"""
    if not symbol:
        return False
    rows = (
        QuantInstrument.update(status="deleted", updated_at=datetime.now())
        .where(QuantInstrument.symbol == symbol, QuantInstrument.status == "active")
        .execute()
    )
    return rows > 0


def _cascade_soft_delete_bar(symbols: list[str]) -> dict:
    """级联软删除 K 线 / 分时数据。返回各表受影响行数。

    单次 update ... where(symbol.in_(...)) 一条 SQL 完成整批更新，
    避免 per-symbol 循环引起的 N 次 IO。
    """
    from quant.entities import QuantDailyBar, QuantMinuteBar
    now = datetime.now()
    out = {"daily": 0, "minute": 0}
    if not symbols:
        return out
    try:
        out["daily"] = (
            QuantDailyBar.update(status="deleted", updated_at=now)
            .where(QuantDailyBar.symbol.in_(symbols), QuantDailyBar.status == "active")
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("cascade_soft_delete daily failed: %s", exc)
    try:
        out["minute"] = (
            QuantMinuteBar.update(status="deleted", updated_at=now)
            .where(QuantMinuteBar.symbol.in_(symbols), QuantMinuteBar.status == "active")
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("cascade_soft_delete minute failed: %s", exc)
    return out


def soft_delete_instrument(symbol: str) -> bool:
    """软删除单个股票池条目，并级联软删除对应 K 线 / 分时数据。
    返回是否真正改了状态（false 表示已经是 deleted）。
    """
    if not symbol:
        return False
    rows = (
        QuantInstrument.update(status="deleted", updated_at=datetime.now())
        .where(QuantInstrument.symbol == symbol, QuantInstrument.status == "active")
        .execute()
    )
    if rows > 0:
        _cascade_soft_delete_bar([symbol])
    return rows > 0


def batch_soft_delete_instruments(symbols: Iterable[str]) -> dict:
    """批量软删除：股票池 + 级联 K 线 / 分时数据。返回 {deleted, missing, cascade}。"""
    symbol_list = [s for s in (symbols or []) if s]
    if not symbol_list:
        return {"deleted": [], "missing": [], "cascade": {"daily": 0, "minute": 0}}
    active_tuples = (
        QuantInstrument.select(QuantInstrument.symbol)
        .where(QuantInstrument.symbol.in_(symbol_list), QuantInstrument.status == "active")
        .tuples()
    )
    active = {row[0] for row in active_tuples}
    missing = [s for s in symbol_list if s not in active]
    deleted = [s for s in symbol_list if s in active]
    cascade = {"daily": 0, "minute": 0}
    if deleted:
        QuantInstrument.update(status="deleted", updated_at=datetime.now()).where(
            QuantInstrument.symbol.in_(deleted), QuantInstrument.status == "active"
        ).execute()
        cascade = _cascade_soft_delete_bar(deleted)
    return {"deleted": deleted, "missing": missing, "cascade": cascade}
