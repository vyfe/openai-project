"""调度 API 路由集成测试。"""

import pytest

from datetime import datetime
from unittest.mock import patch

from service.quant.schedule_query_service import (
    RUN_STATUS_AWAITING_DATA,
    RUN_STATUS_CANCELLED,
    RUN_STATUS_SUCCESS,
    create_schedule_config,
    manual_trigger_schedule,
)


class TestSchedulerRoutes:
    """测试 /scheduler/* 路由。"""

    def test_meta(self, auth_client):
        resp = auth_client.get("/never_guess_my_usage/quant/scheduler/meta")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True

    def test_configs_empty(self, auth_client):
        resp = auth_client.get("/never_guess_my_usage/quant/scheduler/configs")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True

    def test_create_config(self, auth_client):
        resp = auth_client.post("/never_guess_my_usage/quant/scheduler/config/create", json={
            "name": "每日拉数",
            "task_type": "data_sync",
            "cron_expr": "20 15 * * 1-5",
            "payload": {"symbols": ["000001.SZ"]},
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True

    def test_create_missing_name(self, auth_client):
        resp = auth_client.post("/never_guess_my_usage/quant/scheduler/config/create", json={
            "task_type": "data_sync",
            "cron_expr": "20 15 * * 1-5",
            "payload": {"symbols": ["000001.SZ"]},
        })
        data = resp.get_json()
        assert data["success"] is False


class TestSchedulerCancelRun:
    """POST /scheduler/run/<id>/cancel：强制取消执行记录。"""

    def _make_run_in_status(self, status: str) -> int:
        from quant.entities import QuantScheduleRun
        config = create_schedule_config(
            name="取消 API 测试",
            task_type="data_sync",
            cron_expr="20 15 * * 1-5",
            payload={"symbols": ["000001.SZ"]},
        )
        with patch("service.quant.schedule_query_service.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2025, 1, 15, 15, 0)
            run = manual_trigger_schedule(config["id"])
        record = QuantScheduleRun.get_by_id(run["id"])
        record.status = status
        record.save()
        return record.id

    def test_cancel_awaiting_data_run(self, auth_client):
        """核心场景：agent 长时间不上报 → run 卡 awaiting_data → 一键取消。"""
        run_id = self._make_run_in_status(RUN_STATUS_AWAITING_DATA)
        resp = auth_client.post(
            f"/never_guess_my_usage/quant/scheduler/run/{run_id}/cancel",
            json={"reason": "agent 上报超时"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["data"]["status"] == RUN_STATUS_CANCELLED
        assert "agent 上报超时" in data["data"]["message"]

    def test_cancel_reason_optional(self, auth_client):
        """reason 不传也能成功——给默认文案。"""
        run_id = self._make_run_in_status(RUN_STATUS_AWAITING_DATA)
        resp = auth_client.post(
            f"/never_guess_my_usage/quant/scheduler/run/{run_id}/cancel",
            json={},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["data"]["status"] == RUN_STATUS_CANCELLED

    def test_cancel_terminal_run_returns_error(self, auth_client):
        """终态 run 不能取消——避免误覆盖已成功的状态。"""
        run_id = self._make_run_in_status(RUN_STATUS_SUCCESS)
        resp = auth_client.post(
            f"/never_guess_my_usage/quant/scheduler/run/{run_id}/cancel",
            json={"reason": "误操作"},
        )
        data = resp.get_json()
        assert data["success"] is False
        assert "不支持取消" in data["msg"]

    def test_cancel_unknown_run_returns_error(self, auth_client):
        resp = auth_client.post(
            "/never_guess_my_usage/quant/scheduler/run/999999/cancel",
            json={},
        )
        data = resp.get_json()
        assert data["success"] is False
