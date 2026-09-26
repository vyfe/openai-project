"""单人级通道推送 demo 单测。"""

from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import patch

import pytest

from quant.entities import QuantImChannel, QuantReportRecord
from service.quant.binding_service import bind_user
from service.quant.position_service import create_position_entry
from service.quant.schedule_user_push_service import (
    filter_report_by_symbols,
    push_report_filtered_per_channel,
)


def _create_channel(name, receive_id, receive_id_type="open_id", inbound_chat_id="oc_test"):
    now = datetime.now()
    return QuantImChannel.create(
        name=name,
        channel_type="feishu_app",
        status="active",
        config_json=json.dumps({
            "inbound_chat_id": inbound_chat_id,
            "receive_id": receive_id,
            "receive_id_type": receive_id_type,
        }, ensure_ascii=False),
        mention_list_json="[]",
        description="test",
        created_at=now,
        updated_at=now,
    )


def _seed_strategy():
    """测试用策略（QuantReportRecord.strategy_id 非空约束）。"""
    from quant.entities import QuantStrategy
    return QuantStrategy.create(
        name="test_strategy_push",
        description="test",
        status="active",
        rule_definition_json="{}",
        parameters_json="{}",
        created_by="test",
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )


def _create_report(content: str, report_key: str = "test_report") -> int:
    strategy = _seed_strategy()
    record = QuantReportRecord.create(
        report_key=report_key,
        strategy_id=strategy.id,
        run_id=None,
        trade_date=datetime(2026, 9, 26).date(),
        report_type="test_report",
        title="测试报告",
        prompt_version="v1",
        summary="[1] 摘要要点 A",
        market_view="市场整体震荡。",
        signal_highlights=[
            "- 600519.SH 出现买入信号",
            "- 002837.SZ 出现卖出信号",
            "- 000001.SZ 出现关注信号",
        ],
        risk_warnings="本报告仅供参考。",
        action_watchlist=[
            "- 600519.SH 关注支撑位 1650",
            "- 002837.SZ 关注压力位 13",
            "- 000001.SZ 关注底部形态",
        ],
        memory_references=["600519.SH", "002837.SZ", "000001.SZ"],
        final_markdown=content,
        created_by="test",
        llm_used=False,
        status="generated",
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    return record.id


_SAMPLE_REPORT = """# 测试报告

## 摘要
- [1] 摘要要点 A
- [2] 摘要要点 B

## 市场观察
- 市场整体震荡。

## 信号概览
- 600519.SH 出现买入信号
- 002837.SZ 出现卖出信号
- 000001.SZ 出现关注信号

## 风险提示
- 本报告仅供参考。

## 建议动作
- 600519.SH 关注支撑位 1650
- 002837.SZ 关注压力位 13
- 000001.SZ 关注底部形态

## 记忆引用
- 600519.SH
- 002837.SZ
- 000001.SZ

## 契约说明
- Bundle 版本: `v1`
"""


class TestFilterReportBySymbols:
    """filter_report_by_symbols 单元测试。"""

    def test_no_holdings_keeps_global_sections_only(self):
        out = filter_report_by_symbols(_SAMPLE_REPORT, set())
        # 保留：标题、摘要、市场观察、风险提示、契约说明
        assert "# 测试报告" in out
        assert "## 摘要" in out
        assert "## 市场观察" in out
        assert "## 风险提示" in out
        assert "## 契约说明" in out
        # 过滤：信号概览/建议动作/记忆引用
        assert "## 信号概览" not in out
        assert "## 建议动作" not in out
        assert "## 记忆引用" not in out

    def test_with_holdings_keeps_relevant_lines(self):
        held = {"600519.SH", "002837.SZ"}
        out = filter_report_by_symbols(_SAMPLE_REPORT, held)
        # 保留
        assert "## 信号概览" in out
        assert "600519.SH 出现买入信号" in out
        assert "002837.SZ 出现卖出信号" in out
        # 过滤
        assert "000001.SZ 出现关注信号" not in out
        assert "## 建议动作" in out
        assert "000001.SZ 关注底部形态" not in out
        # 记忆引用
        assert "## 记忆引用" in out
        assert "- 600519.SH" in out
        assert "- 002837.SZ" in out
        assert "- 000001.SZ" not in out

    def test_empty_markdown_passes_through(self):
        assert filter_report_by_symbols("", {"600519.SH"}) == ""

    def test_section_keeps_custom_sections(self):
        custom = _SAMPLE_REPORT + "\n## 我的自由发挥段\n- 这是 LLM 生成的内容\n"
        out = filter_report_by_symbols(custom, set())
        assert "## 我的自由发挥段" in out


class TestPushReportFilteredPerChannel:
    """push_report_filtered_per_channel 集成测试。"""

    def test_p2p_channel_with_bound_user_gets_filtered_report(
        self, seed_admin_user, seed_test_instruments
    ):
        bind_user("ou_p2p_user_a", "test_admin", "test123")
        # 给用户写一条持仓
        create_position_entry(
            symbol="600519.SH",
            side="buy",
            quantity=100,
            price=1688.0,
            occurred_at=datetime.now(),
            source="manual",
            created_by="test_admin",
        )
        channel = _create_channel("p2p:oc_user_a", receive_id="ou_p2p_user_a")
        report_id = _create_report(_SAMPLE_REPORT)

        with patch(
            "service.quant.schedule_user_push_service.send_feishu_text",
            return_value={"message_type": "text", "request_payload": {}, "response_payload": {"code": 0}},
        ) as mock_send:
            results = push_report_filtered_per_channel([channel.id], report_id)

        assert len(results) == 1
        result = results[0]
        assert result["filter_applied"] is True
        assert result["username"] == "test_admin"
        assert "600519.SH" in result["held_symbols"]
        # 推送内容应包含持仓 + 报告（过滤后）
        _, kwargs = mock_send.call_args
        sent_content = kwargs["content"]
        assert "test_admin 当前持仓" in sent_content
        assert "## 信号概览" in sent_content
        assert "600519.SH 出现买入信号" in sent_content
        # 用户没持仓 002837.SZ 也不在持仓集中，所以 002837 应被过滤
        assert "002837.SZ 出现卖出信号" not in sent_content

    def test_group_channel_no_user_filter_passes_full_report(self, seed_admin_user):
        # 群聊 channel：receive_id_type=chat_id → 反查失败 → 透传
        channel = _create_channel(
            "group:oc_full",
            receive_id="oc_group_full",
            receive_id_type="chat_id",
        )
        report_id = _create_report(_SAMPLE_REPORT)

        with patch(
            "service.quant.schedule_user_push_service.send_feishu_text",
            return_value={"message_type": "text", "request_payload": {}, "response_payload": {"code": 0}},
        ) as mock_send:
            results = push_report_filtered_per_channel([channel.id], report_id)

        assert len(results) == 1
        result = results[0]
        assert result["filter_applied"] is False
        assert result["username"] is None
        # 内容应等于原报告
        _, kwargs = mock_send.call_args
        sent_content = kwargs["content"]
        assert sent_content == _SAMPLE_REPORT

    def test_user_with_no_positions_gets_market_only(
        self, seed_admin_user, seed_test_instruments
    ):
        bind_user("ou_p2p_user_empty", "test_admin", "test123")
        # 不写持仓
        channel = _create_channel("p2p:oc_empty", receive_id="ou_p2p_user_empty")
        report_id = _create_report(_SAMPLE_REPORT)

        with patch(
            "service.quant.schedule_user_push_service.send_feishu_text",
            return_value={"message_type": "text", "request_payload": {}, "response_payload": {"code": 0}},
        ) as mock_send:
            results = push_report_filtered_per_channel([channel.id], report_id)

        assert len(results) == 1
        _, kwargs = mock_send.call_args
        sent_content = kwargs["content"]
        # "无持仓" 前缀
        assert "当前无持仓" in sent_content
        # 信号/动作/记忆引用段应被过滤掉
        assert "## 信号概览" not in sent_content
        assert "## 建议动作" not in sent_content
        assert "## 记忆引用" not in sent_content
        # 全局段保留
        assert "## 市场观察" in sent_content

    def test_multiple_channels_each_filter_independently(
        self, seed_admin_user, seed_test_instruments
    ):
        # 3 个用户 3 个 channel，各自持仓不同
        bind_user("ou_user_a", "test_admin", "test123")
        bind_user("ou_user_b", "test_admin", "test123")
        bind_user("ou_user_c", "test_admin", "test123")
        create_position_entry(
            symbol="600519.SH", side="buy", quantity=100, price=1688.0,
            occurred_at=datetime.now(), source="manual", created_by="test_admin",
        )
        create_position_entry(
            symbol="002837.SZ", side="buy", quantity=200, price=12.0,
            occurred_at=datetime.now(), source="manual", created_by="test_admin",
        )
        create_position_entry(
            symbol="000001.SZ", side="buy", quantity=300, price=10.0,
            occurred_at=datetime.now(), source="manual", created_by="test_admin",
        )
        channel_a = _create_channel("p2p:oc_a", receive_id="ou_user_a")
        channel_b = _create_channel("p2p:oc_b", receive_id="ou_user_b")
        channel_c = _create_channel("p2p:oc_c", receive_id="ou_user_c")
        report_id = _create_report(_SAMPLE_REPORT)

        # 但 list_position_summary 是按 created_by 过滤的，所有人都会拿到全部持仓
        # 所以实际推送内容会一样（测试只验证过滤逻辑路径都被触发）
        with patch(
            "service.quant.schedule_user_push_service.send_feishu_text",
            return_value={"message_type": "text", "request_payload": {}, "response_payload": {"code": 0}},
        ):
            results = push_report_filtered_per_channel(
                [channel_a.id, channel_b.id, channel_c.id], report_id
            )

        assert len(results) == 3
        for r in results:
            assert r["filter_applied"] is True
            assert r["username"] == "test_admin"
        # 持仓集合应包含全部 3 只
        assert set(results[0]["held_symbols"]) == {"600519.SH", "002837.SZ", "000001.SZ"}
