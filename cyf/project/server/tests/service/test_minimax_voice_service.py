import io
import json
import wave
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import pytest
import requests
from werkzeug.datastructures import FileStorage

from conf.settings import load_settings
from model.entities import VoiceReading
from service.minimax_client import MiniMaxClient, VoiceError
from service.minimax_music_service import MiniMaxMusicService
from service.minimax_voice_service import MiniMaxVoiceService

pytestmark = pytest.mark.service


@pytest.fixture
def voice_service(test_settings, tmp_path):
    return MiniMaxVoiceService(replace(test_settings, minimax_api_key="sk-voice-test-only",
        minimax_storage_dir=str(tmp_path / "voice")))


def recording(seconds=12):
    stream = io.BytesIO()
    with wave.open(stream, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(8000)
        audio.writeframes(b"\0\0" * int(seconds * 8000))
    return FileStorage(stream=io.BytesIO(stream.getvalue()), filename="sample.wav")


def create_voice(service):
    with patch.object(service.clone_client, "upload", return_value=12345), patch.object(service.clone_client, "request", return_value={}):
        service.clone({"voice_id": "YuexiTest001", "alias": "我的声音", "consent": True}, {"sample": recording()})


def test_pending_voice_survives_empty_cloud_list(voice_service):
    create_voice(voice_service)
    with patch.object(voice_service.clone_client, "request", return_value={}):
        voice_service.sync()
    state = voice_service.snapshot()
    assert state["voices"][0]["voice_id"] == "YuexiTest001"
    assert state["voices"][0]["status"] == "pending"
    assert "sk-voice-test-only" not in json.dumps(state)


def test_formal_synthesis_activates_voice_and_persists_audio(voice_service):
    create_voice(voice_service)
    voice_service.preference({"voice_id": "YuexiTest001", "make_default": True})
    response = {"data": {"audio": "https://audio.example.com/story.mp3"}, "extra_info": {"audio_length": 210500, "usage_characters": 711, "usage_voice_count": 1}}
    # 刚复刻的音色尚未激活，首次合成用计费凭据付音色费用。
    with patch.object(voice_service.clone_client, "request", return_value=response) as call, \
         patch.object(voice_service.client, "download_audio", return_value=b"ID3test-audio"):
        result = voice_service.synthesize({"voice_id": "YuexiTest001", "title": "第十一集测试", "text": "阿禾走到月溪边。", "speed": 0.9})
    assert result["duration_seconds"] == 210.5
    assert voice_service.audio_path(result["id"], "mp3").read_bytes() == b"ID3test-audio"
    assert voice_service.audio_path(result["id"], "txt").read_text() == "阿禾走到月溪边。"
    assert voice_service.snapshot()["voices"][0]["status"] == "active"
    assert voice_service.snapshot()["history"][0]["usage_characters"] == 711
    saved = VoiceReading.get_by_id(result["id"])
    assert saved.audio_url == "https://audio.example.com/story.mp3"
    assert saved.source_text == "阿禾走到月溪边。"
    assert saved.status == "ready"
    assert saved.url_expires_at is not None
    assert call.call_args.args[1]["output_format"] == "url"
    assert call.call_args.args[1]["stream"] is False
    assert call.call_args.args[1]["voice_setting"]["voice_id"] == "YuexiTest001"
    assert "sk-voice-test-only" not in json.dumps(voice_service.profile())


def test_activated_voice_uses_subscription_credential(voice_service):
    create_voice(voice_service)
    response = {"data": {"audio": "https://audio.example.com/story.mp3"}, "extra_info": {"usage_characters": 711}}
    with patch.object(voice_service.clone_client, "request", return_value=response):
        voice_service.synthesize({"voice_id": "YuexiTest001", "text": "首次激活"})
    with patch.object(voice_service.client, "request", return_value=response) as call, \
         patch.object(voice_service.client, "download_audio", return_value=b"ID3again"):
        voice_service.synthesize({"voice_id": "YuexiTest001", "text": "第二次合成"})
    assert call.call_args.args[1]["voice_setting"]["voice_id"] == "YuexiTest001"


def test_insufficient_balance_falls_back_to_billing_credential(voice_service):
    # 本地台账没有该音色（手填 ID），先用订阅凭据，1008 后自动换计费凭据重试。
    with patch.object(voice_service.client, "request", side_effect=VoiceError("余额不足", 502, 1008)) as subscription, \
         patch.object(voice_service.clone_client, "request", return_value={"data": {"audio": "https://audio.example.com/story.mp3"}}) as billing, \
         patch.object(voice_service.client, "download_audio", return_value=b"ID3fallback"):
        result = voice_service.synthesize({"voice_id": "MyVoice1792673780684", "text": "余额不足降级"})
    assert subscription.call_count == 1
    assert billing.call_count == 1
    assert result["status"] == "ready"


def test_insufficient_balance_is_not_retried_on_billing_credential(voice_service):
    create_voice(voice_service)
    with patch.object(voice_service.clone_client, "request", side_effect=VoiceError("余额不足", 502, 1008)) as billing:
        with pytest.raises(VoiceError):
            voice_service.synthesize({"voice_id": "YuexiTest001", "text": "首次激活"})
    assert billing.call_count == 1


def test_download_failure_keeps_link_and_can_retry_without_regenerating(voice_service):
    with patch.object(voice_service.client, "request", return_value={"data": {"audio": "https://audio.example.com/story.mp3"}}) as generate, \
         patch.object(voice_service.client, "download_audio", side_effect=VoiceError("download failed")):
        row = voice_service.synthesize({"voice_id": "YuexiTest001", "text": "正文已经入库"})
    assert row["status"] == "remote_ready"
    assert VoiceReading.get_by_id(row["id"]).audio_url == "https://audio.example.com/story.mp3"
    with patch.object(voice_service.client, "request") as generate_again, \
         patch.object(voice_service.client, "download_audio", return_value=b"ID3retry"):
        assert voice_service.audio_path(row["id"], "mp3").read_bytes() == b"ID3retry"
    assert generate.call_count == 1
    generate_again.assert_not_called()
    assert voice_service.reading(row["id"])["text"] == "正文已经入库"
    assert voice_service.reading(row["id"])["status"] == "ready"


def test_synthesis_timeout_keeps_submitted_text_and_unknown_status(voice_service):
    with patch.object(voice_service.client, "request", side_effect=VoiceError("网络中断", 502, uncertain=True)):
        with pytest.raises(VoiceError):
            voice_service.synthesize({"voice_id": "YuexiTest001", "text": "保存这段正文"})
    row = VoiceReading.get(VoiceReading.scope == voice_service.store.scope)
    assert row.status == "unknown"
    assert row.source_text == "保存这段正文"
    assert row.audio_url is None


@pytest.mark.parametrize("uncertain,expected", [(True, "unknown"), (False, None)])
def test_clone_failure_keeps_only_uncertain_attempt(voice_service, uncertain, expected):
    with patch.object(voice_service.clone_client, "upload", return_value=12345), \
         patch.object(voice_service.clone_client, "request", side_effect=VoiceError("failed", uncertain=uncertain)):
        with pytest.raises(VoiceError):
            voice_service.clone({"voice_id": "YuexiTest001", "alias": "本人", "consent": True}, {"sample": recording()})
    voices = voice_service.snapshot()["voices"]
    assert (voices[0]["status"] if voices else None) == expected


@pytest.mark.parametrize("payload,files", [
    ({"voice_id": "bad", "alias": "本人", "consent": True}, {"sample": lambda: recording()}),
    ({"voice_id": "YuexiTest001", "alias": "本人", "consent": False}, {"sample": lambda: recording()}),
    ({"voice_id": "YuexiTest001", "alias": "本人", "consent": True}, {"sample": lambda: recording(2)}),
    ({"voice_id": "YuexiTest001", "alias": "本人", "consent": True, "need_noise_reduction": "yes"}, {"sample": lambda: recording()}),
])
def test_invalid_clone_never_uploads(voice_service, payload, files):
    with patch.object(voice_service.clone_client, "upload") as upload:
        with pytest.raises(VoiceError):
            voice_service.clone(payload, {k: factory() for k, factory in files.items()})
    upload.assert_not_called()


def test_delete_rejects_system_and_requires_exact_id(voice_service):
    voice_service.store.update(lambda s: s["cloud_voices"].append({"voice_id": "system-test", "voice_type": "system", "alias": "系统"}))
    with patch.object(voice_service.clone_client, "request") as call:
        with pytest.raises(VoiceError, match="系统音色"):
            voice_service.delete({"voice_id": "system-test", "confirmation": "system-test"})
        with pytest.raises(VoiceError, match="完整音色 ID"):
            voice_service.delete({"voice_id": "system-test", "confirmation": "wrong"})
    call.assert_not_called()


def test_delete_clears_default_after_cloud_success(voice_service):
    create_voice(voice_service)
    voice_service.preference({"voice_id": "YuexiTest001", "make_default": True})
    with patch.object(voice_service.clone_client, "request", return_value={}) as call:
        voice_service.delete({"voice_id": "YuexiTest001", "confirmation": "YuexiTest001"})
    assert voice_service.snapshot()["default_voice_id"] == ""
    assert voice_service.snapshot()["voices"] == []
    assert call.call_args.args[1] == {"voice_id": "YuexiTest001", "voice_type": "voice_cloning"}


def test_data_isolation_and_path_validation(voice_service):
    create_voice(voice_service)
    other = MiniMaxVoiceService(replace(voice_service.settings, minimax_api_key="different-key"))
    assert other.snapshot()["voices"] == []
    with pytest.raises(VoiceError):
        voice_service.audio_path("../../conf/conf.ini", "txt")
    with voice_service.store.locked("operation", blocking=False):
        with pytest.raises(VoiceError, match="正在执行"):
            with MiniMaxVoiceService(voice_service.settings).store.locked("operation", blocking=False):
                pass


@pytest.mark.parametrize("payload", [{"speed": float("nan")}, {"volume": 0}, {"pitch": 0.5}, {"model": "not-tts"}, {"text": "a" * 10000}])
def test_invalid_synthesis_never_calls_paid_api(voice_service, payload):
    with patch.object(voice_service.client, "request") as call:
        with pytest.raises(VoiceError):
            voice_service.synthesize({"voice_id": "YuexiTest001", "text": "晚安", **payload})
    call.assert_not_called()


def test_api_failure_is_redacted_and_not_retried(voice_service):
    response = Mock(status_code=200)
    response.json.return_value = {"base_resp": {"status_code": 1004, "status_msg": "bad key sk-voice-test-only"}}
    with patch("service.minimax_client.requests.post", return_value=response) as post:
        with pytest.raises(VoiceError) as error:
            voice_service.client.request("/v1/get_voice", {"voice_type": "all"})
    assert "sk-voice-test-only" not in str(error.value)
    assert error.value.code == 1004
    assert post.call_count == 1
    assert post.call_args.kwargs["allow_redirects"] is False


def test_timeout_reports_uncertain_without_retry(voice_service):
    with patch("service.minimax_client.requests.post", side_effect=requests.Timeout) as post:
        with pytest.raises(VoiceError) as error:
            voice_service.client.request("/v1/t2a_v2", {})
    assert error.value.uncertain is True
    assert post.call_count == 1


def test_configuration_env_wins_and_default_has_no_key(tmp_path, monkeypatch):
    config = tmp_path / "voice.ini"
    config.write_text("[minimax]\napi_key=<填入 API Key>\nregion=cn\n", encoding="utf-8")
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    settings = load_settings(str(config))
    assert MiniMaxClient(settings).ready is False
    monkeypatch.setenv("MINIMAX_API_KEY", "voice-env-test")
    settings = load_settings(str(config))
    assert settings.minimax_api_key == "voice-env-test"
    assert "voice-env-test" not in repr(settings)


def test_clone_credential_follows_billing_key_while_synthesis_uses_speech_key(test_settings, tmp_path):
    settings = replace(test_settings, minimax_api_key="speech-key", minimax_music_api_key="billing-key",
                        minimax_clone_api_key="billing-key", minimax_clone_region="cn",
                        minimax_storage_dir=str(tmp_path / "voice"))
    service = MiniMaxVoiceService(settings)
    assert service.client.key == "speech-key"
    assert service.clone_client.key == "billing-key"
    assert service.snapshot()["config"]["clone_dedicated"] is True
    assert service.snapshot()["config"]["clone_ready"] is True
    with patch.object(service.clone_client, "request", return_value={}) as clone_call, \
         patch.object(service.client, "request") as synth_call:
        service.sync()
    clone_call.assert_called_once()
    synth_call.assert_not_called()
    with patch.object(service.client, "request", return_value={"data": {"audio": "https://audio.example.com/s.mp3"}}), \
         patch.object(service.client, "download_audio", return_value=b"ID3test"):
        service.synthesize({"voice_id": "test0011", "text": "晚安"})
    synth_call.assert_not_called()


def test_clone_credential_falls_back_to_speech_key_without_billing_key(tmp_path, monkeypatch):
    config = tmp_path / "voice.ini"
    config.write_text("[minimax]\napi_key=speech-key\nregion=cn\n", encoding="utf-8")
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    monkeypatch.delenv("MINIMAX_MUSIC_API_KEY", raising=False)
    settings = load_settings(str(config))
    assert settings.minimax_clone_api_key == "speech-key"
    assert settings.minimax_clone_region == "cn"
    assert not settings.minimax_music_api_key
    service = MiniMaxMusicService(replace(settings, minimax_storage_dir=str(tmp_path / "music")))
    assert service.client.key == "speech-key"


def _age_voice(service, days):
    """把台账里所有音色的激活时间往前挪，模拟接近 7 天到期。"""
    moment = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    def update(state):
        for voice in state["voices"].values():
            voice["created_time"] = moment
            voice["last_activated_at"] = moment
    service.store.update(update)


def test_keepalive_activates_due_voice(voice_service):
    create_voice(voice_service)
    _age_voice(voice_service, 6)
    with patch.object(voice_service.clone_client, "request", return_value={"data": {"audio": "https://a/x.mp3"}}) as call:
        result = voice_service.run_keepalive()
    assert result["attempted"] == 1
    assert result["results"][0]["ok"] is True
    payload = call.call_args.args[1]
    assert payload["voice_setting"]["voice_id"] == "YuexiTest001"
    assert payload["text"].startswith("现在是")
    state = voice_service.store.read()
    assert state["voices"]["YuexiTest001"]["status"] == "active"
    assert state["voices"]["YuexiTest001"]["keepalive_count"] == 1


def test_keepalive_skips_fresh_voice(voice_service):
    create_voice(voice_service)
    _age_voice(voice_service, 2)
    with patch.object(voice_service.clone_client, "request") as call:
        assert voice_service.run_keepalive()["attempted"] == 0
    call.assert_not_called()


def test_keepalive_respects_switch_and_voice_disable(voice_service):
    create_voice(voice_service)
    _age_voice(voice_service, 6)
    voice_service.update_keepalive({"enabled": False, "hour": 3, "minute": 17, "disabled_voices": []})
    with patch.object(voice_service.clone_client, "request") as call:
        assert voice_service.run_keepalive()["attempted"] == 0
    call.assert_not_called()
    voice_service.update_keepalive({"enabled": True, "hour": 4, "minute": 30, "disabled_voices": ["YuexiTest001"]})
    with patch.object(voice_service.clone_client, "request") as call:
        assert voice_service.run_keepalive()["attempted"] == 0
    call.assert_not_called()


def test_keepalive_failure_keeps_error_for_diagnostics(voice_service):
    create_voice(voice_service)
    _age_voice(voice_service, 6)
    with patch.object(voice_service.clone_client, "request", side_effect=VoiceError("无复刻权限", 502, 2038)):
        result = voice_service.run_keepalive()
    assert result["results"][0]["ok"] is False
    assert "2038" not in result["results"][0]["error"] and "无复刻权限" in result["results"][0]["error"]
    assert "无复刻权限" in voice_service.store.read()["voices"]["YuexiTest001"]["last_keepalive_error"]


def test_keepalive_status_reports_days_left(voice_service):
    create_voice(voice_service)
    _age_voice(voice_service, 3)
    status = voice_service.keepalive_status()
    assert status["enabled"] is True
    assert status["hour"] == 3 and status["minute"] == 17
    item = status["voices"][0]
    assert item["voice_id"] == "YuexiTest001"
    assert 2 <= item["days_left"] <= 4
    assert item["disabled"] is False


def test_synced_custom_voice_joins_keepalive(voice_service):
    # 在别处复刻的音色同步过来后也要纳入保活，否则 7 天后仍会被官方删除。
    cloud = {"system_voice": [{"voice_id": "sys-1", "voice_name": "系统音"}],
             "voice_cloning": [{"voice_id": "MyVoice001", "voice_name": "我的音色", "created_time": "2026-10-20"}],
             "voice_generation": []}
    with patch.object(voice_service.clone_client, "request", return_value=cloud):
        voice_service.sync()
    status = voice_service.keepalive_status()
    assert [voice["voice_id"] for voice in status["voices"]] == ["MyVoice001"]
    assert status["voices"][0]["days_left"] is not None
    _age_voice(voice_service, 6)
    with patch.object(voice_service.clone_client, "request", return_value={"data": {"audio": "https://a/x.mp3"}}) as call:
        assert voice_service.run_keepalive()["attempted"] == 1
    assert call.call_args.args[1]["voice_setting"]["voice_id"] == "MyVoice001"
    assert voice_service.store.read()["voices"]["MyVoice001"]["keepalive_count"] == 1


@pytest.mark.parametrize("payload", [
    {"enabled": "yes", "hour": 3, "minute": 17, "disabled_voices": []},
    {"enabled": True, "hour": 25, "minute": 17, "disabled_voices": []},
    {"enabled": True, "hour": 3, "minute": 60, "disabled_voices": []},
    {"enabled": True, "hour": 3, "minute": 17, "disabled_voices": "not-a-list"},
])
def test_invalid_keepalive_settings_are_rejected(voice_service, payload):
    with pytest.raises(VoiceError):
        voice_service.update_keepalive(payload)
