"""数据/仪表盘 API 路由集成测试。"""

import pytest


class TestDataRoutes:
    """测试数据相关路由。"""

    def test_dashboard_overview(self, auth_client):
        resp = auth_client.get("/never_guess_my_usage/quant/dashboard/overview")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True

    def test_providers(self, auth_client):
        resp = auth_client.get("/never_guess_my_usage/quant/providers")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True

    def test_daily_bars_missing_symbol(self, auth_client):
        resp = auth_client.get("/never_guess_my_usage/quant/data/daily_bars")
        data = resp.get_json()
        # 无 symbol 参数应返回失败
        assert data["success"] is False

    def test_daily_bars_with_symbol(self, auth_client, seed_daily_bars):
        resp = auth_client.get("/never_guess_my_usage/quant/data/daily_bars", params={"symbol": "000001.SZ"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
