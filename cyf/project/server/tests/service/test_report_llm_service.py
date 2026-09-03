"""report_llm_service 单元测试 — 覆盖 LLM 改写器的 schema / 数值契约 / 失败兜底。

LLM 改写器只依赖 get_client_for_user + openai SDK；测试用 MagicMock 替代 client。
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from service.quant.report_llm_service import (
    LLMCallError,
    LLMContractError,
    _collect_bundle_numbers,
    _extract_numbers_from_text,
    _strip_non_numeric_tokens,
    _validate_number_contract,
    rewrite_report_with_llm,
)


def _fake_client(content: str = "") -> MagicMock:
    """构造假的 OpenAI client，chat.completions.create 返回 content。"""
    client = MagicMock()
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = content
    response.usage = MagicMock(prompt_tokens=100, completion_tokens=200)
    client.chat.completions.create.return_value = response
    return client


def _sample_bundle() -> dict:
    """标准 AnalysisBundle，覆盖数值契约的关键字段。"""
    return {
        "bundle_version": "analysis-bundle-v1",
        "prompt_version": "prompt-v1",
        "strategy": {"id": 1, "name": "均线突破", "description": "demo"},
        "run": {"trade_date": "2026-09-02", "signals_total": 3, "symbols_total": 100},
        "symbols": ["000001.SZ", "600519.SH"],
        "signal_summary": {"signals_total": 3, "symbols_total": 100, "pass_rate": 0.03},
        "top_signals": [
            {"symbol": "000001.SZ", "name": "平安银行", "score": 2.5,
             "close_price": 12.34, "pct_change": 2.1, "turnover_rate": 1.5},
            {"symbol": "600519.SH", "name": "贵州茅台", "score": 1.8,
             "close_price": 1680.0, "pct_change": -0.5, "turnover_rate": 0.8},
        ],
        "risk_flags": [{"code": "NO_PASS_SIGNAL", "level": "warning", "message": "测试风险"}],
        "market_summary": {"sample_size": 2, "avg_pct_change": 0.8, "avg_turnover_rate": 1.15},
        "memory_snippets": [{"symbol": "000001.SZ"}],
        "operator_notes": [],
    }


def _well_formed_draft() -> dict:
    """完全合规的 ReportDraft，所有数字都来自 _sample_bundle()。"""
    return {
        "title": "均线突破 · 2026-09-02 测试报告",
        "summary": [
            "本次扫描 100 个标的，通过 3 个。",
            "数值均来源于 AnalysisBundle。",
        ],
        "market_view": ["本次信号样本平均涨跌幅 0.8%，平均换手 1.15%。"],
        "signal_highlights": [
            "平安银行 得分 2.5，收盘 12.34，涨跌幅 2.1%：规则通过",
            "贵州茅台 得分 1.8，收盘 1680.0，涨跌幅 -0.5%：规则通过",
        ],
        "risk_warnings": ["测试风险"],
        "action_watchlist": ["复核得分最高的 3 个标的"],
        "memory_references": ["000001.SZ"],
        "footer_notes": ["Bundle 版本 analysis-bundle-v1"],
    }


class TestNumberExtraction:
    """_extract_numbers_from_text 与 _collect_bundle_numbers 工具函数。"""

    def test_extracts_ints_and_floats_and_percentages(self):
        nums = _extract_numbers_from_text("平安银行收盘 12.34，涨跌幅 2.1%")
        assert "12.34" in nums
        assert "2.1%" in nums

    def test_extracts_negative_numbers(self):
        nums = _extract_numbers_from_text("贵州茅台涨跌幅 -0.5%")
        assert "-0.5%" in nums

    def test_empty_or_none_text_returns_empty(self):
        assert _extract_numbers_from_text("") == []
        assert _extract_numbers_from_text(None) == []

    def test_collect_bundle_numbers_includes_rounded_variants(self):
        nums = _collect_bundle_numbers(_sample_bundle())
        # close_price=12.34 应有 .34/.3/.0 等简化形式
        assert "12.34" in nums
        # pct_change=2.1 → "2.1" / "2%" 都会收录
        assert "2.1" in nums
        # avg_pct_change=0.8
        assert "0.8" in nums
        # signals_total=3
        assert "3" in nums
        # symbols_total=100
        assert "100" in nums


class TestNumberContract:
    """_validate_number_contract：编造的数值要被 reject。"""

    def test_well_formed_draft_passes(self):
        invented = _validate_number_contract(_well_formed_draft(), _sample_bundle())
        assert invented == []

    def test_invented_numeric_value_is_detected(self):
        bad = json.loads(json.dumps(_well_formed_draft()))  # deep copy
        bad["summary"][0] = "本次扫描 999 个标的，通过 3 个。"
        invented = _validate_number_contract(bad, _sample_bundle())
        # 999 不在 bundle 里（bundle 是 100），应被检测出来
        assert "999" in invented

    def test_version_year_is_always_allowed(self):
        """年份（2026/2025）应总是合法，与 bundle 内容无关。"""
        draft = {"summary": ["本期 2026 年 9 月数据"], "market_view": [], "signal_highlights": [],
                 "action_watchlist": [], "risk_warnings": [], "footer_notes": []}
        invented = _validate_number_contract(draft, _sample_bundle())
        assert invented == []

    def test_no_numbers_in_draft_passes(self):
        draft = {"summary": ["全部合规，没有数字。"], "market_view": [], "signal_highlights": [],
                 "action_watchlist": [], "risk_warnings": [], "footer_notes": []}
        invented = _validate_number_contract(draft, _sample_bundle())
        assert invented == []


class TestStripNonNumericTokens:
    """_strip_non_numeric_tokens：日期 / 时间 / 股票代码 不应当被合同误判为编造数字。"""

    def test_strips_stock_codes(self):
        cleaned = _strip_non_numeric_tokens("贵州茅台（600519.SH）和平安银行（000001.SZ）")
        assert "600519" not in cleaned
        assert "000001" not in cleaned
        # 真数值保留
        nums = _extract_numbers_from_text(cleaned)
        assert nums == []

    def test_strips_iso_dates(self):
        cleaned = _strip_non_numeric_tokens("交易日期：2026-05-15；报告生成时间：2026-05-17T17:22:18")
        assert "2026" not in cleaned
        assert "-05" not in cleaned
        assert "-15" not in cleaned
        assert "-17" not in cleaned
        assert cleaned.strip() == "交易日期： ；报告生成时间："

    def test_strips_slash_dates(self):
        cleaned = _strip_non_numeric_tokens("参考日期 2026/09/02 数据")
        assert "2026" not in cleaned
        assert "09" not in cleaned
        assert "02" not in cleaned

    def test_strips_times(self):
        cleaned = _strip_non_numeric_tokens("开盘 9:30，收盘 15:00")
        assert "9" not in cleaned
        assert "30" not in cleaned
        assert "15" not in cleaned
        assert "00" not in cleaned

    def test_keeps_real_numbers(self):
        cleaned = _strip_non_numeric_tokens("收盘价 1332.95，涨跌幅 -0.6869%")
        # 日期 / 时间 / 股票代码都没出现 → 数值不动
        assert "1332.95" in cleaned
        assert "-0.6869%" in cleaned

    def test_keeps_ma5_numeric(self):
        """MA5 里的 5 不应当被日期正则误剥（也不应当被认作编造）。"""
        cleaned = _strip_non_numeric_tokens("收盘跌破MA5")
        assert "5" in cleaned


class TestContractWithRealLLMOutput:
    """用真实 LLM 输出验证 contract：日期 / 股票代码 / 时间都不算编造，但 999/888 这类真编造会被抓。"""

    def test_realistic_llm_output_passes_contract(self):
        # 完全模拟你贴的 LLM 输出：日期、股票代码、时间、负数都包含
        draft = {
            "title": "A股收盘跌破MA5策略报告",
            "summary": [
                "本次运行状态为success，策略为收盘跌破MA5。",
                "覆盖2个标的，共产生2个信号，命中率为1.0。",
                "市场样本平均涨跌幅为-0.6149，平均换手率为0.4834。",
            ],
            "market_view": [
                "2026-05-15样本中，贵州茅台与平安银行均出现收盘跌破MA5信号。",
                "样本平均涨跌幅为-0.6149，整体表现偏弱。",
            ],
            "signal_highlights": [
                "贵州茅台（600519.SH）：卖出信号，收盘价1332.95，涨跌幅-0.6869，换手率0.4646。",
                "平安银行（000001.SZ）：卖出信号，收盘价10.99，涨跌幅-0.543，换手率0.5023。",
            ],
            "risk_warnings": [
                "当前未提供额外风险标记。",
                "本次样本量为2，结论代表性有限。",
            ],
            "action_watchlist": [
                "关注贵州茅台（600519.SH）与平安银行（000001.SZ）的后续表现。",
            ],
            "memory_references": [],
            "footer_notes": [
                "市场：A_SHARE；策略版本：strategy-v1。",
                "交易日期：2026-05-15；报告生成时间：2026-05-17T17:22:18。",
            ],
        }
        # 用一个含合法数值的 bundle 校验；信号数值（1332.95 / -0.6869 等）应来自 bundle
        bundle = {
            "run": {"trade_date": "2026-05-15", "signals_total": 2, "symbols_total": 2},
            "top_signals": [
                {"symbol": "600519.SH", "name": "贵州茅台", "score": 2.0,
                 "close_price": 1332.95, "pct_change": -0.6869, "turnover_rate": 0.4646},
                {"symbol": "000001.SZ", "name": "平安银行", "score": 1.5,
                 "close_price": 10.99, "pct_change": -0.543, "turnover_rate": 0.5023},
            ],
            "signal_summary": {"signals_total": 2, "symbols_total": 2, "pass_rate": 1.0},
            "market_summary": {"sample_size": 2, "avg_pct_change": -0.6149, "avg_turnover_rate": 0.4834},
        }
        invented = _validate_number_contract(draft, bundle)
        assert invented == [], f"不应有编造数字，但检测到: {invented}"

    def test_invented_999_still_caught(self):
        """即使用了 strip helper，纯编造的数字仍应当被抓出。"""
        draft = {"summary": ["AI 检测到 999 只异动股，888 个候选。"], "market_view": [],
                 "signal_highlights": [], "risk_warnings": [], "action_watchlist": [],
                 "footer_notes": []}
        invented = _validate_number_contract(draft, _sample_bundle())
        assert "999" in invented
        assert "888" in invented


class TestRewriteReportWithLLM:
    """rewrite_report_with_llm 主路径。"""

    def test_success_returns_compatible_draft(self):
        draft = _well_formed_draft()
        client = _fake_client(content=json.dumps(draft, ensure_ascii=False))

        with patch("service.quant.report_llm_service.get_client_for_user", return_value=(client, None)):
            result = rewrite_report_with_llm(
                bundle=_sample_bundle(),
                prompt_template={"prompt_version": "v1", "prompt_template": "你是量化研究助理"},
                model_name="gpt-5.6-luna",
                username="cyf",
            )

        # 字段补齐：draft_version / disclaimer / signal_overview 等别名
        assert result["draft_version"] == "report-draft-v1"
        assert "disclaimer" in result
        assert result["signal_overview"] == result["signal_highlights"]
        assert result["risk_alerts"] == result["risk_warnings"]
        assert result["suggested_actions"] == result["action_watchlist"]
        assert result["llm_status"] == "success"
        assert result["model_name"] == "gpt-5.6-luna"

    def test_invented_numbers_raise_contract_error(self):
        draft = _well_formed_draft()
        bad = json.loads(json.dumps(draft))
        bad["summary"][0] = "本次扫描 999 个标的，通过 3 个。"  # 999 不在 bundle
        client = _fake_client(content=json.dumps(bad, ensure_ascii=False))

        with patch("service.quant.report_llm_service.get_client_for_user", return_value=(client, None)):
            with pytest.raises(LLMContractError) as exc_info:
                rewrite_report_with_llm(
                    bundle=_sample_bundle(),
                    prompt_template=None,
                    username="cyf",
                )
        assert "999" in str(exc_info.value)

    def test_unparseable_json_raises_call_error(self):
        client = _fake_client(content="这是不的 json {{")  # 不是 JSON

        with patch("service.quant.report_llm_service.get_client_for_user", return_value=(client, None)):
            with pytest.raises(LLMCallError):
                rewrite_report_with_llm(
                    bundle=_sample_bundle(),
                    prompt_template=None,
                    username="cyf",
                )

    def test_get_client_failure_raises_call_error(self):
        with patch(
            "service.quant.report_llm_service.get_client_for_user",
            side_effect=ValueError("无 API key"),
        ):
            with pytest.raises(LLMCallError, match="无法获取 API client"):
                rewrite_report_with_llm(
                    bundle=_sample_bundle(),
                    prompt_template=None,
                    username="cyf",
                )

    def test_openai_sdk_exception_raises_call_error(self):
        client = MagicMock()
        client.chat.completions.create.side_effect = RuntimeError("API 502")

        with patch("service.quant.report_llm_service.get_client_for_user", return_value=(client, None)):
            with pytest.raises(LLMCallError, match="大模型调用失败"):
                rewrite_report_with_llm(
                    bundle=_sample_bundle(),
                    prompt_template=None,
                    username="cyf",
                )

    def test_empty_bundle_raises_call_error(self):
        client = _fake_client()

        with patch("service.quant.report_llm_service.get_client_for_user", return_value=(client, None)):
            with pytest.raises(LLMCallError, match="bundle 为空"):
                rewrite_report_with_llm(
                    bundle={},
                    prompt_template=None,
                    username="cyf",
                )

    def test_prompt_template_model_name_overrides_caller(self):
        """prompt_template.model_name 优先于 caller 的 model_name（caller 为空时）。"""
        draft = _well_formed_draft()
        client = _fake_client(content=json.dumps(draft, ensure_ascii=False))

        with patch("service.quant.report_llm_service.get_client_for_user", return_value=(client, None)):
            result = rewrite_report_with_llm(
                bundle=_sample_bundle(),
                prompt_template={"model_name": "claude-3-7-sonnet", "prompt_template": "..."},
                model_name="",  # 不覆盖
                username="cyf",
            )
        assert result["model_name"] == "claude-3-7-sonnet"

    def test_caller_model_name_overrides_prompt_template(self):
        """caller 传入的 model_name 优先级最高。"""
        draft = _well_formed_draft()
        client = _fake_client(content=json.dumps(draft, ensure_ascii=False))

        with patch("service.quant.report_llm_service.get_client_for_user", return_value=(client, None)):
            result = rewrite_report_with_llm(
                bundle=_sample_bundle(),
                prompt_template={"model_name": "claude-3-7-sonnet", "prompt_template": "..."},
                model_name="gpt-5.6-luna",  # 覆盖模板
                username="cyf",
            )
        assert result["model_name"] == "gpt-5.6-luna"