import io
from dataclasses import replace
from unittest.mock import patch

import pytest

from conf.runtime import runtime_state
from service.minimax_client import VoiceError
from service.minimax_voice_service import MiniMaxVoiceService

pytestmark = pytest.mark.api
BASE = "/never_guess_my_usage/voice"


@pytest.fixture(autouse=True)
def voice_settings(test_settings, tmp_path):
    with patch.object(runtime_state, "settings", replace(test_settings,
        minimax_api_key="sk-api-test-only", minimax_storage_dir=str(tmp_path / "voice"))):
        yield


def test_requires_admin_even_for_audio(app):
    client = app.test_client()
    for url in (BASE + "/state", BASE + "/profile", BASE + "/audio/20261022-123456-aabbccdd/mp3"):
        assert client.get(url).status_code == 401


def test_state_never_returns_secret(auth_client):
    response = auth_client.get(BASE + "/state")
    assert response.status_code == 200
    assert response.get_json()["data"]["config"]["ready"] is True
    assert "sk-api-test-only" not in response.get_data(as_text=True)


def test_business_error_preserves_official_code(auth_client):
    with patch("service.minimax_client.MiniMaxClient.request", side_effect=VoiceError("无复刻权限", 502, 2038)):
        response = auth_client.post(BASE + "/sync", json={})
    assert response.status_code == 502
    assert response.get_json()["code"] == 2038
    assert response.get_json()["success"] is False


def test_multipart_clone_decodes_form_flags(app, seed_admin_user):
    client = app.test_client()
    with patch.object(MiniMaxVoiceService, "clone", return_value={"voice_id": "YuexiTest001"}) as clone:
        response = client.post(BASE + "/clone", data={"user": "test_admin", "password": "test123", "consent": "true",
            "need_noise_reduction": "false", "sample": (io.BytesIO(b"file"), "sample.mp3")})
    assert response.get_json()["success"] is True
    assert clone.call_args.args[0]["consent"] is True
    assert clone.call_args.args[0]["need_noise_reduction"] is False


def test_download_authorized_audio_only(auth_client):
    service = MiniMaxVoiceService()
    with patch.object(service.client, "request", return_value={"data": {"audio": "https://audio.example.com/test.mp3"}, "extra_info": {"audio_length": 1000}}), \
         patch.object(service.client, "download_audio", return_value=b"ID3test"):
        row = service.synthesize({"voice_id": "test0011", "text": "晚安"})
    response = auth_client.get(BASE + f"/audio/{row['id']}/mp3")
    assert response.status_code == 200
    assert response.data == b"ID3test"
    assert response.headers["Cache-Control"] == "private, no-store"
    response = auth_client.get(BASE + "/audio/not-an-id/txt")
    assert response.status_code == 400


def test_sqlite_detail_keeps_text_and_oss_url(auth_client):
    with patch("service.minimax_client.MiniMaxClient.request", return_value={"data": {"audio": "https://audio.example.com/test.mp3"}}), \
         patch("service.minimax_client.MiniMaxClient.download_audio", return_value=b"ID3test"):
        response = auth_client.post(BASE + "/synthesize", json={"voice_id": "YuexiTest001", "text": "粘贴进去的故事正文", "title": "第十一集"})
    assert response.status_code == 200
    row = response.get_json()["data"]
    detail = auth_client.get(BASE + "/reading/" + row["id"]).get_json()["data"]
    assert detail["text"] == "粘贴进去的故事正文"
    assert detail["audio_url"] == "https://audio.example.com/test.mp3"
    assert detail["url_expired"] is False


def test_keepalive_settings_can_be_read_and_saved(auth_client):
    response = auth_client.get(BASE + "/keepalive")
    assert response.status_code == 200
    assert response.get_json()["data"]["enabled"] is True
    response = auth_client.post(BASE + "/keepalive", json={"enabled": False, "hour": 4, "minute": 30, "disabled_voices": []})
    assert response.status_code == 200
    saved = auth_client.get(BASE + "/keepalive").get_json()["data"]
    assert saved["enabled"] is False
    assert saved["hour"] == 4 and saved["minute"] == 30


def test_keepalive_run_reports_attempts(auth_client):
    with patch("service.minimax_client.MiniMaxClient.request") as call:
        response = auth_client.post(BASE + "/keepalive/run", json={})
    assert response.status_code == 200
    assert response.get_json()["data"]["attempted"] == 0
    call.assert_not_called()


def test_keepalive_rejects_invalid_settings(auth_client):
    response = auth_client.post(BASE + "/keepalive", json={"enabled": True, "hour": 30, "minute": 0, "disabled_voices": []})
    assert response.status_code == 400
