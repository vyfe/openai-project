from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Optional

from quant.entities import (
    QuantOperationRecord,
    QuantPromptTemplate,
    QuantReportRecord,
    QuantStrategy,
    QuantStrategyRun,
    QuantStrategySignal,
)
from service.quant.memory_service import extract_memory_snippets


ANALYSIS_BUNDLE_VERSION = "analysis-bundle-v1"
REPORT_DRAFT_VERSION = "report-draft-v1"
DEFAULT_REPORT_TEMPLATE = """你是量化研究助理。基于结构化 AnalysisBundle 输出受约束的 ReportDraft。\n规则：\n1. 不得虚构 bundle 中不存在的数值。\n2. 数值必须引用 bundle 中已有字段。\n3. 记忆仅用于解释增强，不得替代当天信号。\n4. 输出应包含摘要、信号概览、风险、动作建议、记忆引用。\n"""


def _normalize_report_type(report_type: str) -> str:
    text = str(report_type or "test_report").strip()
    return text or "test_report"


def _latest_prompt(strategy_id: Optional[int] = None, report_type: str = "test_report") -> Optional[dict]:
    query = (
        QuantPromptTemplate.select()
        .where((QuantPromptTemplate.status == "active") & (QuantPromptTemplate.report_type == report_type))
        .order_by(QuantPromptTemplate.id.desc())
    )
    if strategy_id is not None:
        strategy_prompt = query.where(QuantPromptTemplate.strategy_id == strategy_id).first()
        if strategy_prompt:
            return strategy_prompt.to_dict()
    global_prompt = query.where(QuantPromptTemplate.strategy_id.is_null(True)).first()
    return global_prompt.to_dict() if global_prompt else None


def list_prompt_templates(strategy_id: Optional[int] = None, report_type: Optional[str] = None) -> list[dict]:
    query = QuantPromptTemplate.select().order_by(QuantPromptTemplate.id.desc())
    if strategy_id is not None:
        query = query.where(QuantPromptTemplate.strategy_id == strategy_id)
    if report_type:
        query = query.where(QuantPromptTemplate.report_type == report_type)
    return [item.to_dict() for item in query.iterator()]


def get_prompt_template(template_id: int) -> dict:
    return QuantPromptTemplate.get_by_id(template_id).to_dict()


def create_prompt_template(
    *,
    prompt_version: str,
    prompt_template: str,
    strategy_id=None,
    template_name: str = "default",
    status: str = "active",
    report_type: str = "test_report",
    change_note: str = "",
) -> dict:
    if not str(prompt_version or "").strip():
        raise ValueError("prompt_version 不能为空")
    record = QuantPromptTemplate.create(
        strategy_id=int(strategy_id) if strategy_id not in (None, "") else None,
        template_name=str(template_name or "default").strip() or "default",
        prompt_version=str(prompt_version).strip(),
        status=str(status or "active").strip() or "active",
        report_type=_normalize_report_type(report_type),
        prompt_template=str(prompt_template or "").strip() or DEFAULT_REPORT_TEMPLATE,
        change_note=str(change_note or "").strip(),
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    return record.to_dict()


def update_prompt_template(template_id: int, **updates) -> dict:
    record = QuantPromptTemplate.get_by_id(template_id)
    if "strategy_id" in updates:
        record.strategy_id = int(updates["strategy_id"]) if updates["strategy_id"] not in (None, "") else None
    if "template_name" in updates:
        record.template_name = str(updates["template_name"] or "default").strip() or "default"
    if "prompt_version" in updates:
        record.prompt_version = str(updates["prompt_version"] or "").strip()
    if "status" in updates:
        record.status = str(updates["status"] or "active").strip() or "active"
    if "report_type" in updates:
        record.report_type = _normalize_report_type(updates["report_type"])
    if "prompt_template" in updates:
        record.prompt_template = str(updates["prompt_template"] or "").strip() or DEFAULT_REPORT_TEMPLATE
    if "change_note" in updates:
        record.change_note = str(updates["change_note"] or "").strip()
    record.updated_at = datetime.now()
    record.save()
    return record.to_dict()


def delete_prompt_template(template_id: int) -> bool:
    record = QuantPromptTemplate.get_by_id(template_id)
    record.delete_instance()
    return True


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


def _build_top_signals(signals: list[dict], limit: int = 5) -> list[dict]:
    items = []
    for signal in signals[:limit]:
        metrics = signal.get("metrics") or {}
        items.append(
            {
                "symbol": signal.get("symbol"),
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
    prompt_template = prompt_template or _latest_prompt(strategy.id, report_type=_normalize_report_type(report_type))
    run_dict = strategy_run.to_dict()
    strategy_dict = strategy.to_dict()
    risk_flags = _build_risk_flags(run_dict, operations_snapshot, signals)
    bundle = {
        "bundle_version": ANALYSIS_BUNDLE_VERSION,
        "report_type": _normalize_report_type(report_type),
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
        "top_signals": _build_top_signals(signals),
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


def _validate_analysis_bundle(bundle: dict):
    for key in ("bundle_version", "prompt_version", "strategy", "run", "signals", "top_signals", "memory_snippets", "risk_flags"):
        if key not in bundle:
            raise ValueError(f"AnalysisBundle 缺少字段: {key}")


def _top_signal_lines(bundle: dict) -> list[str]:
    lines = []
    for signal in bundle.get("top_signals", [])[:5]:
        reasons = "；".join((signal.get("reasons") or [])[:2]) or "规则通过"
        lines.append(
            f"{signal.get('symbol')} 得分 {signal.get('score')}，收盘 {signal.get('close_price')}，涨跌幅 {signal.get('pct_change')}%：{reasons}"
        )
    return lines


def generate_report_draft(bundle: dict, prompt_template: Optional[dict] = None) -> dict:
    _validate_analysis_bundle(bundle)
    strategy = bundle["strategy"]
    run = bundle["run"]
    memory_refs = [item["symbol"] for item in bundle.get("memory_snippets", [])]
    signal_lines = _top_signal_lines(bundle)
    market_summary = bundle.get("market_summary") or {}
    risk_lines = [item.get("message") for item in bundle.get("risk_flags", []) if item.get("message")]
    operator_notes = bundle.get("operator_notes") or []
    market_view = []
    if market_summary.get("avg_pct_change") is not None:
        market_view.append(
            f"本次信号样本平均涨跌幅 `{market_summary.get('avg_pct_change')}`%，平均换手 `{market_summary.get('avg_turnover_rate')}`%。"
        )
    if not market_view:
        market_view.append("当前样本不足以形成稳定市场概览，报告以规则信号解释为主。")
    footer_notes = [
        f"Bundle 版本 `{bundle.get('bundle_version')}`，Prompt 版本 `{bundle.get('prompt_version')}`。",
        "所有数值字段均来自结构化 AnalysisBundle，当前未启用自由生成数值。",
    ]
    if operator_notes:
        footer_notes.append(f"最近人工备注共 {len(operator_notes)} 条，已纳入解释上下文预算。")
    report_draft = {
        "draft_version": REPORT_DRAFT_VERSION,
        "title": f"{strategy['name']} · {run['trade_date']} 测试报告",
        "summary": [
            f"本次扫描 {run['symbols_total']} 个标的，通过 {run['signals_total']} 个。",
            "当前报告为结构化测试报告，数值均来源于 AnalysisBundle，不依赖自由生成。",
        ],
        "market_view": market_view,
        "signal_highlights": signal_lines or ["本次没有通过信号，建议检查数据是否完整或规则是否过严。"],
        "risk_warnings": risk_lines or [
            "该报告仅用于研究和测试，不构成自动交易指令。",
            "若当天未完成数据拉取或有大量失败任务，需优先核对样本完整性。",
        ],
        "action_watchlist": [
            "优先复核得分最高的前 3 个标的，再决定是否进入人工操作登记。",
            "如需形成长期经验，请在执行后及时回填结果，以便记忆梳理任务吸收。"
        ],
        "memory_references": memory_refs,
        "footer_notes": footer_notes,
        "prompt_version": (prompt_template or {}).get("prompt_version", "template-v1"),
        "disclaimer": "数值字段禁止由 LLM 自由生成；当前为模板化测试报告。",
    }
    report_draft["signal_overview"] = report_draft["signal_highlights"]
    report_draft["risk_alerts"] = report_draft["risk_warnings"]
    report_draft["suggested_actions"] = report_draft["action_watchlist"]
    return report_draft


def _validate_report_draft(report_draft: dict):
    for key in (
        "title",
        "summary",
        "market_view",
        "signal_highlights",
        "risk_warnings",
        "action_watchlist",
        "memory_references",
        "footer_notes",
    ):
        if key not in report_draft:
            raise ValueError(f"ReportDraft 缺少字段: {key}")


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


def create_report_for_run(run_id: int, report_type: str = "test_report", schedule_run_id: Optional[int] = None) -> dict:
    report_type = _normalize_report_type(report_type)
    strategy_run = _load_strategy_run(run_id)
    prompt_template = _latest_prompt(strategy_run.strategy_id, report_type=report_type)
    bundle = build_analysis_bundle(run_id, report_type=report_type, prompt_template=prompt_template)
    report_draft = generate_report_draft(bundle, prompt_template=prompt_template)
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
                "model_name": "template-engine",
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


def get_report(report_id: int) -> dict:
    return QuantReportRecord.get_by_id(report_id).to_dict()
