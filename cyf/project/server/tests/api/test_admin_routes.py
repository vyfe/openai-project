from dataclasses import replace
from unittest.mock import patch

import pytest

from conf.runtime import runtime_state
from model.entities import SystemPrompt


pytestmark = pytest.mark.api


def _create_prompt(name="通用助手", group="default"):
    return SystemPrompt.create(
        role_name=name,
        role_group=group,
        role_desc="测试提示词",
        role_content="请保持准确。",
        status_valid=True,
    )


class TestAdminRoutes:
    def test_system_prompt_crud_serializes_model_instances(self, auth_client):
        prompt = _create_prompt()

        list_response = auth_client.get(
            "/never_guess_my_usage/system_prompt/list",
            params={"page": 1, "page_size": 10},
        )
        list_data = list_response.get_json()
        assert list_data["success"] is True
        assert list_data["data"]["items"][0]["id"] == prompt.id

        get_response = auth_client.get(f"/never_guess_my_usage/system_prompt/get/{prompt.id}")
        assert get_response.get_json()["data"]["role_content"] == "请保持准确。"

        update_response = auth_client.post(
            "/never_guess_my_usage/system_prompt/update",
            json={"id": prompt.id, "role_content": "请保持简洁。"},
        )
        assert update_response.get_json()["success"] is True
        assert update_response.get_json()["data"]["role_content"] == "请保持简洁。"

    def test_system_prompt_create_parses_boolean_status(self, auth_client):
        response = auth_client.post(
            "/never_guess_my_usage/system_prompt/create",
            json={
                "role_name": "禁用助手",
                "role_group": "default",
                "role_desc": "测试提示词",
                "role_content": "不生效。",
                "status_valid": False,
            },
        )

        data = response.get_json()
        assert data["success"] is True
        assert data["data"]["status_valid"] is False

    def test_sql_meta_returns_renderable_table_details(self, auth_client):
        _create_prompt()

        response = auth_client.get("/never_guess_my_usage/sql/meta")
        data = response.get_json()

        assert data["success"] is True
        assert data["data"]["database"]["path"]
        prompt_table = next(table for table in data["data"]["tables"] if table["table_name"] == "systemprompt")
        assert prompt_table["row_count"] == 1
        assert {column["name"] for column in prompt_table["columns"]} >= {"role_name", "role_content"}

    def test_sql_execute_returns_columns_and_rows(self, auth_client, test_settings):
        _create_prompt()

        enabled_settings = replace(test_settings, enable_sql_execute=True)
        with patch.object(runtime_state, "settings", enabled_settings):
            response = auth_client.post(
                "/never_guess_my_usage/sql_execute",
                json={"sql": "SELECT role_name FROM systemprompt"},
            )
            pragma_response = auth_client.post(
                "/never_guess_my_usage/sql_execute",
                json={"sql": "PRAGMA table_info(systemprompt)"},
            )

        data = response.get_json()
        assert data["success"] is True
        assert data["data"]["columns"] == ["role_name"]
        assert data["data"]["rows"] == [{"role_name": "通用助手"}]

        pragma_data = pragma_response.get_json()
        assert pragma_data["success"] is True, pragma_data
        assert "name" in pragma_data["data"]["columns"]

    def test_runtime_overview_returns_snapshot_at_data_root(self, auth_client):
        response = auth_client.get("/never_guess_my_usage/runtime/overview")
        data = response.get_json()

        assert data["success"] is True
        assert data["data"]["uptime_seconds"] >= 0
        assert data["data"]["database"]["path"]
        assert "runtime" not in data["data"]
