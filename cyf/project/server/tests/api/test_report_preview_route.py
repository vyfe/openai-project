"""/report/preview 路由集成测试 — 验证 IDE 调试接口的入参透传与返回结构。

不写真实 run_id：mock preview_report_for_run，避免依赖行情数据。
"""
from __future__ import annotations

from unittest.mock import patch

import pytest


@pytest.fixture
def fake_preview_result():
    """构造 mock preview_report_for_run 返回值。"""
    return {
        "bundle": {
            "bundle_version": "analysis-bundle-v1",
            "prompt_version": "v1",
            "strategy": {"id": 1, "name": "均线突破"},
            "run": {"trade_date": "2026-09-02", "signals_total": 3, "symbols_total": 100},
            "top_signals": [
                {"symbol": "000001.SZ", "name": "平安银行", "score": 2.5,
                 "close_price": 12.34, "pct_change": 2.1, "turnover_rate": 1.5},
            ],
            "signal_summary": {"signals_total": 3, "symbols_total": 100, "pass_rate": 0.03},
            "risk_flags": [],
            "market_summary": {"sample_size": 1, "avg_pct_change": 2.1, "avg_turnover_rate": 1.5},
        },
        "draft": {
            "draft_version": "report-draft-v1",
            "title": "均线突破 · 2026-09-02 测试报告",
            "summary": ["本次扫描 100 个标的，通过 3 个。"],
            "market_view": ["本次信号样本平均涨跌幅 2.1%，平均换手 1.5%。"],
            "signal_highlights": ["平安银行 得分 2.5，收盘 12.34，涨跌幅 2.1%：规则通过"],
            "risk_warnings": ["该报告仅用于研究和测试，不构成自动交易指令。"],
            "action_watchlist": ["复核得分最高的前 3 个标的"],
            "memory_references": [],
            "footer_notes": ["Bundle 版本 analysis-bundle-v1"],
            "llm_status": "success",
            "model_name": "gpt-5.6-luna",
        },
        "markdown": "# 均线突破 · 2026-09-02 测试报告\n\n## 摘要\n\n- 本次扫描 100 个标的，通过 3 个。",
        "meta": {
            "prompt_template_id": 1,
            "prompt_version": "v1",
            "model_name": "gpt-5.6-luna",
            "llm_status": "success",
            "report_type": "test_report",
            "run_id": 100,
            "strategy_id": 1,
        },
    }


class TestReportPreviewRoute:
    """需求 2 调试入口。"""

    def test_preview_with_template_and_llm_enabled(self, auth_client, fake_preview_result):
        """传 prompt_template_id + llm_enabled + model_name：service 收到所有参数 + 路由返回 4 字段结构。"""
        with patch(
            "routes.quant.strategy_routes.preview_report_for_run",
            return_value=fake_preview_result,
        ) as spy:
            resp = auth_client.post(
                "/never_guess_my_usage/quant/report/preview",
                json={
                    "run_id": 100,
                    "llm_enabled": True,
                    "prompt_template_id": 1,
                    "model_name": "gpt-5.6-luna",
                },
            )

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        # service 被调用 + 参数完整透传
        spy.assert_called_once()
        call_kwargs = spy.call_args.kwargs
        assert call_kwargs["run_id"] == 100
        assert call_kwargs["llm_enabled"] is True
        assert call_kwargs["prompt_template_id"] == 1
        assert call_kwargs["model_name"] == "gpt-5.6-luna"

        # 路由返回 4 字段：bundle / draft / markdown / meta
        result = data["data"]
        assert set(result.keys()) == {"bundle", "draft", "markdown", "meta"}
        # meta 含 llm_status / model_name 方便前端调试
        assert result["meta"]["llm_status"] == "success"
        assert result["meta"]["model_name"] == "gpt-5.6-luna"

    def test_preview_defaults_to_template_mode(self, auth_client, fake_preview_result):
        """不传 llm_enabled：默认走确定性模板（service 收到 llm_enabled=False）。"""
        fake_preview_result["draft"]["llm_status"] = "disabled"
        fake_preview_result["meta"]["llm_status"] = "disabled"

        with patch(
            "routes.quant.strategy_routes.preview_report_for_run",
            return_value=fake_preview_result,
        ) as spy:
            resp = auth_client.post(
                "/never_guess_my_usage/quant/report/preview",
                json={"run_id": 100},
            )

        assert resp.status_code == 200
        call_kwargs = spy.call_args.kwargs
        assert call_kwargs["llm_enabled"] is False
        assert call_kwargs["prompt_template_id"] is None
        assert call_kwargs["model_name"] == ""

    def test_preview_fallback_status_visible(self, auth_client, fake_preview_result):
        """LLM 失败时 llm_status=fallback_*：前端应能在 meta 看到。"""
        fake_preview_result["draft"]["llm_status"] = "fallback_contract"
        fake_preview_result["meta"]["llm_status"] = "fallback_contract"

        with patch(
            "routes.quant.strategy_routes.preview_report_for_run",
            return_value=fake_preview_result,
        ):
            resp = auth_client.post(
                "/never_guess_my_usage/quant/report/preview",
                json={"run_id": 100, "llm_enabled": True},
            )

        assert resp.status_code == 200
        assert resp.get_json()["data"]["meta"]["llm_status"] == "fallback_contract"

    def test_preview_missing_run_id_returns_error(self, auth_client):
        """不传 run_id：返回 200 + success=false 业务错误（项目约定）。"""
        resp = auth_client.post(
            "/never_guess_my_usage/quant/report/preview",
            json={"llm_enabled": True},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is False

    def test_preview_invalid_prompt_template_id_returns_error(self, auth_client):
        """prompt_template_id 不是整数：返回业务错误，不抛 500。"""
        resp = auth_client.post(
            "/never_guess_my_usage/quant/report/preview",
            json={"run_id": 100, "prompt_template_id": "not_an_int"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is False

    def test_no_auth_returns_401(self, app):
        """未认证：返回 401。"""
        with app.test_client() as client:
            resp = client.post(
                "/never_guess_my_usage/quant/report/preview",
                json={"run_id": 100},
            )
            assert resp.status_code == 401