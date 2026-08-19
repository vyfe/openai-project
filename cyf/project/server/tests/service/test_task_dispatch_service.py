"""task_dispatch_service 集成测试 — 验证 Agent 任务队列跨进程持久化与 schedule_run 联动。"""

from datetime import datetime
from unittest.mock import patch

import pytest

from service.quant.task_dispatch_service import (
    create_fetch_bars_task,
    claim_next_task,
    mark_task_success,
    mark_task_failed,
    list_tasks,
    reset_task,
)
from service.quant.schedule_query_service import (
    RUN_STATUS_AWAITING_DATA,
    RUN_STATUS_SUCCESS,
    RUN_STATUS_FAILED,
    RUN_STATUS_PENDING,
    create_schedule_config,
    manual_trigger_schedule,
)


def _force_now(year=2025, month=1, day=15, hour=15):
    return patch("service.quant.schedule_query_service.datetime", wraps=datetime)


class TestCreateFetchBarsTask:
    def test_creates_pending_task_in_db(self):
        task = create_fetch_bars_task(
            symbols=["000001.SZ", "600519.SH"],
            start_date="2025-01-10",
            end_date="2025-01-15",
            provider="auto",
            adjust_flag="qfq",
            note="unit-test",
            lease_seconds=300,
        )
        assert task["status"] == "pending"
        assert task["task_type"] == "fetch_a_share_daily_bars"
        assert task["client_id"] == ""
        assert task["payload"]["symbols"] == ["000001.SZ", "600519.SH"]
        assert task["lease_seconds"] == 300
        assert task["task_id"]

    def test_persists_schedule_run_id(self):
        task = create_fetch_bars_task(
            symbols=["000001.SZ"],
            start_date="2025-01-10",
            end_date="2025-01-15",
            schedule_run_id=42,
        )
        assert task["schedule_run_id"] == 42


class TestClaimNextTask:
    def test_returns_none_when_empty(self):
        assert claim_next_task(client_id="agent-A") is None

    def test_claims_pending_task(self):
        created = create_fetch_bars_task(
            symbols=["000001.SZ"],
            start_date="2025-01-10",
            end_date="2025-01-15",
        )
        claimed = claim_next_task(client_id="agent-A")
        assert claimed is not None
        assert claimed["task_id"] == created["task_id"]
        assert claimed["status"] == "leased"
        assert claimed["client_id"] == "agent-A"
        assert claimed["leased_at"]
        assert claimed["lease_expires_at"]
        assert claimed["attempts"] == 1


class TestMarkTaskSuccess:
    def test_marks_success(self):
        task = create_fetch_bars_task(
            symbols=["000001.SZ"],
            start_date="2025-01-10",
            end_date="2025-01-15",
        )
        claim_next_task(client_id="agent-A")
        result = mark_task_success(
            task_id=task["task_id"],
            client_id="agent-A",
            import_batch={"batch_id": "B1", "records": 10},
            message="ok",
        )
        assert result["status"] == "success"
        assert result["import_batch"]["batch_id"] == "B1"
        assert result["finished_at"]

    def test_rejects_wrong_client(self):
        task = create_fetch_bars_task(
            symbols=["000001.SZ"],
            start_date="2025-01-10",
            end_date="2025-01-15",
        )
        claim_next_task(client_id="agent-A")
        with pytest.raises(ValueError, match="任务不属于当前客户端"):
            mark_task_success(task_id=task["task_id"], client_id="agent-B")


class TestMarkTaskFailed:
    def test_marks_failed(self):
        task = create_fetch_bars_task(
            symbols=["000001.SZ"],
            start_date="2025-01-10",
            end_date="2025-01-15",
        )
        claim_next_task(client_id="agent-A")
        result = mark_task_failed(task_id=task["task_id"], client_id="agent-A", message="fetch error")
        assert result["status"] == "failed"
        assert "fetch error" in result["message"]


class TestResetTask:
    def test_reset_returns_to_pending(self):
        task = create_fetch_bars_task(
            symbols=["000001.SZ"],
            start_date="2025-01-10",
            end_date="2025-01-15",
        )
        claim_next_task(client_id="agent-A")
        mark_task_failed(task_id=task["task_id"], client_id="agent-A", message="x")
        result = reset_task(task_id=task["task_id"])
        assert result["status"] == "pending"
        assert result["client_id"] == ""
        assert result["leased_at"] is None


class TestScheduleRunClosedLoop:
    """Agent 上报时联动 schedule_run 状态。"""

    def _make_awaiting_run(self):
        config = create_schedule_config(
            name=f"闭环测试-{datetime.now().timestamp()}",
            task_type="data_sync",
            cron_expr="20 15 * * 1-5",
            payload={"symbols": ["000001.SZ"]},
        )
        with patch("service.quant.schedule_query_service.datetime", wraps=datetime) as mock_dt:
            mock_dt.now.return_value = datetime(2025, 1, 15, 15, 0)
            run = manual_trigger_schedule(config["id"])
        from quant.entities import QuantScheduleRun
        record = QuantScheduleRun.get_by_id(run["id"])
        record.status = RUN_STATUS_AWAITING_DATA
        record.message = "已下发任务，等待 Agent 上报"
        record.save()
        return record

    def test_agent_success_updates_schedule_run(self):
        run = self._make_awaiting_run()
        task = create_fetch_bars_task(
            symbols=["000001.SZ"],
            start_date="2025-01-10",
            end_date="2025-01-15",
            schedule_run_id=run.id,
        )
        claim_next_task(client_id="agent-A")
        mark_task_success(
            task_id=task["task_id"],
            client_id="agent-A",
            import_batch={"batch_id": "B-CLOSED-1", "records": 1},
        )

        from quant.entities import QuantScheduleRun
        refreshed = QuantScheduleRun.get_by_id(run.id)
        assert refreshed.status == RUN_STATUS_SUCCESS
        assert refreshed.finished_at is not None
        assert "Agent 上报成功" in refreshed.message

    def test_agent_failure_updates_schedule_run(self):
        run = self._make_awaiting_run()
        task = create_fetch_bars_task(
            symbols=["000001.SZ"],
            start_date="2025-01-10",
            end_date="2025-01-15",
            schedule_run_id=run.id,
        )
        claim_next_task(client_id="agent-A")
        mark_task_failed(task_id=task["task_id"], client_id="agent-A", message="remote 5xx")

        from quant.entities import QuantScheduleRun
        refreshed = QuantScheduleRun.get_by_id(run.id)
        assert refreshed.status == RUN_STATUS_FAILED
        assert "Agent 上报失败" in refreshed.message
        assert "remote 5xx" in refreshed.message

    def test_skips_link_when_schedule_run_not_awaiting(self):
        """非 awaiting_data 状态的 schedule_run 不应被覆盖（比如已被人工重置）。"""
        config = create_schedule_config(
            name="覆盖测试",
            task_type="data_sync",
            cron_expr="20 15 * * 1-5",
            payload={"symbols": ["000001.SZ"]},
        )
        with patch("service.quant.schedule_query_service.datetime", wraps=datetime) as mock_dt:
            mock_dt.now.return_value = datetime(2025, 1, 15, 15, 0)
            run = manual_trigger_schedule(config["id"])
        from quant.entities import QuantScheduleRun
        record = QuantScheduleRun.get_by_id(run["id"])
        record.status = RUN_STATUS_PENDING  # 已被人重置
        record.save()

        task = create_fetch_bars_task(
            symbols=["000001.SZ"],
            start_date="2025-01-10",
            end_date="2025-01-15",
            schedule_run_id=run["id"],
        )
        claim_next_task(client_id="agent-A")
        mark_task_success(task_id=task["task_id"], client_id="agent-A", import_batch={})

        refreshed = QuantScheduleRun.get_by_id(run["id"])
        assert refreshed.status == RUN_STATUS_PENDING  # 保持不变

    def test_no_link_no_side_effect(self):
        """task 没有 schedule_run_id 时不应触碰任何 schedule_run。"""
        config = create_schedule_config(
            name="无联动测试",
            task_type="data_sync",
            cron_expr="20 15 * * 1-5",
            payload={"symbols": ["000001.SZ"]},
        )
        with patch("service.quant.schedule_query_service.datetime", wraps=datetime) as mock_dt:
            mock_dt.now.return_value = datetime(2025, 1, 15, 15, 0)
            unrelated_run = manual_trigger_schedule(config["id"])
        from quant.entities import QuantScheduleRun
        unrelated_record = QuantScheduleRun.get_by_id(unrelated_run["id"])
        unrelated_record.status = RUN_STATUS_SUCCESS
        unrelated_record.save()
        original_status = unrelated_record.status

        task = create_fetch_bars_task(
            symbols=["000001.SZ"],
            start_date="2025-01-10",
            end_date="2025-01-15",
            schedule_run_id=None,
        )
        claim_next_task(client_id="agent-A")
        mark_task_success(task_id=task["task_id"], client_id="agent-A", import_batch={})

        refreshed = QuantScheduleRun.get_by_id(unrelated_run["id"])
        assert refreshed.status == original_status


class TestListTasks:
    def test_orders_by_created_at_desc(self):
        a = create_fetch_bars_task(symbols=["A"], start_date="2025-01-10", end_date="2025-01-15")
        b = create_fetch_bars_task(symbols=["B"], start_date="2025-01-10", end_date="2025-01-15")
        items = list_tasks(limit=10)
        ids = [item["task_id"] for item in items]
        assert ids[0] == b["task_id"]
        assert ids[1] == a["task_id"]