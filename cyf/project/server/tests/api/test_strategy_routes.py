"""策略 API 路由集成测试 — 验证 Flask test client 端到端请求。"""

import json
import pytest


class TestStrategyRoutes:
    """测试 /never_guess_my_usage/quant/strategy/* 路由。"""

    def test_list_empty(self, auth_client):
        resp = auth_client.get("/never_guess_my_usage/quant/strategy/list")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert isinstance(data["data"], list)

    def test_create_strategy(self, auth_client):
        resp = auth_client.post("/never_guess_my_usage/quant/strategy/create", json={
            "name": "API策略",
            "symbols": ["000001.SZ"],
            "rule_config": {"logic": "all", "rules": []},
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["data"]["name"] == "API策略"

    def test_create_missing_name(self, auth_client):
        resp = auth_client.post("/never_guess_my_usage/quant/strategy/create", json={})
        data = resp.get_json()
        assert data["success"] is False

    def test_get_strategy(self, auth_client):
        create_resp = auth_client.post("/never_guess_my_usage/quant/strategy/create", json={"name": "GetTest"})
        created = create_resp.get_json()["data"]

        resp = auth_client.get(f"/never_guess_my_usage/quant/strategy/get/{created['id']}")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["data"]["name"] == "GetTest"

    def test_no_auth_returns_401(self, app):
        """无认证参数应返回 401。"""
        with app.test_client() as client:
            resp = client.get("/never_guess_my_usage/quant/strategy/list")
            assert resp.status_code == 401


class TestPromptTemplateRoutes:
    def test_create_and_update_extra_sections(self, auth_client):
        created = auth_client.post(
            "/never_guess_my_usage/quant/prompt_template/create",
            json={
                "prompt_version": "template-v1",
                "prompt_template": "测试模板",
                "extra_sections": [{"title": "风险矩阵", "instruction": "列出风险"}],
            },
        ).get_json()["data"]
        assert created["extra_sections"] == [{"title": "风险矩阵", "instruction": "列出风险"}]

        updated = auth_client.post(
            "/never_guess_my_usage/quant/prompt_template/update",
            json={
                "id": created["id"],
                "extra_sections": [{"title": "操作清单", "instruction": "列出动作"}],
            },
        ).get_json()["data"]
        assert updated["extra_sections"] == [{"title": "操作清单", "instruction": "列出动作"}]
