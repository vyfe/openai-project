"""调度 API 路由集成测试。"""

import pytest


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
