from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from model.entities import Dialog
from model.repositories.log_repository import set_dialog
from service.dialog_context_service import build_dialog_context_payload


def _seed_dialog(username="test_admin", title="源对话"):
    return set_dialog(
        username,
        "gpt-test",
        "chat",
        title,
        build_dialog_context_payload(
            [
                {"role": "user", "content": "请分析这个问题", "time": "2026-07-04 10:00:00"},
                {"role": "assistant", "content": "已有结论", "time": "2026-07-04 10:01:00"},
            ],
            usage={"total_tokens": 100001},
        ),
    )


def _mock_openai_client(summary="交接摘要内容"):
    usage = SimpleNamespace(total_tokens=123, prompt_tokens=100, completion_tokens=23)
    message = SimpleNamespace(content=summary)
    choice = SimpleNamespace(message=message)
    result = SimpleNamespace(choices=[choice], usage=usage)
    result.to_dict = lambda: {"content": summary, "usage": {"total_tokens": 123}}
    client = MagicMock()
    client.chat.completions.create.return_value = result
    return client


class TestHandoffRoutes:
    def test_handoff_rejects_foreign_dialog(self, auth_client):
        dialog_id = _seed_dialog(username="other_user")

        resp = auth_client.post("/never_guess_my_usage/handoff", json={"dialog_id": dialog_id, "model": "gpt-test"})

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is False
        assert "不存在或无权限" in data["msg"]

    def test_handoff_creates_new_dialog(self, auth_client):
        source_id = _seed_dialog()
        mock_client = _mock_openai_client()

        with patch("service.handoff_service.is_valid_model", return_value=True), \
             patch("service.handoff_service.get_client_for_user", return_value=(mock_client, 0)):
            resp = auth_client.post("/never_guess_my_usage/handoff", json={"dialog_id": source_id, "model": "gpt-test"})

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["data"]["dialog_id"] != source_id
        assert data["data"]["dialog_name"].startswith("交接摘要 - 源对话")
        assert data["data"]["usage"]["total_tokens"] == 123

        created = Dialog.get_by_id(data["data"]["dialog_id"])
        assert created.username == "test_admin"
        assert created.modelname == "gpt-test"
        assert "交接摘要内容" in created.context

    def test_dialog_content_returns_usage(self, auth_client):
        dialog_id = _seed_dialog()

        resp = auth_client.post("/never_guess_my_usage/split_his_content", json={"dialogId": dialog_id})

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["content"]["usage"]["total_tokens"] == 100001
