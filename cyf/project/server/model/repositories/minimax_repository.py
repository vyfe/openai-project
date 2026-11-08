"""复用平台 SQLite，保存音色台账、朗读记录和音乐创作结果。"""
import json
from datetime import datetime
from typing import Optional

from model.entities import MusicTrack, VoiceAccountState, VoiceAssetOwnership, VoiceReading


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


# ---------- 自定义音色归属 ----------

def claim_voice_ownership(scope: str, voice_id: str, owner_user_id: int) -> None:
    """登记自定义音色的归属；已存在则保持原归属。"""
    VoiceAssetOwnership.insert(
        scope=scope,
        voice_id=voice_id,
        owner_user_id=owner_user_id,
        created_at=datetime.now(),
    ).on_conflict_ignore().execute()


def owned_voice_ids(scope: str, owner_user_id: int) -> set:
    return {row.voice_id for row in VoiceAssetOwnership.select(VoiceAssetOwnership.voice_id).where(
        (VoiceAssetOwnership.scope == scope) & (VoiceAssetOwnership.owner_user_id == owner_user_id))}


def release_voice_ownership(scope: str, voice_id: str):
    VoiceAssetOwnership.delete().where((VoiceAssetOwnership.scope == scope) & (VoiceAssetOwnership.voice_id == voice_id)).execute()


def get_voice_owner(scope: str, voice_id: str) -> Optional[int]:
    row = VoiceAssetOwnership.get_or_none(
        (VoiceAssetOwnership.scope == scope) & (VoiceAssetOwnership.voice_id == voice_id)
    )
    return row.owner_user_id if row else None


def owns_voice(scope: str, voice_id: str, owner_user_id: Optional[int], is_admin: bool = False) -> bool:
    """系统音色共享；自定义音色仅本人与管理员可用。

    ``owner_user_id`` 为 ``None`` 表示系统作用域（内部调用 / 迁移脚本），不做限制。
    """
    if is_admin or owner_user_id is None:
        return True
    recorded_owner = get_voice_owner(scope, voice_id)
    if recorded_owner is None:
        # 未登记归属的历史音色默认仅管理员可操作。
        return False
    return int(recorded_owner) == int(owner_user_id)


# ---------- 朗读记录 ----------

def reading_dict(row, include_text=False):
    result = {name: getattr(row, name) for name in (
        "id", "title", "voice_id", "model", "speed", "volume", "pitch", "emotion", "status", "audio_url",
        "duration_seconds", "usage_characters", "usage_voice_count", "size", "error_message",
    )}
    result["has_audio"] = bool(row.audio_url or row.status == "ready")
    result["created_at"] = row.created_at.isoformat() + "Z"
    result["url_expires_at"] = row.url_expires_at.isoformat() + "Z" if row.url_expires_at else None
    result["url_expired"] = bool(row.url_expires_at and row.url_expires_at <= datetime.utcnow())
    if include_text:
        result["text"] = row.source_text
    return result


def _scope_owner(query, model, owner_user_id: Optional[int], is_admin: bool):
    """把查询收敛到本人记录；管理员可见同凭据下的全部记录。"""
    if is_admin:
        return query
    return query.where(model.owner_user_id == owner_user_id)


def list_readings(scope, owner_user_id: Optional[int] = None, is_admin: bool = False):
    query = VoiceReading.select().where(VoiceReading.scope == scope)
    query = _scope_owner(query, VoiceReading, owner_user_id, is_admin)
    rows = query.order_by(VoiceReading.created_at.desc()).limit(200)
    return [reading_dict(row) for row in rows]


def get_reading(scope, audio_id, owner_user_id: Optional[int] = None, is_admin: bool = False):
    query = VoiceReading.select().where((VoiceReading.scope == scope) & (VoiceReading.id == audio_id))
    query = _scope_owner(query, VoiceReading, owner_user_id, is_admin)
    return query.get_or_none()


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


def list_tracks(scope, owner_user_id: Optional[int] = None, is_admin: bool = False):
    query = MusicTrack.select().where(MusicTrack.scope == scope)
    query = _scope_owner(query, MusicTrack, owner_user_id, is_admin)
    rows = query.order_by(MusicTrack.created_at.desc()).limit(200)
    return [track_dict(row) for row in rows]


def get_track(scope, track_id, owner_user_id: Optional[int] = None, is_admin: bool = False):
    query = MusicTrack.select().where((MusicTrack.scope == scope) & (MusicTrack.id == track_id))
    query = _scope_owner(query, MusicTrack, owner_user_id, is_admin)
    return query.get_or_none()


def remove_track(scope, track_id, owner_user_id: Optional[int] = None, is_admin: bool = False):
    query = MusicTrack.delete().where((MusicTrack.scope == scope) & (MusicTrack.id == track_id))
    query = _scope_owner(query, MusicTrack, owner_user_id, is_admin)
    return query.execute()
