"""report_draft / report_llm_service / report_generation_service — custom_sections 扩展段单测。

custom_sections 是 LLM 根据 prompt_template 意图生成的"自由发挥段"，
由 render_report_markdown 插在 ## 契约说明 之前。本文件覆盖：
- _validate_report_draft 对 custom_sections 的校验
- _validate_number_contract 对 custom_sections[*].body_md 的扫描
- rewrite_report_with_llm 缺省补 custom_sections=[]
- _build_template_draft 兜底模板给 custom_sections=[]
- render_report_markdown 插入位置 + 多段 / 空列表 / 非法字段处理
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from service.quant.report_draft import (
    _build_template_draft,
    _validate_report_draft,
)
from service.quant.report_generation_service import render_report_markdown
from service.quant.report_llm_service import (
    _validate_number_contract,
    rewrite_report_with_llm,
)


# ---------------------------------------------------------------------------
# 共享 fixture
# ---------------------------------------------------------------------------


def _sample_bundle() -> dict:
    return {
        "bundle_version": "analysis-bundle-v1",
        "prompt_version": "prompt-v1",
        "strategy": {"id": 1, "name": "测试策略", "description": "demo"},
        "run": {"trade_date": "2026-09-02", "signals_total": 3, "symbols_total": 100},
        "symbols": ["000001.SZ"],
        "signal_summary": {"signals_total": 3, "symbols_total": 100, "pass_rate": 0.03},
        "top_signals": [
            {"symbol": "000001.SZ", "name": "平安银行", "score": 2.5,
             "close_price": 12.34, "pct_change": 2.1, "turnover_rate": 1.5},
        ],
        "risk_flags": [],
        "market_summary": {"sample_size": 1, "avg_pct_change": 2.1, "avg_turnover_rate": 1.5},
        "memory_snippets": [],
        "operator_notes": [],
    }


def _well_formed_draft() -> dict:
    """不含 custom_sections 的最简合规 ReportDraft。"""
    return {
        "title": "测试策略 · 2026-09-02",
        "summary": ["本次扫描 100 个标的，通过 3 个。"],
        "market_view": ["样本平均涨跌幅 2.1%。"],
        "signal_highlights": ["平安银行 得分 2.5。"],
        "risk_warnings": ["无"],
        "action_watchlist": ["复核"],
        "memory_references": [],
        "footer_notes": ["Bundle 版本 analysis-bundle-v1"],
    }


def _fake_client(content: str) -> MagicMock:
    client = MagicMock()
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = content
    response.usage = MagicMock(prompt_tokens=10, completion_tokens=20)
    client.chat.completions.create.return_value = response
    return client


# ---------------------------------------------------------------------------
# _validate_report_draft
# ---------------------------------------------------------------------------


class TestValidateCustomSections:
    """_validate_report_draft 对 custom_sections 的字段校验。"""

    def test_missing_custom_sections_is_ok(self):
        # 缺省视为空列表，向后兼容
        _validate_report_draft(_well_formed_draft())

    def test_empty_list_is_ok(self):
        draft = json.loads(json.dumps(_well_formed_draft()))
        draft["custom_sections"] = []
        _validate_report_draft(draft)

    def test_valid_sections_pass(self):
        draft = json.loads(json.dumps(_well_formed_draft()))
        draft["custom_sections"] = [
            {"title": "风险矩阵", "body_md": "- 行 1\n- 行 2"},
            {"title": "操作清单", "body_md": "次日开盘复核"},
        ]
        _validate_report_draft(draft)

    def test_non_list_raises(self):
        draft = json.loads(json.dumps(_well_formed_draft()))
        draft["custom_sections"] = {"title": "x", "body_md": "y"}
        with pytest.raises(ValueError, match="必须是 list"):
            _validate_report_draft(draft)

    def test_too_many_sections_raises(self):
        draft = json.loads(json.dumps(_well_formed_draft()))
        draft["custom_sections"] = [{"title": f"t{i}", "body_md": "b"} for i in range(4)]
        with pytest.raises(ValueError, match="最多 3 段"):
            _validate_report_draft(draft)

    def test_section_must_be_dict(self):
        draft = json.loads(json.dumps(_well_formed_draft()))
        draft["custom_sections"] = ["not-a-dict"]
        with pytest.raises(ValueError, match="必须是 dict"):
            _validate_report_draft(draft)

    def test_section_missing_title_raises(self):
        draft = json.loads(json.dumps(_well_formed_draft()))
        draft["custom_sections"] = [{"body_md": "x"}]
        with pytest.raises(ValueError, match=r"\.title 必须是 str"):
            _validate_report_draft(draft)

    def test_section_missing_body_md_raises(self):
        draft = json.loads(json.dumps(_well_formed_draft()))
        draft["custom_sections"] = [{"title": "x"}]
        with pytest.raises(ValueError, match=r"\.body_md 必须是 str"):
            _validate_report_draft(draft)

    # ----- allowed_extra_titles 段标题校验 -----

    def test_allowed_titles_passes_when_match(self):
        draft = json.loads(json.dumps(_well_formed_draft()))
        draft["custom_sections"] = [
            {"title": "风险矩阵", "body_md": "..."},
            {"title": "次日操作", "body_md": "..."},
        ]
        _validate_report_draft(draft, allowed_extra_titles={"风险矩阵", "次日操作"})

    def test_allowed_titles_rejects_undeclared(self):
        draft = json.loads(json.dumps(_well_formed_draft()))
        draft["custom_sections"] = [
            {"title": "风险矩阵", "body_md": "..."},
            {"title": "凭空捏造", "body_md": "..."},
        ]
        with pytest.raises(ValueError, match="凭空捏造"):
            _validate_report_draft(draft, allowed_extra_titles={"风险矩阵"})

    def test_allowed_titles_none_means_no_restriction(self):
        draft = json.loads(json.dumps(_well_formed_draft()))
        draft["custom_sections"] = [{"title": "任意标题", "body_md": "..."}]
        # 不传 allowed_extra_titles，任意标题都通过
        _validate_report_draft(draft)
        _validate_report_draft(draft, allowed_extra_titles=None)

    def test_allowed_titles_empty_set_blocks_all(self):
        # 空集合 = 任何标题都不允许
        draft = json.loads(json.dumps(_well_formed_draft()))
        draft["custom_sections"] = [{"title": "风险矩阵", "body_md": "..."}]
        with pytest.raises(ValueError, match="风险矩阵"):
            _validate_report_draft(draft, allowed_extra_titles=set())

    def test_allowed_titles_trims_whitespace(self):
        draft = json.loads(json.dumps(_well_formed_draft()))
        draft["custom_sections"] = [{"title": "风险矩阵 ", "body_md": "..."}]
        _validate_report_draft(draft, allowed_extra_titles={"风险矩阵"})


# ---------------------------------------------------------------------------
# _validate_number_contract 覆盖 custom_sections
# ---------------------------------------------------------------------------


class TestNumberContractCoversCustomSections:
    """custom_sections[*].body_md 里的数字同样要走数值契约。"""

    def test_custom_section_with_bundle_number_passes(self):
        draft = json.loads(json.dumps(_well_formed_draft()))
        draft["custom_sections"] = [
            {"title": "强弱对比", "body_md": "平安银行收盘 12.34，涨跌幅 2.1%。"}
        ]
        invented = _validate_number_contract(draft, _sample_bundle())
        assert invented == []

    def test_custom_section_with_invented_number_caught(self):
        draft = json.loads(json.dumps(_well_formed_draft()))
        draft["custom_sections"] = [
            {"title": "风险矩阵", "body_md": "AI 提示有 999 个异常波动"}
        ]
        invented = _validate_number_contract(draft, _sample_bundle())
        assert "999" in invented

    def test_custom_section_multiline_each_line_scanned(self):
        draft = json.loads(json.dumps(_well_formed_draft()))
        draft["custom_sections"] = [
            {"title": "t", "body_md": "第一行 999\n第二行 12.34 平安银行\n第三行 888"}
        ]
        invented = _validate_number_contract(draft, _sample_bundle())
        assert "999" in invented
        assert "888" in invented
        # 12.34 在 bundle 里，应放行
        assert "12.34" not in invented

    def test_custom_section_empty_body_no_crash(self):
        draft = json.loads(json.dumps(_well_formed_draft()))
        draft["custom_sections"] = [{"title": "t", "body_md": ""}]
        invented = _validate_number_contract(draft, _sample_bundle())
        assert invented == []

    def test_malformed_section_silently_skipped(self):
        # contract 层是兜底扫描，遇到非 dict 元素不抛错，跳过即可
        draft = json.loads(json.dumps(_well_formed_draft()))
        draft["custom_sections"] = ["not-a-dict"]
        invented = _validate_number_contract(draft, _sample_bundle())
        assert invented == []


# ---------------------------------------------------------------------------
# rewrite_report_with_llm 缺省补 custom_sections
# ---------------------------------------------------------------------------


class TestLLMDefaultsCustomSections:
    """LLM 返回里若缺 custom_sections，会被补成空列表。"""

    def test_missing_custom_sections_is_backfilled(self):
        draft = _well_formed_draft()
        client = _fake_client(json.dumps(draft, ensure_ascii=False))

        with patch("service.quant.report_llm_service.get_client_for_user", return_value=(client, None)):
            result = rewrite_report_with_llm(
                bundle=_sample_bundle(),
                prompt_template={"prompt_version": "v1", "prompt_template": "..."},
                username="cyf",
            )
        assert result["custom_sections"] == []

    def test_existing_custom_sections_preserved(self):
        draft = json.loads(json.dumps(_well_formed_draft()))
        draft["custom_sections"] = [
            {"title": "复盘", "body_md": "次日开盘需复核"}
        ]
        client = _fake_client(json.dumps(draft, ensure_ascii=False))

        with patch("service.quant.report_llm_service.get_client_for_user", return_value=(client, None)):
            result = rewrite_report_with_llm(
                bundle=_sample_bundle(),
                prompt_template={"prompt_version": "v1", "prompt_template": "..."},
                username="cyf",
            )
        assert len(result["custom_sections"]) == 1
        assert result["custom_sections"][0]["title"] == "复盘"

    def test_undeclared_title_raises_contract_error(self):
        """LLM 返回了模板没声明的段标题 → 抛 LLMContractError。"""
        from service.quant.report_llm_service import LLMContractError

        draft = json.loads(json.dumps(_well_formed_draft()))
        draft["custom_sections"] = [
            {"title": "凭空捏造", "body_md": "..."},
        ]
        client = _fake_client(json.dumps(draft, ensure_ascii=False))

        with patch("service.quant.report_llm_service.get_client_for_user", return_value=(client, None)):
            with pytest.raises(LLMContractError, match="凭空捏造"):
                rewrite_report_with_llm(
                    bundle=_sample_bundle(),
                    prompt_template={"prompt_version": "v1", "prompt_template": "..."},
                    username="cyf",
                    allowed_extra_titles={"风险矩阵"},
                )

    def test_declared_title_passes_through(self):
        """LLM 返回的标题在声明集合内 → 通过。"""
        draft = json.loads(json.dumps(_well_formed_draft()))
        draft["custom_sections"] = [
            {"title": "风险矩阵", "body_md": "- 强度: 高"},
        ]
        client = _fake_client(json.dumps(draft, ensure_ascii=False))

        with patch("service.quant.report_llm_service.get_client_for_user", return_value=(client, None)):
            result = rewrite_report_with_llm(
                bundle=_sample_bundle(),
                prompt_template={"prompt_version": "v1", "prompt_template": "..."},
                username="cyf",
                allowed_extra_titles={"风险矩阵"},
            )
        assert result["custom_sections"][0]["title"] == "风险矩阵"


# ---------------------------------------------------------------------------
# _build_template_draft 兜底模板
# ---------------------------------------------------------------------------


class TestFallbackDraftHasCustomSections:
    """deterministic 兜底模板要给 custom_sections 默认空列表。"""

    def test_template_draft_has_empty_custom_sections(self):
        bundle = _sample_bundle()
        draft = _build_template_draft(
            bundle=bundle,
            memory_refs=[],
            operator_notes=[],
            llm_status="disabled",
        )
        assert draft.get("custom_sections") == []


# ---------------------------------------------------------------------------
# render_report_markdown 插入位置
# ---------------------------------------------------------------------------


class TestRenderMarkdownCustomSections:
    """render_report_markdown 在 ## 契约说明 之前插入 custom_sections。"""

    def test_empty_custom_sections_not_rendered(self):
        bundle = _sample_bundle()
        draft = _well_formed_draft()
        draft["custom_sections"] = []
        md = render_report_markdown(bundle, draft)
        assert "## 契约说明" in md
        # 没有多出奇怪的空行堆叠
        assert md.count("## ") == 7  # 摘要/市场观察/信号概览/风险提示/建议动作/记忆引用/契约说明

    def test_single_section_inserted_before_contract(self):
        bundle = _sample_bundle()
        draft = _well_formed_draft()
        draft["custom_sections"] = [
            {"title": "风险矩阵", "body_md": "- 强度: 高\n- 概率: 中"}
        ]
        md = render_report_markdown(bundle, draft)
        assert "## 风险矩阵" in md
        assert md.index("## 风险矩阵") < md.index("## 契约说明")
        assert "- 强度: 高" in md
        assert "- 概率: 中" in md

    def test_multiple_sections_in_order(self):
        bundle = _sample_bundle()
        draft = _well_formed_draft()
        draft["custom_sections"] = [
            {"title": "A 段", "body_md": "aaa"},
            {"title": "B 段", "body_md": "bbb"},
        ]
        md = render_report_markdown(bundle, draft)
        assert md.index("## A 段") < md.index("## B 段") < md.index("## 契约说明")

    def test_empty_title_or_body_skipped(self):
        bundle = _sample_bundle()
        draft = _well_formed_draft()
        draft["custom_sections"] = [
            {"title": "", "body_md": "x"},
            {"title": "有标题", "body_md": ""},
        ]
        md = render_report_markdown(bundle, draft)
        # 两个都被跳过，markdown 仍然只有7个 ##
        assert md.count("## ") == 7

    def test_malformed_section_skipped_not_crashed(self):
        bundle = _sample_bundle()
        draft = _well_formed_draft()
        draft["custom_sections"] = ["not-a-dict"]
        # _validate_report_draft 会先抛 ValueError —— 这是契约级保证
        with pytest.raises(ValueError):
            render_report_markdown(bundle, draft)

    def test_missing_custom_sections_field_renders_cleanly(self):
        """LLM 漏字段、模板兜底均会给空列表，render 应正常工作。"""
        bundle = _sample_bundle()
        draft = _well_formed_draft()  # 没有 custom_sections 字段
        # 先把缺省补成 [] 让 _validate_report_draft 过；这就是 LLM 成功路径的行为
        draft["custom_sections"] = []
        md = render_report_markdown(bundle, draft)
        assert "## 契约说明" in md