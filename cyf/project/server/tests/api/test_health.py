"""健康检查端点集成测试 — 验证 /health 的就绪判断和组件探针。"""

import pytest
from unittest.mock import patch


class TestHealthCheck:
    def test_health_ok(self, app):
        with app.test_client() as client:
            resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"
        assert data["service"] == "openai-project"
        assert "components" in data
        assert data["components"]["quant_db"] == "ok"

    def test_health_includes_components_dict(self, app):
        with app.test_client() as client:
            resp = client.get("/health")
        data = resp.get_json()
        assert isinstance(data["components"], dict)
        assert len(data["components"]) >= 1

    def test_health_degraded_when_db_fails(self, app):
        """模拟 quant_db 探针抛异常，期望 503 + degraded。"""
        from conf.app_factory import _probe_components

        def _broken_probe():
            return {"quant_db": "error: simulated"}

        with patch("conf.app_factory._probe_components", _broken_probe):
            with app.test_client() as client:
                resp = client.get("/health")
        assert resp.status_code == 503
        data = resp.get_json()
        assert data["status"] == "degraded"
        assert data["components"]["quant_db"].startswith("error")

    def test_root_still_returns_ok_for_options(self, app):
        """保留 / 的 CORS 预检兼容。"""
        with app.test_client() as client:
            resp = client.options("/")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "OK"