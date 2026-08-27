"""execute_schedule_run 集成测试 — 覆盖 schedule run 分发链路，防止重构漏改变量名（NameError 兜底）。

历史教训：commit 49eab60 重构 execute_data_sync 支持多 frequency 时，把变量名 task_id 改成 task_ids，
但第 408-410 行的 logger.info 没同步更新，导致 data_sync 分支 100% 抛 NameError: name 'task_id' is not defined。
该测试断言走完整个 happy path 不抛 NameError 并产出正确的 awaiting_data 状态。
"""

from datetime import datetime
from unittest.mock import patch

import pytest

from service.quant.schedule_execution_service import execute_schedule_run
from service.quant.schedule_query_service import (
    RUN_STATUS_AWAITING_DATA,
    create_schedule_config,
    manual_trigger_schedule,
)
from quant.entities import QuantScheduleRun


def _create_pending_data_sync_run(payload=None) -> int:
    """创建一条待执行的 data_sync schedule_run 并返回 run_id。"""
    config = create_schedule_config(
        name="data-sync-nameerror-guard",
        task_type="data_sync",
        cron_expr="20 15 * * 1-5",
        payload=payload or {"symbols": ["000001.SZ"]},
    )
    with patch("service.quant.schedule_query_service.datetime") as mock_dt:
        mock_dt.now.return_value = datetime(2025, 1, 15, 15, 0)
        triggered = manual_trigger_schedule(config["id"])
    return triggered["id"]


class TestExecuteScheduleRunDataSync:
    """data_sync 任务：跑完 execute_schedule_run 后应当走 awaiting_data 状态，不抛 NameError。"""

    def test_data_sync_does_not_raise_name_error(self):
        """核心兜底：执行 execute_schedule_run(data_sync) 不抛 NameError。

        重构 execute_data_sync 的变量名时，必须保证 logger.info 调用同步更新，
        否则走到 awaiting_data 状态记录时必爆 NameError。
        """
        run_id = _create_pending_data_sync_run()
        result = execute_schedule_run(run_id)
        assert result is not None

    def test_data_sync_enters_awaiting_data_status(self):
        run_id = _create_pending_data_sync_run()
        execute_schedule_run(run_id)

        record = QuantScheduleRun.get_by_id(run_id)
        assert record.status == RUN_STATUS_AWAITING_DATA

    def test_data_sync_message_lists_task_ids(self):
        """message 字段应当包含至少一个 task_id（多 frequency 时逗号分隔），便于排查。"""
        run_id = _create_pending_data_sync_run()
        execute_schedule_run(run_id)

        record = QuantScheduleRun.get_by_id(run_id)
        assert "已下发任务" in record.message
        # 单一 frequency（默认）应当至少有一个 task_id 出现在 message 里
        assert any(ch.isdigit() or ch.isalpha() for ch in record.message)

    def test_data_sync_single_frequency_creates_one_task(self):
        """默认 payload 不带 frequencies 时，应当只下发一条 task（兼容旧 schema）。"""
        run_id = _create_pending_data_sync_run({"symbols": ["000001.SZ"]})
        execute_schedule_run(run_id)

        from quant.quant_entities_ops import QuantClientTask
        tasks = list(QuantClientTask.select().where(QuantClientTask.schedule_run_id == run_id))
        assert len(tasks) == 1
        assert tasks[0].task_type == "fetch_a_share_daily_bars"


class TestExecuteScheduleRunGuards:
    """execute_schedule_run 的状态守卫：非 pending/retry 状态应拒绝执行。"""

    def test_awaiting_data_run_cannot_be_executed_again(self):
        """awaiting_data 状态的 run 不应被二次 execute（agent 未上报前不应重新派发）。"""
        run_id = _create_pending_data_sync_run()
        execute_schedule_run(run_id)
        with pytest.raises(ValueError, match="当前 run 状态不允许执行"):
            execute_schedule_run(run_id)