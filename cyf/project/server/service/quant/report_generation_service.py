from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from typing import Optional

from quant.entities import (
    QuantInstrument,
    QuantOperationRecord,
    QuantReportRecord,
    QuantStrategy,
    QuantStrategyRun,
    QuantStrategySignal,
)
from service.quant.memory_service import extract_memory_snippets
from service.quant.report_draft import (
    REPORT_DRAFT_VERSION,
    _validate_report_draft,
    generate_report_draft,
)
from service.quant.report_prompt_service import (
    latest_prompt,
    normalize_report_type,
)


logger = logging.getLogger("quant.report")


ANALYSIS_BUNDLE_VERSION = "analysis-bundle-v1"


def _load_strategy_run(run_id: int) -> QuantStrategyRun:
    return QuantStrategyRun.get_by_id(run_id)


def _load_strategy(strategy_id: int) -> QuantStrategy:
    return QuantStrategy.get_by_id(strategy_id)


def _load_run_signals(run_id: int, limit: int = 20) -> list[dict]:
    query = (
        QuantStrategySignal.select()
        .where(QuantStrategySignal.run_id == run_id)
        .order_by(QuantStrategySignal.passed.desc(), QuantStrategySignal.score.desc(), QuantStrategySignal.id.asc())
        .limit(limit)
    )
    return [item.to_dict() for item in query.iterator()]


def _bulk_lookup_instrument_names(symbols: list) -> dict:
    """批量查 quant_instrument.name；空字符串表示该 symbol 在股票池里没有 name。"""
    cleaned = sorted({str(s).strip() for s in symbols if str(s or "").strip()})
    if not cleaned:
        return {}
    rows = QuantInstrument.select(QuantInstrument.symbol, QuantInstrument.name).where(
        QuantInstrument.symbol.in_(cleaned)
    )
    return {row.symbol: (row.name or "") for row in rows}


def _load_recent_operations(strategy_id: int, trade_date, limit: int = 10) -> list[dict]:
    query = (
        QuantOperationRecord.select()
        .where((QuantOperationRecord.strategy_id == strategy_id) & (QuantOperationRecord.trade_date <= trade_date))
        .order_by(QuantOperationRecord.trade_date.desc(), QuantOperationRecord.id.desc())
        .limit(limit)
    )
    return [item.to_dict() for item in query.iterator()]


def _strategy_version(strategy: QuantStrategy) -> str:
    payload = strategy.to_dict().get("rule_config", {}) or {}
    version = str(payload.get("strategy_version", "")).strip()
    return version or "strategy-v1"


def _build_top_signals(signals: list[dict], limit: int = 5, name_map: Optional[dict] = None) -> list[dict]:
    items = []
    name_map = name_map or {}
    for signal in signals[:limit]:
        metrics = signal.get("metrics") or {}
        symbol = signal.get("symbol")
        items.append(
            {
                "symbol": symbol,
                "name": name_map.get(symbol, ""),
                "score": signal.get("score"),
                "signal_type": signal.get("signal_type"),
                "passed": signal.get("passed"),
                "trade_date": signal.get("trade_date"),
                "close_price": metrics.get("close_price"),
                "pct_change": metrics.get("pct_change"),
                "turnover_rate": metrics.get("turnover_rate"),
                "reasons": (signal.get("reasons") or [])[:3],
            }
        )
    return items


def _build_risk_flags(run: dict, operations_snapshot: list[dict], signals: list[dict]) -> list[dict]:
    flags = []
    if not run.get("signals_total"):
        flags.append({"code": "NO_PASS_SIGNAL", "level": "warning", "message": "本次没有通过信号，需检查数据完整性或规则阈值。"})
    pending_reviews = [item for item in operations_snapshot if item.get("status") in ("draft", "executed") and not item.get("result_status")]
    if pending_reviews:
        flags.append(
            {
                "code": "OPERATIONS_PENDING_REVIEW",
                "level": "info",
                "message": f"最近仍有 {len(pending_reviews)} 条人工操作未闭环，经验归纳应谨慎解读。",
            }
        )
    weak_scores = [item for item in signals[:5] if float(item.get("score") or 0) < 1]
    if weak_scores:
        flags.append({"code": "WEAK_SIGNAL_SCORE", "level": "info", "message": "当前靠前信号得分偏低，建议只作为观察名单。"})
    return flags


def _build_market_summary(signals: list[dict]) -> dict:
    metrics = [item.get("metrics") or {} for item in signals if item.get("metrics")]
    pct_values = [float(item["pct_change"]) for item in metrics if item.get("pct_change") is not None]
    turnover_values = [float(item["turnover_rate"]) for item in metrics if item.get("turnover_rate") is not None]
    return {
        "sample_size": len(metrics),
        "avg_pct_change": round(sum(pct_values) / len(pct_values), 4) if pct_values else None,
        "avg_turnover_rate": round(sum(turnover_values) / len(turnover_values), 4) if turnover_values else None,
    }


def _build_operator_notes(operations_snapshot: list[dict], limit: int = 3) -> list[str]:
    notes = []
    for item in operations_snapshot[:limit]:
        fragments = [item.get("execution_note") or "", item.get("review_note") or "", item.get("thesis") or ""]
        text = "；".join([fragment.strip() for fragment in fragments if str(fragment or "").strip()])[:120]
        if not text:
            continue
        notes.append(f"{item.get('trade_date')} {item.get('symbol')} {item.get('action')}：{text}")
    return notes


def build_analysis_bundle(run_id: int, report_type: str = "test_report", prompt_template: Optional[dict] = None) -> dict:
    strategy_run = _load_strategy_run(run_id)
    strategy = _load_strategy(strategy_run.strategy_id)
    signals = _load_run_signals(run_id)
    operations_snapshot = _load_recent_operations(strategy.id, strategy_run.trade_date)
    symbols = [item["symbol"] for item in signals if item.get("passed")] or [item["symbol"] for item in signals[:5]]
    prompt_template = prompt_template or latest_prompt(strategy.id, report_type=normalize_report_type(report_type))
    run_dict = strategy_run.to_dict()
    strategy_dict = strategy.to_dict()
    # top_signals 涉及的 symbol 批量查股票中文名（供报告渲染与 LLM 改写使用）
    top_symbols = [s.get("symbol") for s in signals[:5] if s.get("symbol")]
    name_map = _bulk_lookup_instrument_names(top_symbols)
    risk_flags = _build_risk_flags(run_dict, operations_snapshot, signals)
    bundle = {
        "bundle_version": ANALYSIS_BUNDLE_VERSION,
        "report_type": normalize_report_type(report_type),
        "prompt_version": (prompt_template or {}).get("prompt_version", "template-v1"),
        "market": strategy.market,
        "timezone": "Asia/Shanghai",
        "as_of": (strategy_run.finished_at or strategy_run.created_at or datetime.now()).isoformat(),
        "field_conventions": {
            "datetime": "ISO-8601",
            "price_unit": "CNY",
            "pct_change_unit": "percent_value",
            "pass_rate_unit": "ratio_0_1",
            "missing_value": None,
        },
        "strategy": {
            "id": strategy.id,
            "name": strategy.name,
            "status": strategy.status,
            "market": strategy.market,
            "strategy_version": _strategy_version(strategy),
            "description": strategy.description,
            "symbols": strategy_dict.get("symbols", []),
        },
        "run": run_dict,
        "symbols": symbols,
        "signal_summary": {
            "signals_total": strategy_run.signals_total,
            "symbols_total": strategy_run.symbols_total,
            "pass_rate": round(strategy_run.signals_total / strategy_run.symbols_total, 6) if strategy_run.symbols_total else 0.0,
        },
        "top_signals": _build_top_signals(signals, name_map=name_map),
        "signals": signals,
        "risk_flags": risk_flags,
        "operations_snapshot": operations_snapshot,
        "portfolio_snapshot": {
            "recent_operations_total": len(operations_snapshot),
            "open_or_pending_total": len([item for item in operations_snapshot if item.get("status") in ("draft", "executed")]),
        },
        "market_summary": _build_market_summary(signals),
        "memory_snippets": extract_memory_snippets(symbols),
        "operator_notes": _build_operator_notes(operations_snapshot),
        "token_budget": {
            "signal_limit": len(signals),
            "memory_limit": len(symbols[:6]),
            "operator_note_limit": min(len(operations_snapshot), 3),
        },
    }
    return bundle




def render_report_markdown(bundle: dict, report_draft: dict) -> str:
    _validate_report_draft(report_draft)
    sections = [
        f"# {report_draft['title']}",
        "",
        "## 摘要",
        *[f"- {line}" for line in report_draft["summary"]],
        "",
        "## 市场观察",
        *[f"- {line}" for line in report_draft["market_view"]],
        "",
        "## 信号概览",
        *[f"- {line}" for line in report_draft["signal_highlights"]],
        "",
        "## 风险提示",
        *[f"- {line}" for line in report_draft["risk_warnings"]],
        "",
        "## 建议动作",
        *[f"- {line}" for line in report_draft["action_watchlist"]],
        "",
        "## 记忆引用",
        *([f"- {symbol}" for symbol in report_draft["memory_references"]] or ["- 本次没有命中可用的长期记忆。"]),
        "",
        "## 契约说明",
        f"- Bundle 版本: `{bundle.get('bundle_version')}`",
        f"- Prompt 版本: `{report_draft.get('prompt_version')}`",
        f"- 免责声明: {report_draft.get('disclaimer')}",
        *[f"- {line}" for line in report_draft.get("footer_notes", [])],
        "",
    ]
    return "\n".join(sections)


def create_report_for_run(
    run_id: int,
    report_type: str = "test_report",
    schedule_run_id: Optional[int] = None,
    *,
    prompt_template_id: Optional[int] = None,
    llm_enabled: bool = False,
    model_name: str = "",
    username: str = "system",
) -> dict:
    """生成并落库一条报告。

    prompt_template_id：指定具体模板；None 时走 latest_prompt 自动选。
    llm_enabled：是否走 LLM 改写（失败自动兜底）。
    model_name：覆盖 prompt_template 默认模型。
    """
    report_type = normalize_report_type(report_type)
    strategy_run = _load_strategy_run(run_id)
    if prompt_template_id is not None:
        from service.quant.report_prompt_service import get_prompt_template
        try:
            prompt_template = get_prompt_template(int(prompt_template_id))
        except Exception:
            prompt_template = latest_prompt(strategy_run.strategy_id, report_type=report_type)
    else:
        prompt_template = latest_prompt(strategy_run.strategy_id, report_type=report_type)
    bundle = build_analysis_bundle(run_id, report_type=report_type, prompt_template=prompt_template)
    report_draft = generate_report_draft(
        bundle,
        prompt_template=prompt_template,
        llm_enabled=llm_enabled,
        model_name=model_name,
        username=username,
    )
    markdown = render_report_markdown(bundle, report_draft)
    run = bundle["run"]
    record = QuantReportRecord.create(
        report_key=f"report-{run_id}-{report_type}-{uuid.uuid4().hex[:8]}",
        strategy_id=int(run["strategy_id"]),
        run_id=run_id,
        schedule_run_id=schedule_run_id,
        trade_date=datetime.strptime(run["trade_date"], "%Y-%m-%d").date(),
        report_type=report_type,
        status="success",
        bundle_version=bundle["bundle_version"],
        prompt_version=report_draft.get("prompt_version", "template-v1"),
        title=report_draft["title"],
        analysis_bundle_json=json.dumps(bundle, ensure_ascii=False),
        report_draft_json=json.dumps(report_draft, ensure_ascii=False),
        final_markdown=markdown,
        memory_references_json=json.dumps(report_draft["memory_references"], ensure_ascii=False),
        meta_json=json.dumps(
            {
                "prompt_template_id": (prompt_template or {}).get("id"),
                "model_name": report_draft.get("model_name") or model_name or "template-engine",
                "llm_status": report_draft.get("llm_status", "disabled"),
                "report_type": report_type,
                "model_params": {"mode": "deterministic", "report_type": report_type},
                "token_budget": bundle.get("token_budget", {}),
                "generated_at": datetime.now().isoformat(),
            },
            ensure_ascii=False,
        ),
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    return record.to_dict()


def list_reports(strategy_id: Optional[int] = None, run_id: Optional[int] = None, limit: int = 100) -> list[dict]:
    query = QuantReportRecord.select().order_by(QuantReportRecord.id.desc()).limit(limit)
    if strategy_id:
        query = query.where(QuantReportRecord.strategy_id == strategy_id)
    if run_id:
        query = query.where(QuantReportRecord.run_id == run_id)
    return [item.to_dict() for item in query.iterator()]


def preview_report_for_run(
    run_id: int,
    report_type: str = "test_report",
    *,
    prompt_template_id: Optional[int] = None,
    llm_enabled: bool = False,
    model_name: str = "",
    username: str = "system",
) -> dict:
    """不落库的"报告 IDE"：返回 bundle + draft + markdown + meta，供前端调试 / 预览用。

    与 create_report_for_run 几乎一致，唯一区别是不写 QuantReportRecord。
    """
    report_type = normalize_report_type(report_type)
    strategy_run = _load_strategy_run(run_id)
    if prompt_template_id is not None:
        from service.quant.report_prompt_service import get_prompt_template
        try:
            prompt_template = get_prompt_template(int(prompt_template_id))
        except Exception:
            prompt_template = latest_prompt(strategy_run.strategy_id, report_type=report_type)
    else:
        prompt_template = latest_prompt(strategy_run.strategy_id, report_type=report_type)
    bundle = build_analysis_bundle(run_id, report_type=report_type, prompt_template=prompt_template)
    report_draft = generate_report_draft(
        bundle,
        prompt_template=prompt_template,
        llm_enabled=llm_enabled,
        model_name=model_name,
        username=username,
    )
    markdown = render_report_markdown(bundle, report_draft)
    return {
        "bundle": bundle,
        "draft": report_draft,
        "markdown": markdown,
        "meta": {
            "prompt_template_id": (prompt_template or {}).get("id"),
            "prompt_version": (prompt_template or {}).get("prompt_version", "template-v1"),
            "model_name": report_draft.get("model_name") or model_name or "template-engine",
            "llm_status": report_draft.get("llm_status", "disabled"),
            "report_type": report_type,
            "run_id": run_id,
            "strategy_id": int(strategy_run.strategy_id),
        },
    }


def get_report(report_id: int) -> dict:
    return QuantReportRecord.get_by_id(report_id).to_dict()
