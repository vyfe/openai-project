from __future__ import annotations

from datetime import datetime
from typing import Optional

from quant.entities import QuantPromptTemplate


DEFAULT_REPORT_TEMPLATE = """你是量化研究助理。基于结构化 AnalysisBundle 输出受约束的 ReportDraft。
规则：
1. 不得虚构 bundle 中不存在的数值。
2. 数值必须引用 bundle 中已有字段。
3. 记忆仅用于解释增强，不得替代当天信号。
4. 输出应包含摘要、信号概览、风险、动作建议、记忆引用。
"""


def normalize_report_type(report_type: str) -> str:
    text = str(report_type or "test_report").strip()
    return text or "test_report"


def latest_prompt(strategy_id: Optional[int] = None, report_type: str = "test_report") -> Optional[dict]:
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
        report_type=normalize_report_type(report_type),
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
        record.report_type = normalize_report_type(updates["report_type"])
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
