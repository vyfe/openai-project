import io
from dataclasses import replace
from unittest.mock import patch

import pytest

from conf.runtime import runtime_state

pytestmark = pytest.mark.api
BASE = "/never_guess_my_usage/music"
CLOUD = {"data": {"status": 2, "audio": "https://audio.example.com/song.mp3"},
         "extra_info": {"music_duration": 25364}}


@pytest.fixture(autouse=True)
def music_settings(test_settings, tmp_path):
    with patch.object(runtime_state, "settings", replace(test_settings,
        minimax_api_key="sk-api-test-only", minimax_storage_dir=str(tmp_path / "music"))):
        yield


def test_requires_admin_even_for_state(app):
    client = app.test_client()
    assert client.get(BASE + "/state").status_code == 401


def test_state_never_returns_secret(auth_client):
    response = auth_client.get(BASE + "/state")
    assert response.status_code == 200
    assert response.get_json()["data"]["config"]["ready"] is True
    assert "sk-api-test-only" not in response.get_data(as_text=True)


def test_generate_persists_track_and_serves_local_audio(auth_client):
    with patch("service.minimax_client.MiniMaxClient.request", return_value=CLOUD), \
         patch("service.minimax_client.MiniMaxClient.download_audio", return_value=b"ID3song"):
        response = auth_client.post(BASE + "/generate", json={"title": "清晨", "prompt": "轻快的民谣", "lyrics": "歌词", "model": "music-3.0"})
    assert response.status_code == 200
    row = response.get_json()["data"]
    assert row["status"] == "ready"
    detail = auth_client.get(BASE + "/track/" + row["id"]).get_json()["data"]
    assert detail["prompt"] == "轻快的民谣"
    assert detail["lyrics"] == "歌词"
    audio = auth_client.get(BASE + f"/audio/{row['id']}/mp3")
    assert audio.status_code == 200
    assert audio.data == b"ID3song"
    assert audio.headers["Cache-Control"] == "private, no-store"


def test_invalid_parameters_never_reach_paid_api(auth_client):
    with patch("service.minimax_client.MiniMaxClient.request") as call:
        response = auth_client.post(BASE + "/generate", json={"prompt": "风格"})
    assert response.status_code == 400
    call.assert_not_called()


def test_delete_removes_track(auth_client):
    with patch("service.minimax_client.MiniMaxClient.request", return_value=CLOUD), \
         patch("service.minimax_client.MiniMaxClient.download_audio", return_value=b"ID3song"):
        row = auth_client.post(BASE + "/generate", json={"prompt": "风格", "lyrics": "歌词"}).get_json()["data"]
    response = auth_client.post(BASE + "/delete", json={"id": row["id"]})
    assert response.status_code == 200
    assert auth_client.get(BASE + "/track/" + row["id"]).status_code == 400


def test_cover_preprocess_and_generate(app, auth_client, seed_admin_user):
    client = app.test_client()
    cloud = {"cover_feature_id": "feat-123", "formatted_lyrics": "[Verse]\n街角的路灯亮了", "audio_duration": 42.5}
    with patch("service.minimax_client.MiniMaxClient.request", return_value=cloud):
        response = client.post(BASE + "/cover/preprocess", data={
            "user": "test_admin", "password": "test123",
            "audio": (io.BytesIO(b"ID3reference"), "song.mp3"), "audio_duration": "42.5", "title": "翻唱一版"})
    assert response.status_code == 200
    track = response.get_json()["data"]
    assert track["status"] == "cover_ready"
    assert track["lyrics"] == "[Verse]\n街角的路灯亮了"
    with patch("service.minimax_client.MiniMaxClient.request", return_value=CLOUD) as call, \
         patch("service.minimax_client.MiniMaxClient.download_audio", return_value=b"ID3cover"):
        response = auth_client.post(BASE + "/cover/generate", json={
            "id": track["id"], "prompt": "流行摇滚，女声演唱，副歌有强力和弦", "lyrics": "[Verse]\n改过的歌词"})
    assert response.status_code == 200
    assert call.call_args.args[1]["cover_feature_id"] == "feat-123"
    assert auth_client.get(BASE + f"/audio/{track['id']}/mp3").data == b"ID3cover"


def test_cover_preprocess_rejects_unsupported_format(app, seed_admin_user):
    client = app.test_client()
    with patch("service.minimax_client.MiniMaxClient.request") as call:
        response = client.post(BASE + "/cover/preprocess", data={
            "user": "test_admin", "password": "test123",
            "audio": (io.BytesIO(b"not audio"), "song.txt"), "audio_duration": "42.5"})
    assert response.status_code == 400
    call.assert_not_called()
