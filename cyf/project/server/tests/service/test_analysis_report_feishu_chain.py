"""execute_analysis_report → send_report_to_channel → 飞书 markdown 卡片 集成测试。

需求 1 链路通顺验证：定时调度 analysis_report 跑完后，应当用 msg_type='interactive' 卡片
把 report 的 final_markdown 推给飞书，让飞书渲染 markdown 而不是展示源码。

防止后续重构把 send_channel_content 退回 text 路径，或把 title 丢掉。
"""
from __future__ import annotations

import json
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from service.quant.schedule_execution_service import execute_analysis_report


def _fake_strategy_run(run_id: int, strategy_id: int, signals_total: int) -> dict:
    return {
        "id": run_id,
        "strategy_id": strategy_id,
        "run_key": f"strategy-{strategy_id}-fake-{run_id}",
        "trade_date": "2026-09-01",
        "status": "success",
        "symbols_total": 10,
        "signals_total": signals_total,
    }


def _fake_report(report_id: int, run_id: int, strategy_id: int, title: str) -> dict:
    return {
        "id": report_id,
        "run_id": run_id,
        "strategy_id": strategy_id,
        "report_key": f"report-{report_id}-fake",
        "trade_date": "2026-09-01",
        "report_type": "test_report",
        "title": title,
        "final_markdown": (
            f"# {title}\n\n"
            "- **信号 1**: 000001.SZ 收盘 12.34 (+2.1%)\n"
            "- **信号 2**: 600519.SH 收盘 1680 (-0.5%)\n\n"
            "## 风险\n- 数据完整性需关注"
        ),
        "analysis_bundle": {"strategy": {"id": strategy_id}, "top_signals": []},
        "report_draft": {"prompt_version": "template-v1"},
    }


def _fake_channel(channel_id: int = 1) -> dict:
    return {
        "channel_id": channel_id,
        "channel_type": "feishu_app",
        "config": {"receive_id": "oc_test_chat_xxx", "receive_id_type": "chat_id"},
        "channel_target": "feishu:chat_id:oc_t...",
        "mention_list": [],
    }


def _patched_quant_report_record(report: dict):
    """Patch service.quant.im_delivery_service.QuantReportRecord.get_by_id，让它返回 fake report。

    send_report_to_channel 内部会查 DB 取 title/final_markdown。集成测试不应该
    写真实 record，改为 patch Model 让它返回构造好的 to_dict()。
    """
    fake_record = MagicMock()
    fake_record.to_dict.return_value = report
    fake_model = MagicMock()
    fake_model.get_by_id.return_value = fake_record
    return patch("service.quant.im_delivery_service.QuantReportRecord", fake_model)


@pytest.fixture
def fake_run():
    """一个看上去像 QuantScheduleRun 的对象，schedule_execution_service 只读这些字段。"""
    run = MagicMock()
    run.id = 100
    run.schedule_id = 1
    run.schedule_name = "盘后报告"
    run.task_type = "analysis_report"
    run.trade_date = date(2026, 9, 1)
    run.payload_json = json.dumps(
        {"strategy_ids": [10], "channel_ids": [1], "save_all_signals": True},
        ensure_ascii=False,
    )
    return run


class TestExecuteAnalysisReportFeishuChain:
    """需求 1 链路通：execute_analysis_report 走完应当用 interactive 卡片推 final_markdown。"""

    def test_runs_strategy_creates_report_and_pushes_via_card(self, fake_run):
        strategy_id = 10
        strategy_run = _fake_strategy_run(run_id=200, strategy_id=strategy_id, signals_total=3)
        report = _fake_report(report_id=500, run_id=200, strategy_id=strategy_id, title="均线突破 · 2026-09-01 测试报告")
        channel = _fake_channel(channel_id=1)

        with patch(
            "service.quant.schedule_execution_service.run_strategy",
            return_value=strategy_run,
        ), patch(
            "service.quant.schedule_execution_service.create_report_for_run",
            return_value=report,
        ), patch(
            "service.quant.im_delivery_service.load_channel",
            return_value=channel,
        ), _patched_quant_report_record(report), patch(
            "service.quant.im_delivery_service.send_feishu_card",
        ) as spy_card, patch(
            "service.quant.schedule_execution_service.deliver_to_bound_users",
            return_value=[],
        ):
            spy_card.return_value = {
                "message_type": "interactive",
                "request_payload": {"msg_type": "interactive"},
                "response_payload": {"code": 0, "msg": "success", "message_id": "om_xxx"},
            }

            result = execute_analysis_report(fake_run)

        # 验证整条链路的关键产物
        assert "reports" in result and len(result["reports"]) == 1
        assert "deliveries" in result and len(result["deliveries"]) == 1
        # send_feishu_card 被调用了一次（走的是 markdown 卡片路径）
        spy_card.assert_called_once()
        # 调用参数：send_feishu_card(channel, title=..., markdown=...) — channel 是 positional，
        # title/markdown 是 keyword
        call_args = spy_card.call_args
        channel_arg = call_args.args[0]
        title_arg = call_args.kwargs["title"]
        markdown_arg = call_args.kwargs["markdown"]
        assert channel_arg["channel_id"] == 1
        assert title_arg == "均线突破 · 2026-09-01 测试报告"
        # markdown 是 report 的 final_markdown，飞书会用 markdown 渲染
        assert "# 均线突破" in markdown_arg
        assert "- **信号 1**" in markdown_arg

    def test_pushes_to_multiple_channels_when_payload_lists_many(self, fake_run):
        """payload.channel_ids 多选时应当对每个 channel 都推一次。"""
        run = fake_run
        run.payload_json = json.dumps(
            {"strategy_ids": [10], "channel_ids": [1, 2, 3], "save_all_signals": True},
            ensure_ascii=False,
        )
        strategy_run = _fake_strategy_run(run_id=201, strategy_id=10, signals_total=0)
        report = _fake_report(report_id=501, run_id=201, strategy_id=10, title="多通道测试")

        channels = [_fake_channel(channel_id=i) for i in (1, 2, 3)]

        with patch(
            "service.quant.schedule_execution_service.run_strategy",
            return_value=strategy_run,
        ), patch(
            "service.quant.schedule_execution_service.create_report_for_run",
            return_value=report,
        ), patch(
            "service.quant.im_delivery_service.load_channel",
            side_effect=lambda channel_id=None: channels[channel_id - 1],
        ), _patched_quant_report_record(report), patch(
            "service.quant.im_delivery_service.send_feishu_card",
            return_value={
                "message_type": "interactive",
                "request_payload": {"msg_type": "interactive"},
                "response_payload": {"code": 0, "msg": "ok"},
            },
        ), patch(
            "service.quant.schedule_execution_service.deliver_to_bound_users",
            return_value=[],
        ):
            result = execute_analysis_report(run)

        assert len(result["deliveries"]) == 3
        summary = result["summary"]
        assert summary["strategy_count"] == 1
        assert summary["delivery_count"] == 3
        assert summary["mode"] == "test_report"

    def test_failed_card_push_does_not_break_other_channels(self, fake_run):
        """鲁棒性：单 channel 推送失败不应让整个 schedule run 失败。"""
        run = fake_run
        run.payload_json = json.dumps(
            {"strategy_ids": [10], "channel_ids": [1, 2], "save_all_signals": True},
            ensure_ascii=False,
        )
        strategy_run = _fake_strategy_run(run_id=202, strategy_id=10, signals_total=1)
        report = _fake_report(report_id=502, run_id=202, strategy_id=10, title="鲁棒性测试")

        success_card = {
            "message_type": "interactive",
            "request_payload": {"msg_type": "interactive"},
            "response_payload": {"code": 0, "msg": "ok"},
        }

        def fake_send(channel, title, markdown):
            if channel["channel_id"] == 1:
                raise ValueError("飞书通道 #1 receive_id 无效")
            return success_card

        channels = [_fake_channel(channel_id=i) for i in (1, 2)]

        with patch(
            "service.quant.schedule_execution_service.run_strategy",
            return_value=strategy_run,
        ), patch(
            "service.quant.schedule_execution_service.create_report_for_run",
            return_value=report,
        ), patch(
            "service.quant.im_delivery_service.load_channel",
            side_effect=lambda channel_id=None: channels[channel_id - 1],
        ), _patched_quant_report_record(report), patch(
            "service.quant.im_delivery_service.send_feishu_card",
            side_effect=fake_send,
        ), patch(
            "service.quant.schedule_execution_service.deliver_to_bound_users",
            return_value=[],
        ):
            result = execute_analysis_report(run)

        # 1 个成功 + 1 个失败，summary 计数对得上
        assert len(result["deliveries"]) == 2
        statuses = sorted(d["status"] for d in result["deliveries"])
        assert statuses == ["failed", "success"]