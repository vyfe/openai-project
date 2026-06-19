"""交易/持仓/操作 API 路由集成测试。"""

import pytest


class TestPositionRoutes:
    """测试 /never_guess_my_usage/quant/positions/* 路由。"""

    def test_summary_empty(self, auth_client):
        resp = auth_client.get("/never_guess_my_usage/quant/positions/summary")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True

    def test_create_position(self, auth_client):
        resp = auth_client.post("/never_guess_my_usage/quant/positions/create", json={
            "symbol": "000001.SZ",
            "side": "buy",
            "quantity": 100,
            "price": 12.0,
            "occurred_at": "2025-01-15 10:00:00",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["data"]["symbol"] == "000001.SZ"


class TestOperationRoutes:
    """测试 /never_guess_my_usage/quant/operations/* 路由。"""

    def test_list_empty(self, auth_client):
        resp = auth_client.get("/never_guess_my_usage/quant/operations/list")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True

    def test_create_operation(self, auth_client):
        resp = auth_client.post("/never_guess_my_usage/quant/operations/create", json={
            "symbol": "000001.SZ",
            "trade_date": "2025-01-15",
            "action": "buy",
            "status": "planned",
            "thesis": "测试买入",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
