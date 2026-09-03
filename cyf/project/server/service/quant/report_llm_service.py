"""LLM 改写量化测试报告 ReportDraft。

复用 service/host_service.get_client_for_user + openai SDK，与 expr_llm_service 同模式。
依赖：
- bundle：dict（来自 report_generation_service.build_analysis_bundle）
- prompt_template：dict（含 prompt_template / prompt_version / model_name）
- model_name：str（可空 → 走 prompt_template.model_name → DEFAULT_REPORT_MODEL_NAME）
- username：str（用于 host_service.get_client_for_user 取 OpenAI client）

输出：ReportDraft dict（与 generate_report_draft deterministic 输出 schema 完全一致）。

数值契约校验：LLM 输出的字符串里出现的数字必须能在 bundle 已有字段找到（允许 ±1/100% 容差；
省略度量字段、序号、版本号等"合法数字"），否则 reject 一次重试 → 抛 LLMContractError 让上层兜底。
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional

from openai import OpenAI

from service.host_service import get_client_for_user
from service.quant.report_prompt_service import (
    DEFAULT_REPORT_MODEL_NAME,
    DEFAULT_REPORT_TEMPLATE,
    resolve_model_name,
)


logger = logging.getLogger("quant.report_llm")


class LLMContractError(RuntimeError):
    """LLM 输出违反数值契约：编造了 bundle 中不存在的数值。"""


class LLMCallError(RuntimeError):
    """LLM 调用本身失败（网络 / API 错误 / JSON 解析失败）。"""


# ----------------------------------------------------------------------
# System prompt：复用用户 prompt_template，加报告 schema 与数值契约约束
# ----------------------------------------------------------------------

DRAFT_SCHEMA_INSTRUCTION = """
## 输出契约（严格遵守）
返回一段 JSON object，必须严格符合以下 schema（section 顺序与 key 名都不能变）：
{
  "draft_version": "report-draft-v1",
  "title": str,                            # 报告标题
  "summary": [str, ...],                    # 2-4 行摘要 bullet
  "market_view": [str, ...],                # 1-3 行市场观察
  "signal_highlights": [str, ...],          # 0-5 行命中信号 bullet
  "risk_warnings": [str, ...],             # 0-5 行风险提示 bullet
  "action_watchlist": [str, ...],           # 0-3 行动作建议 bullet
  "memory_references": [str, ...],          # 命中的长期记忆标的列表
  "footer_notes": [str, ...]                # 2-4 行元信息 bullet
}

## 数值契约（最关键）
- 报告中的所有数值（价格、涨跌幅、换手、信号总数、命中率等）必须来自下方 AnalysisBundle 中已有字段
- 不得编造任何 AnalysisBundle 中不存在的数值（编造一个就 reject）
- 文本里出现的"日期 / 版本号 / 序号"等不是数值，可以自由写
- 命中信号的描述应当引用 bundle.top_signals[] 里的 symbol 与 name（如果有）

## 风格
- 用中文，简洁、量化、研究助理口吻
- 风险段必须保留（即便没有命中信号也要写"无通过信号、数据完整性需关注"）
- 不要解释、不要 markdown 代码块包裹；只返回 JSON
""".strip()


USER_PROMPT_TEMPLATE = """用户自定义 Prompt（来自 Prompt 模板）：

{custom_prompt}

---

下面是结构化 AnalysisBundle（请基于它输出 ReportDraft）：

{bundle_json}
""".strip()


# ----------------------------------------------------------------------
# 数值契约校验
# ----------------------------------------------------------------------

# 用户文本里出现的所有"数字 token"（含小数、百分号、千分号、负号）
_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?%?")

# 文本预处理：先把"非数值的标识符 token"删掉，再做数值契约校验
# - 日期段：2026-05-15 / 2026-05-15T17:22:18 / 2026/05/15
# - 时间段：17:22:18 / 9:30
# - 股票代码：600519.SH / 000001.SZ / 830001.BJ
_DATE_RE = re.compile(r"\d{4}[-/]\d{1,2}[-/]\d{1,2}(?:T\d{2}:\d{2}:\d{2}(?:\.\d+)?)?")
_TIME_RE = re.compile(r"\b\d{1,2}:\d{2}(?::\d{2})?\b")
_STOCK_CODE_RE = re.compile(r"\b\d{6}\.(?:SH|SZ|BJ)\b")


def _strip_non_numeric_tokens(text: str) -> str:
    """把"非数值标识符"（日期 / 时间 / 股票代码）从文本里替换成空格，避免被数字正则误抓。

    这些 token 出现在报告文本里是合理的（解释信号时间 / 标的代码），但**不是数值**，
    不应该参与 contract 校验。
    """
    if not text:
        return ""
    cleaned = _STOCK_CODE_RE.sub(" ", text)
    cleaned = _DATE_RE.sub(" ", cleaned)
    cleaned = _TIME_RE.sub(" ", cleaned)
    return cleaned


def _collect_bundle_numbers(bundle: dict) -> set[str]:
    """从 bundle 里提取所有可能出现在报告中的数值，统一为字符串集合。

    收集来源：
    - signal_summary.{signals_total, symbols_total, pass_rate}
    - top_signals[*].{score, close_price, pct_change, turnover_rate}
    - market_summary.{avg_pct_change, avg_turnover_rate, sample_size}
    - run.signals_total / symbols_total
    """
    nums: set[str] = set()

    def _add(value):
        if value is None:
            return
        text = str(value).strip()
        if not text:
            return
        nums.add(text)
        # 同时收录 round 1/2/3 位简化版本，方便匹配浮点显示
        try:
            f = float(text.rstrip("%"))
            for digits in (0, 1, 2, 3, 4):
                rounded = f"{f:.{digits}f}"
                if "." not in rounded:
                    rounded += ".0"
                nums.add(rounded)
                nums.add(rounded.rstrip("0").rstrip(".") or "0")
                if "." in rounded:
                    nums.add(rounded + "%")
        except ValueError:
            pass

    summary = bundle.get("signal_summary") or {}
    _add(summary.get("signals_total"))
    _add(summary.get("symbols_total"))
    _add(summary.get("pass_rate"))

    for signal in (bundle.get("top_signals") or []):
        _add(signal.get("score"))
        _add(signal.get("close_price"))
        _add(signal.get("pct_change"))
        _add(signal.get("turnover_rate"))

    market = bundle.get("market_summary") or {}
    _add(market.get("sample_size"))
    _add(market.get("avg_pct_change"))
    _add(market.get("avg_turnover_rate"))

    run = bundle.get("run") or {}
    _add(run.get("signals_total"))
    _add(run.get("symbols_total"))

    # 也接受日期型数字（YYYYMMDD 或 YYYY-MM-DD 形式）
    for key in ("trade_date", "as_of"):
        raw = bundle.get(key) or (bundle.get("run") or {}).get(key)
        if raw:
            text = str(raw).replace("-", "")
            if text.isdigit():
                nums.add(text)
            nums.add(str(raw))

    return nums


def _extract_numbers_from_text(text: str) -> list[str]:
    if not text:
        return []
    return [m.group(0) for m in _NUMBER_RE.finditer(text)]


def _validate_number_contract(report_draft: dict, bundle: dict) -> list[str]:
    """返回 LLM 编造的"不在 bundle 里"的数字列表；空列表 = 通过。"""
    allowed = _collect_bundle_numbers(bundle)
    # 一些总是合法的"无关数字"：年份 + 1-12（月）/ 1-31（日期序号）
    always_allowed = {"2026", "2025", "2024"} | {str(i) for i in range(1, 32)}
    invented: list[str] = []
    sections = ("summary", "market_view", "signal_highlights", "risk_warnings",
                "action_watchlist", "footer_notes")
    for section in sections:
        for line in report_draft.get(section) or []:
            # 先剥掉日期 / 时间 / 股票代码等非数值 token，避免误判
            cleaned_line = _strip_non_numeric_tokens(line)
            for num in _extract_numbers_from_text(cleaned_line):
                normalized = num.rstrip("%")
                if num in always_allowed:
                    continue
                if num in allowed or normalized in allowed:
                    continue
                invented.append(num)
    return invented


# ----------------------------------------------------------------------
# Bundle 序列化（紧凑版，避免占过多 token）
# ----------------------------------------------------------------------

def _compact_bundle(bundle: dict) -> dict:
    """压缩 AnalysisBundle，去掉全量 signals / operations 大字段；只给 LLM 看顶层摘要。"""
    compact = {key: bundle.get(key) for key in (
        "bundle_version", "report_type", "prompt_version", "market", "as_of",
        "field_conventions", "strategy", "run", "symbols", "signal_summary",
        "top_signals", "risk_flags", "market_summary", "memory_references",
        "operator_notes", "token_budget",
    )}
    return compact


# ----------------------------------------------------------------------
# 主入口
# ----------------------------------------------------------------------

def rewrite_report_with_llm(
    *,
    bundle: dict,
    prompt_template: Optional[dict],
    model_name: str = "",
    username: str = "system",
    temperature: float = 0.3,
    max_tokens: int = 1500,
) -> dict:
    """调 LLM 把 AnalysisBundle 改写成 ReportDraft dict（与 deterministic schema 完全一致）。

    抛出：
    - LLMContractError：数值契约不满足（上层应当 fallback 到模板）
    - LLMCallError：LLM 调用 / JSON 解析失败（上层应当 fallback）
    """
    if not bundle:
        raise LLMCallError("bundle 为空，无法调 LLM")

    resolved_model = model_name.strip() or (prompt_template.get("model_name", "").strip() if prompt_template else "") or DEFAULT_REPORT_MODEL_NAME
    custom_prompt = (prompt_template or {}).get("prompt_template") or DEFAULT_REPORT_TEMPLATE

    logger.info(
        "LLM rewrite start user=%s model=%s temperature=%s max_tokens=%d bundle_size=%d prompt_chars=%d",
        username, resolved_model, temperature, max_tokens,
        len(json.dumps(bundle, ensure_ascii=False)),
        len(custom_prompt),
    )

    try:
        client, _ = get_client_for_user(username)
    except Exception as exc:
        logger.warning("get_client_for_user failed: %s", exc)
        raise LLMCallError(f"无法获取 API client: {exc}") from exc

    system_prompt = f"{custom_prompt}\n\n{DRAFT_SCHEMA_INSTRUCTION}"
    user_prompt = USER_PROMPT_TEMPLATE.format(
        custom_prompt=custom_prompt,
        bundle_json=json.dumps(_compact_bundle(bundle), ensure_ascii=False),
    )

    try:
        resp = client.chat.completions.create(
            model=resolved_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )
    except Exception as exc:
        logger.warning("LLM call failed for user=%s model=%s: %s", username, resolved_model, exc)
        raise LLMCallError(f"大模型调用失败：{exc}") from exc

    raw = (resp.choices[0].message.content or "").strip()
    logger.info("LLM raw response (model=%s, len=%d):\n%s",
                resolved_model, len(raw), raw[:2000])
    parsed = _safe_parse_json(raw)
    if parsed is None:
        logger.warning("LLM response unparseable as JSON. raw[:1000]=\n%s", raw[:1000])
        raise LLMCallError(f"大模型返回无法解析：{raw[:200]}")

    # 数值契约校验
    invented = _validate_number_contract(parsed, bundle)
    if invented:
        logger.warning(
            "LLM contract violated. invented=%s bundle_allowed_sample=%s draft_keys=%s "
            "raw_first_800=%s",
            invented[:10],
            sorted(_collect_bundle_numbers(bundle))[:20],
            list(parsed.keys()),
            raw[:800],
        )
        raise LLMContractError(
            f"LLM 编造了 bundle 不存在的数值: {invented[:5]}; raw[:500]={raw[:500]}"
        )

    # 兜底补字段（防止 LLM 漏字段让上层 render_markdown 崩）
    parsed.setdefault("draft_version", "report-draft-v1")
    parsed.setdefault("prompt_version", (prompt_template or {}).get("prompt_version", "template-v1"))
    parsed.setdefault("disclaimer", "由 LLM 改写，数值严格基于 AnalysisBundle。")
    parsed["signal_overview"] = parsed.get("signal_highlights") or []
    parsed["risk_alerts"] = parsed.get("risk_warnings") or []
    parsed["suggested_actions"] = parsed.get("action_watchlist") or []
    parsed["llm_status"] = "success"
    parsed["model_name"] = resolved_model

    return parsed


def _safe_parse_json(raw: str) -> Optional[dict]:
    try:
        result = json.loads(raw)
        return result if isinstance(result, dict) else None
    except json.JSONDecodeError:
        # 剥 markdown 代码块再试
        cleaned = raw.strip().strip("`").removeprefix("json").strip()
        try:
            result = json.loads(cleaned)
            return result if isinstance(result, dict) else None
        except json.JSONDecodeError:
            return None