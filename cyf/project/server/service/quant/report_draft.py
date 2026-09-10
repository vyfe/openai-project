"""ReportDraft 生成（模板 + LLM 改写路径）。

从 report_generation_service.py 拆出，让 LLM 路径和模板路径独立可测。
"""
from __future__ import annotations

import logging
from typing import Optional

from service.quant.report_llm_service import (
    LLMCallError,
    LLMContractError,
    rewrite_report_with_llm,
)
from service.quant.report_prompt_service import (
    DEFAULT_REPORT_MODEL_NAME,
    normalize_extra_sections,
    resolve_model_name,
)


logger = logging.getLogger("quant.report.draft")


# schema 版本号（与 generate_report_draft 输出绑定）
REPORT_DRAFT_VERSION = "report-draft-v1"


def _validate_analysis_bundle(bundle: dict):
    """检查 AnalysisBundle 关键字段齐备。"""
    for key in ("bundle_version", "prompt_version", "strategy", "run", "signals", "top_signals", "memory_snippets", "risk_flags"):
        if key not in bundle:
            raise ValueError(f"AnalysisBundle 缺少字段: {key}")


def _validate_report_draft(report_draft: dict, allowed_extra_titles: Optional[set] = None):
    """检查 ReportDraft 关键字段齐备。

    custom_sections 是可选扩展段：缺省视为空列表；非 list 抛错；
    每项必须是 dict 且含 title / body_md 两个字符串字段。

    allowed_extra_titles：模板声明的 extra_sections 段标题集合（None 或空集合 = 不限制）；
    传入时，LLM 返回的 custom_sections[*].title 必须落在集合内，否则 raise。
    """
    for key in (
        "title", "summary", "market_view", "signal_highlights",
        "risk_warnings", "action_watchlist", "memory_references", "footer_notes",
    ):
        if key not in report_draft:
            raise ValueError(f"ReportDraft 缺少字段: {key}")
    custom_sections = report_draft.get("custom_sections", [])
    if not isinstance(custom_sections, list):
        raise ValueError("ReportDraft.custom_sections 必须是 list")
    if len(custom_sections) > 3:
        raise ValueError("ReportDraft.custom_sections 最多 3 段")
    if allowed_extra_titles is not None and not isinstance(allowed_extra_titles, set):
        allowed_extra_titles = set(allowed_extra_titles)
    for idx, section in enumerate(custom_sections):
        if not isinstance(section, dict):
            raise ValueError(f"ReportDraft.custom_sections[{idx}] 必须是 dict")
        title = section.get("title")
        if not isinstance(title, str):
            raise ValueError(f"ReportDraft.custom_sections[{idx}].title 必须是 str")
        if not isinstance(section.get("body_md"), str):
            raise ValueError(f"ReportDraft.custom_sections[{idx}].body_md 必须是 str")
        if allowed_extra_titles is not None and title.strip() not in allowed_extra_titles:
            raise ValueError(
                f"ReportDraft.custom_sections[{idx}].title={title!r} "
                f"不在模板声明的 extra_sections 集合 {sorted(allowed_extra_titles)!r} 内"
            )


def _top_signal_lines(bundle: dict) -> list[str]:
    """top_signals 转人类可读单行描述（中文标点分隔），用 signal.name / symbol 兜底。"""
    lines = []
    for signal in bundle.get("top_signals", [])[:5]:
        reasons = "；".join((signal.get("reasons") or [])[:2]) or "规则通过"
        label = signal.get("name") or signal.get("symbol")
        lines.append(
            f"{label} 得分 {signal.get('score')}，收盘 {signal.get('close_price')}，涨跌幅 {signal.get('pct_change')}%：{reasons}"
        )
    return lines


def _build_template_draft(
    bundle: dict,
    memory_refs: list[str],
    operator_notes: list[dict],
    llm_status: str,
) -> dict:
    """deterministic 模板生成 ReportDraft（不走 LLM）。"""
    strategy = bundle["strategy"]
    run = bundle["run"]
    market_summary = bundle.get("market_summary") or {}
    risk_lines = [item.get("message") for item in bundle.get("risk_flags", []) if item.get("message")]
    market_view = []
    if market_summary.get("avg_pct_change") is not None:
        market_view.append(
            f"本次信号样本平均涨跌幅 `{market_summary.get('avg_pct_change')}`%，"
            f"平均换手 `{market_summary.get('avg_turnover_rate')}`%。"
        )
    if not market_view:
        market_view.append("当前样本不足以形成稳定市场概览，报告以规则信号解释为主。")
    footer_notes = [
        f"Bundle 版本 `{bundle.get('bundle_version')}`，Prompt 版本 `{bundle.get('prompt_version')}`。",
        "所有数值字段均来自结构化 AnalysisBundle，当前未启用自由生成数值。",
    ]
    if operator_notes:
        footer_notes.append(f"最近人工备注共 {len(operator_notes)} 条，已纳入解释上下文预算。")
    if llm_status.startswith("fallback"):
        footer_notes.append(f"AI 改写未启用 / 失败（{llm_status}），当前为 deterministic 模板兜底。")

    signal_lines = _top_signal_lines(bundle)
    draft = {
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
            "如需形成长期经验，请在执行后及时回填结果，以便记忆梳理任务吸收。",
        ],
        "memory_references": memory_refs,
        "custom_sections": [],
        "footer_notes": footer_notes,
        "prompt_version": (bundle.get("prompt_version") or "template-v1"),
        "disclaimer": "数值字段禁止由 LLM 自由生成；当前为模板化测试报告。",
        "llm_status": llm_status,
        "model_name": bundle.get("model_name") or DEFAULT_REPORT_MODEL_NAME,
    }
    # alias 字段：render_markdown 读这些别名
    draft["signal_overview"] = draft["signal_highlights"]
    draft["risk_alerts"] = draft["risk_warnings"]
    draft["suggested_actions"] = draft["action_watchlist"]
    return draft


def generate_report_draft(
    bundle: dict,
    prompt_template: Optional[dict] = None,
    *,
    llm_enabled: bool = False,
    model_name: str = "",
    username: str = "system",
) -> dict:
    """生成 ReportDraft。

    llm_enabled=True 且 prompt_template 不为空时：调 LLM 改写。
    LLM 失败（合同 / 调用异常）自动 fallback 到模板，并在 footer + llm_status 标记。
    """
    _validate_analysis_bundle(bundle)
    strategy = bundle["strategy"]
    run = bundle["run"]
    memory_refs = [item["symbol"] for item in bundle.get("memory_snippets", [])]
    operator_notes = bundle.get("operator_notes") or []
    resolved_model = (
        resolve_model_name(prompt_template) if prompt_template else (model_name or DEFAULT_REPORT_MODEL_NAME)
    )
    # 模板声明的额外段落（标题集合）—— LLM 改写成功后用于校验 custom_sections 标题。
    allowed_extra_titles: Optional[set] = None
    if prompt_template:
        extra = normalize_extra_sections(prompt_template.get("extra_sections"))
        if extra:
            allowed_extra_titles = {item["title"] for item in extra}

    if llm_enabled and prompt_template:
        try:
            llm_draft = rewrite_report_with_llm(
                bundle=bundle,
                prompt_template=prompt_template,
                model_name=model_name,
                username=username,
                allowed_extra_titles=allowed_extra_titles,
            )
            llm_draft["llm_status"] = "success"
            llm_draft["model_name"] = resolved_model
            llm_draft.setdefault("memory_references", memory_refs)
            return llm_draft
        except LLMContractError as exc:
            logger.warning("LLM 改写 contract 失败，fallback 到模板: %s", exc)
            llm_status = "fallback_contract"
        except LLMCallError as exc:
            logger.warning("LLM 改写调用失败，fallback 到模板: %s", exc)
            llm_status = "fallback_call"
    else:
        llm_status = "disabled"

    draft = _build_template_draft(bundle, memory_refs, operator_notes, llm_status)
    return draft
