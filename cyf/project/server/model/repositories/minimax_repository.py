"""复用平台 SQLite，保存音色台账、朗读记录和音乐创作结果。"""
import json
from datetime import datetime

from model.entities import MusicTrack, VoiceAccountState, VoiceReading


# ---------- 音色台账 ----------

def get_account_state(scope):
    row = VoiceAccountState.get_or_none(VoiceAccountState.scope == scope)
    return json.loads(row.state_json) if row else {
        "voices": {}, "cloud_voices": [], "default_voice_id": "", "last_sync": None,
    }


def save_account_state(scope, state):
    encoded = json.dumps(state, ensure_ascii=False)
    (VoiceAccountState.insert(scope=scope, state_json=encoded)
     .on_conflict(conflict_target=[VoiceAccountState.scope], update={VoiceAccountState.state_json: encoded})
     .execute())


# ---------- 朗读记录 ----------

def reading_dict(row, include_text=False):
    result = {name: getattr(row, name) for name in (
        "id", "title", "voice_id", "model", "speed", "volume", "pitch", "emotion", "status", "audio_url",
        "duration_seconds", "usage_characters", "usage_voice_count", "size", "error_message",
    )}
    result["created_at"] = row.created_at.isoformat() + "Z"
    result["url_expires_at"] = row.url_expires_at.isoformat() + "Z" if row.url_expires_at else None
    result["url_expired"] = bool(row.url_expires_at and row.url_expires_at <= datetime.utcnow())
    if include_text:
        result["text"] = row.source_text
    return result


def list_readings(scope):
    rows = VoiceReading.select().where(VoiceReading.scope == scope).order_by(VoiceReading.created_at.desc()).limit(200)
    return [reading_dict(row) for row in rows]


def get_reading(scope, audio_id):
    return VoiceReading.get_or_none((VoiceReading.scope == scope) & (VoiceReading.id == audio_id))


# ---------- 音乐创作 ----------

def track_dict(row, include_text=False):
    result = {name: getattr(row, name) for name in (
        "id", "title", "model", "instrumental", "lyrics_optimizer", "status", "audio_url",
        "duration_seconds", "size", "error_message",
    )}
    result["created_at"] = row.created_at.isoformat() + "Z"
    result["url_expires_at"] = row.url_expires_at.isoformat() + "Z" if row.url_expires_at else None
    result["url_expired"] = bool(row.url_expires_at and row.url_expires_at <= datetime.utcnow())
    result["has_audio"] = bool(row.audio_url or row.status == "ready")
    result["reference_duration"] = row.reference_duration
    result["cover_ready"] = bool(row.cover_feature_id)
    if include_text:
        result["prompt"] = row.prompt or ""
        result["lyrics"] = row.lyrics or ""
    return result


def list_tracks(scope):
    rows = MusicTrack.select().where(MusicTrack.scope == scope).order_by(MusicTrack.created_at.desc()).limit(200)
    return [track_dict(row) for row in rows]


def get_track(scope, track_id):
    return MusicTrack.get_or_none((MusicTrack.scope == scope) & (MusicTrack.id == track_id))


def remove_track(scope, track_id):
    return MusicTrack.delete().where((MusicTrack.scope == scope) & (MusicTrack.id == track_id)).execute()
