from dataclasses import replace
from unittest.mock import patch

import base64
import io

import pytest
from werkzeug.datastructures import FileStorage

from model.entities import MusicTrack
from service.minimax_client import VoiceError
from service.minimax_music_service import MiniMaxMusicService
from conf.settings import load_settings

pytestmark = pytest.mark.service

CLOUD = {"data": {"status": 2, "audio": "https://audio.example.com/song.mp3"},
         "extra_info": {"music_duration": 25364, "music_size": 813651}}


@pytest.fixture
def music_service(test_settings, tmp_path):
    return MiniMaxMusicService(replace(test_settings, minimax_api_key="sk-music-test-only",
        minimax_storage_dir=str(tmp_path / "music")))


def test_generate_persists_parameters_and_local_audio(music_service):
    with patch.object(music_service.client, "request", return_value=CLOUD) as call, \
         patch.object(music_service.client, "download_audio", return_value=b"ID3song"):
        row = music_service.generate({"title": "清晨", "prompt": "轻快的民谣", "lyrics": "[Verse]\n歌词", "model": "music-3.0"})
    assert row["status"] == "ready"
    assert row["has_audio"] is True
    assert row["duration_seconds"] == 25.364
    saved = MusicTrack.get_by_id(row["id"])
    assert saved.prompt == "轻快的民谣"
    assert saved.lyrics == "[Verse]\n歌词"
    assert saved.audio_url == "https://audio.example.com/song.mp3"
    assert music_service.audio_path(row["id"], "mp3").read_bytes() == b"ID3song"
    assert "轻快的民谣" in music_service.audio_path(row["id"], "txt").read_text()
    payload = call.call_args.args[1]
    assert payload["model"] == "music-3.0"
    assert payload["output_format"] == "url"
    assert payload["is_instrumental"] is False
    assert payload["lyrics_optimizer"] is False


def test_instrumental_needs_prompt_but_no_lyrics(music_service):
    with patch.object(music_service.client, "request", return_value=CLOUD) as call, \
         patch.object(music_service.client, "download_audio", return_value=b"ID3song"):
        music_service.generate({"prompt": "纯钢琴", "instrumental": True})
    payload = call.call_args.args[1]
    assert payload["is_instrumental"] is True
    assert "lyrics" not in payload


def test_lyrics_optimizer_allows_empty_lyrics(music_service):
    with patch.object(music_service.client, "request", return_value=CLOUD) as call, \
         patch.object(music_service.client, "download_audio", return_value=b"ID3song"):
        music_service.generate({"prompt": "轻快的民谣", "lyrics_optimizer": True})
    assert call.call_args.args[1]["lyrics_optimizer"] is True
    assert "lyrics" not in call.call_args.args[1]


def test_hex_audio_is_saved_without_downloading(music_service):
    response = {"data": {"status": 2, "audio": "494433" + "00" * 2000}, "extra_info": {"music_duration": 1000}}
    with patch.object(music_service.client, "request", return_value=response), \
         patch.object(music_service.client, "download_audio") as download:
        row = music_service.generate({"prompt": "风格", "lyrics": "词"})
    download.assert_not_called()
    assert row["status"] == "ready"
    assert row["audio_url"] is None
    assert music_service.audio_path(row["id"], "mp3").read_bytes()[:3] == b"ID3"


@pytest.mark.parametrize("payload", [
    {"prompt": "风格"},
    {"prompt": "", "instrumental": True},
    {"prompt": "风格", "lyrics": "词", "model": "music-cover"},
    {"prompt": "x" * 2001, "lyrics": "词"},
    {"prompt": "风格", "lyrics": "x" * 3501},
    {"prompt": "风格", "lyrics": "词", "instrumental": "yes"},
])
def test_invalid_parameters_never_call_paid_api(music_service, payload):
    with patch.object(music_service.client, "request") as call:
        with pytest.raises(VoiceError):
            music_service.generate(payload)
    call.assert_not_called()


def test_cloud_failure_keeps_parameters_and_marks_failed(music_service):
    with patch.object(music_service.client, "request", side_effect=VoiceError("余额不足", 502, 1008)):
        with pytest.raises(VoiceError):
            music_service.generate({"prompt": "风格", "lyrics": "词"})
    row = MusicTrack.select().get()
    assert row.status == "failed"
    assert row.prompt == "风格"
    assert row.audio_url is None


def test_uncertain_failure_marks_unknown(music_service):
    with patch.object(music_service.client, "request", side_effect=VoiceError("网络中断", 502, uncertain=True)):
        with pytest.raises(VoiceError):
            music_service.generate({"prompt": "风格", "lyrics": "词"})
    assert MusicTrack.select().get().status == "unknown"


def test_empty_audio_marks_unknown_without_guessing(music_service):
    with patch.object(music_service.client, "request", return_value={"data": {"status": 1}}):
        with pytest.raises(VoiceError):
            music_service.generate({"prompt": "风格", "lyrics": "词"})
    assert MusicTrack.select().get().status == "unknown"


def test_credentials_isolate_tracks(music_service):
    with patch.object(music_service.client, "request", return_value=CLOUD), \
         patch.object(music_service.client, "download_audio", return_value=b"ID3song"):
        music_service.generate({"prompt": "风格", "lyrics": "词"})
    other = MiniMaxMusicService(replace(music_service.settings, minimax_api_key="another-key"))
    assert other.snapshot()["tracks"] == []
    assert music_service.snapshot()["tracks"][0]["title"] == "风格"


def test_delete_removes_record_and_local_file(music_service):
    with patch.object(music_service.client, "request", return_value=CLOUD), \
         patch.object(music_service.client, "download_audio", return_value=b"ID3song"):
        row = music_service.generate({"prompt": "风格", "lyrics": "词"})
    music_service.delete(row["id"])
    assert MusicTrack.select().count() == 0
    assert not (music_service.store.folder / "music" / (row["id"] + ".mp3")).exists()


def test_audio_path_rejects_invalid_identifier(music_service):
    with pytest.raises(VoiceError):
        music_service.audio_path("../../conf/conf.ini", "mp3")
    with pytest.raises(VoiceError):
        music_service.audio_path("not-an-id", "mp3")


def reference(name="song.mp3", content=b"ID3reference"):
    return FileStorage(stream=io.BytesIO(content), filename=name)


def test_cover_preprocess_extracts_lyrics_and_feature_id(music_service):
    cloud = {"cover_feature_id": "feat-123", "formatted_lyrics": "[Verse]\n街角的路灯亮了",
             "audio_duration": 42.5}
    with patch.object(music_service.client, "request", return_value=cloud) as call:
        row = music_service.preprocess_cover({"audio_duration": "42.5", "title": "翻唱一版"},
                                             {"audio": reference()})
    assert row["status"] == "cover_ready"
    assert row["cover_ready"] is True
    assert row["lyrics"] == "[Verse]\n街角的路灯亮了"
    assert row["reference_duration"] == 42.5
    assert row["model"] == "music-cover"
    payload = call.call_args.args[1]
    assert payload["model"] == "music-cover"
    assert base64.b64decode(payload["audio_base64"]) == b"ID3reference"


def test_cover_generate_uses_feature_id_and_edited_lyrics(music_service):
    with patch.object(music_service.client, "request", return_value={"cover_feature_id": "feat-123", "formatted_lyrics": "原歌词"}):
        row = music_service.preprocess_cover({"audio_duration": "42.5"}, {"audio": reference()})
    with patch.object(music_service.client, "request", return_value=CLOUD) as call, \
         patch.object(music_service.client, "download_audio", return_value=b"ID3cover"):
        result = music_service.generate_cover({"id": row["id"], "prompt": "流行摇滚，女声演唱，副歌有强力和弦",
                                               "lyrics": "[Verse]\n改过的歌词", "title": "翻唱一版"})
    payload = call.call_args.args[1]
    assert payload["model"] == "music-cover"
    assert payload["cover_feature_id"] == "feat-123"
    assert payload["lyrics"] == "[Verse]\n改过的歌词"
    assert "audio_base64" not in payload
    assert result["status"] == "ready"
    assert music_service.audio_path(result["id"], "mp3").read_bytes() == b"ID3cover"


@pytest.mark.parametrize("payload,files", [
    ({"audio_duration": "42.5"}, {"audio": lambda: reference("song.txt")}),
    ({"audio_duration": "2"}, {"audio": lambda: reference()}),
    ({"audio_duration": "400"}, {"audio": lambda: reference()}),
    ({"audio_duration": "42.5"}, {"audio": lambda: reference(content=b"x" * (21 * 1024 * 1024))}),
])
def test_invalid_reference_audio_never_calls_cloud(music_service, payload, files):
    with patch.object(music_service.client, "request") as call:
        with pytest.raises(VoiceError):
            music_service.preprocess_cover(payload, {k: factory() for k, factory in files.items()})
    call.assert_not_called()


@pytest.mark.parametrize("payload", [
    {"id": "not-an-id", "prompt": "流行摇滚，女声演唱，副歌有强力和弦"},
    {"id": "20261022-160914-18d3cf5a", "prompt": "短"},
    {"id": "20261022-160914-18d3cf5a", "prompt": "流行摇滚，女声演唱，副歌有强力和弦", "lyrics": "太短"},
])
def test_invalid_cover_generation_never_calls_paid_api(music_service, payload):
    with patch.object(music_service.client, "request") as call:
        with pytest.raises(VoiceError):
            music_service.generate_cover(payload)
    call.assert_not_called()


def test_cover_without_feature_id_is_rejected(music_service):
    with patch.object(music_service.client, "request", return_value=CLOUD):
        row = music_service.generate({"prompt": "风格", "lyrics": "词"})
    with pytest.raises(VoiceError, match="翻唱特征"):
        music_service.generate_cover({"id": row["id"], "prompt": "流行摇滚，女声演唱，副歌有强力和弦"})


def test_music_config_falls_back_to_speech_credentials(tmp_path, monkeypatch):
    config = tmp_path / "minimax.ini"
    config.write_text("[minimax]\napi_key=speech-key\nregion=cn\ntimeout_seconds=180\n", encoding="utf-8")
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    monkeypatch.delenv("MINIMAX_MUSIC_API_KEY", raising=False)
    settings = load_settings(str(config))
    assert settings.minimax_music_api_key == ""
    assert not settings.minimax_music_api_key
    assert settings.minimax_music_region == "cn"
    assert settings.minimax_music_timeout_seconds == 180
    service = MiniMaxMusicService(replace(settings, minimax_storage_dir=str(tmp_path / "fallback")))
    assert service.client.key == "speech-key"


def test_music_dedicated_credentials_are_used(tmp_path, monkeypatch):
    config = tmp_path / "minimax.ini"
    config.write_text("[minimax]\napi_key=speech-key\nregion=cn\n"
                       "[minimax_music]\napi_key=music-key\nregion=intl\nmodel=music-2.6\ntimeout_seconds=200\n",
                       encoding="utf-8")
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    monkeypatch.delenv("MINIMAX_MUSIC_API_KEY", raising=False)
    settings = load_settings(str(config))
    assert settings.minimax_music_api_key == "music-key"
    assert settings.minimax_music_api_key
    assert settings.minimax_music_region == "intl"
    assert settings.minimax_music_model == "music-2.6"
    assert settings.minimax_music_timeout_seconds == 200
    dedicated = MiniMaxMusicService(replace(settings, minimax_storage_dir=str(tmp_path / "dedicated")))
    fallback = MiniMaxMusicService(replace(settings, minimax_music_api_key="", minimax_music_region="cn",
        minimax_storage_dir=str(tmp_path / "fallback")))
    assert dedicated.client.key == "music-key"
    assert dedicated.client.base_url == "https://api.minimax.io"
    assert dedicated.client.timeout == 200
    assert fallback.client.key == "speech-key"
    assert dedicated.store.scope != fallback.store.scope


def test_music_env_key_wins_over_config(tmp_path, monkeypatch):
    config = tmp_path / "minimax.ini"
    config.write_text("[minimax]\napi_key=speech-key\n[minimax_music]\napi_key=file-music-key\n", encoding="utf-8")
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    monkeypatch.setenv("MINIMAX_MUSIC_API_KEY", "env-music-key")
    settings = load_settings(str(config))
    assert settings.minimax_music_api_key == "env-music-key"
    assert settings.minimax_music_api_key
    assert "env-music-key" not in repr(settings)
