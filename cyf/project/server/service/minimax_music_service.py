"""音乐创作：按 MiniMax 凭据隔离保存创作参数、生成结果和本地音频。"""
import base64
import os
import re
import secrets
from datetime import datetime, timedelta

from conf.runtime import runtime_state
from model.entities import MusicTrack
from model.repositories.minimax_repository import (
    get_track, list_tracks, remove_track, track_dict,
)
from service.minimax_audio import cache_audio
from service.minimax_client import (
    COVER_MODEL, MUSIC_MODELS, MiniMaxClient, VoiceError, decode_music_audio,
    read_cover_audio, require, text_value,
)
from service.minimax_store import MiniMaxStore

MAX_PROMPT = 2000
MAX_LYRICS = 3500
COVER_PROMPT_RANGE = (10, 300)
COVER_LYRICS_RANGE = (10, 1000)
TRACK_ID_PATTERN = re.compile(r"[0-9]{8}-[0-9]{6}-[a-f0-9]{8}")


def _new_track_id():
    return datetime.now().strftime("%Y%m%d-%H%M%S-") + secrets.token_hex(4)


class MiniMaxMusicService:
    def __init__(self, settings=None):
        self.settings = settings or runtime_state.settings
        # 音乐可使用独立计费密钥；未配置时沿用语音凭据。
        music_key = self.settings.minimax_music_api_key or None
        self.client = MiniMaxClient(self.settings, api_key=music_key, region=self.settings.minimax_music_region,
                                    timeout=self.settings.minimax_music_timeout_seconds)
        self.store = MiniMaxStore(self.settings, api_key=music_key, region=self.settings.minimax_music_region)

    def snapshot(self, owner_user_id=None, is_admin: bool = False):
        """音乐台账快照；普通用户不下发配置路径、密钥种类与内部 Host。"""
        if is_admin:
            config = {
                "ready": self.client.ready, "region": self.client.region,
                "key_kind": self.settings.minimax_music_key_kind, "model": self.settings.minimax_music_model,
                "cover_model": COVER_MODEL,
                "base_url": self.client.base_url, "timeout_seconds": self.client.timeout,
                "config_path": self.settings.conf_path, "storage_dir": str(self.store.folder.parent),
                "dedicated_key": bool(self.settings.minimax_music_api_key),
            }
        else:
            config = {
                "ready": self.client.ready, "model": self.settings.minimax_music_model,
                "cover_model": COVER_MODEL,
            }
        return {
            "config": config,
            "models": list(MUSIC_MODELS),
            "tracks": list_tracks(self.store.scope, owner_user_id=owner_user_id, is_admin=is_admin),
        }

    def generate(self, data, owner_user_id=None):
        model = data.get("model") or self.settings.minimax_music_model
        require(model in MUSIC_MODELS, "请选择支持的音乐模型。")
        prompt = text_value(data, "prompt", MAX_PROMPT, False)
        lyrics = text_value(data, "lyrics", MAX_LYRICS, False)
        instrumental = data.get("instrumental", False)
        require(isinstance(instrumental, bool), "纯音乐开关必须是布尔值。")
        optimizer = data.get("lyrics_optimizer", False)
        require(isinstance(optimizer, bool), "自动写词开关必须是布尔值。")
        require(bool(prompt) or not instrumental, "纯音乐也需要填写风格描述。")
        require(bool(lyrics) or optimizer or instrumental, "带人声的作品需要填写歌词，或开启自动写词。")
        title = text_value(data, "title", 100, False) or (prompt[:24] if prompt else "未命名作品")

        record = MusicTrack.create(id=_new_track_id(), scope=self.store.scope, owner_user_id=owner_user_id,
                                   title=title, prompt=prompt,
                                   lyrics=lyrics, model=model, instrumental=instrumental,
                                   lyrics_optimizer=optimizer)
        payload = {"model": model, "stream": False, "output_format": "url",
                   "is_instrumental": instrumental, "lyrics_optimizer": optimizer,
                   "audio_setting": {"sample_rate": 44100, "bitrate": 256000, "format": "mp3"}}
        if prompt:
            payload["prompt"] = prompt
        if lyrics:
            payload["lyrics"] = lyrics
        try:
            result = self.client.request("/v1/music_generation", payload)
        except VoiceError as exc:
            record.status = "unknown" if exc.uncertain else "failed"
            record.error_message = str(exc)
            record.save()
            raise
        return self._store_result(record, result)

    def preprocess_cover(self, data, files, owner_user_id=None):
        """上传参考音频换取翻唱特征 ID 与 ASR 提取的歌词。"""
        title = text_value(data, "title", 100, False) or "参考翻唱"
        content = read_cover_audio(files.get("audio"), data.get("audio_duration"))
        record = MusicTrack.create(id=_new_track_id(), scope=self.store.scope, owner_user_id=owner_user_id,
                                   title=title, prompt="",
                                   lyrics="", model=COVER_MODEL)
        try:
            result = self.client.request("/v1/music_cover_preprocess", {
                "model": COVER_MODEL, "audio_base64": base64.b64encode(content).decode("ascii"),
            })
        except VoiceError as exc:
            record.status = "unknown" if exc.uncertain else "failed"
            record.error_message = str(exc)
            record.save()
            raise
        feature_id = result.get("cover_feature_id")
        require(isinstance(feature_id, str) and feature_id.strip(),
                "云端未返回翻唱特征 ID，请检查参考音频后重试。")
        duration = result.get("audio_duration")
        record.cover_feature_id = feature_id.strip()
        record.reference_duration = duration if isinstance(duration, (int, float)) else None
        record.lyrics = str(result.get("formatted_lyrics") or "")
        record.status = "cover_ready"
        record.save()
        return track_dict(record, include_text=True)

    def generate_cover(self, data, owner_user_id=None, is_admin: bool = False):
        track_id = text_value(data, "id", 64)
        require(TRACK_ID_PATTERN.fullmatch(track_id), "文件标识无效。")
        record = get_track(self.store.scope, track_id, owner_user_id=owner_user_id, is_admin=is_admin)
        if record is None:
            raise VoiceError("翻唱记录不存在。", 404)
        require(record.cover_feature_id, "该记录没有可用的翻唱特征，请重新上传参考音频。")
        prompt = text_value(data, "prompt", COVER_PROMPT_RANGE[1])
        require(len(prompt) >= COVER_PROMPT_RANGE[0],
                f"目标曲风描述需 {COVER_PROMPT_RANGE[0]}–{COVER_PROMPT_RANGE[1]} 个字符。")
        lyrics = text_value(data, "lyrics", COVER_LYRICS_RANGE[1], False)
        require(not lyrics or len(lyrics) >= COVER_LYRICS_RANGE[0],
                f"歌词需 {COVER_LYRICS_RANGE[0]}–{COVER_LYRICS_RANGE[1]} 个字符。")
        title = text_value(data, "title", 100, False) or record.title
        record.title, record.prompt, record.lyrics = title, prompt, lyrics
        record.status = "generating"
        record.error_message = None
        record.save()
        payload = {"model": COVER_MODEL, "stream": False, "output_format": "url",
                   "cover_feature_id": record.cover_feature_id, "prompt": prompt,
                   "audio_setting": {"sample_rate": 44100, "bitrate": 256000, "format": "mp3"}}
        if lyrics:
            payload["lyrics"] = lyrics
        try:
            result = self.client.request("/v1/music_generation", payload)
        except VoiceError as exc:
            record.status = "unknown" if exc.uncertain else "failed"
            record.error_message = str(exc)
            record.save()
            raise
        return self._store_result(record, result)

    def _store_result(self, record, result):
        """落地云端返回的音频：url 走临时链接，hex 直接解码落盘。"""
        decoded = decode_music_audio((result.get("data") or {}).get("audio"))
        if not decoded:
            record.status = "unknown"
            record.error_message = "云端未返回可用的音频内容，可能仍在生成，请稍后在记录中查看。"
            record.save()
            raise VoiceError(record.error_message, 502, uncertain=True)
        kind, content = decoded
        extra = result.get("extra_info") or {}
        duration = extra.get("music_duration")
        if kind == "url":
            record.audio_url = content
            record.url_expires_at = datetime.utcnow() + timedelta(hours=24)
        record.duration_seconds = duration / 1000 if isinstance(duration, (int, float)) else None
        record.status = "remote_ready"
        record.save()  # 先保存临时链接，随后下载失败也不丢失生成结果。
        try:
            self.cache_audio(record, content if kind == "hex" else None)
        except (VoiceError, OSError):
            record.error_message = "云端音频已生成，链接和创作参数已保存；本地备份未完成，可从记录重试下载。"
            record.save()
        return track_dict(record)

    def cache_audio(self, record, inline=None):
        cache_audio(self.store, self.client, record, "music", inline)

    def audio_path(self, track_id, ext, owner_user_id=None, is_admin: bool = False):
        require(ext in ("mp3", "txt") and TRACK_ID_PATTERN.fullmatch(track_id), "文件标识无效。")
        row = get_track(self.store.scope, track_id, owner_user_id=owner_user_id, is_admin=is_admin)
        if row is None:
            raise VoiceError("文件不存在于当前密钥的音乐记录。", 404)
        folder = self.store.folder / "music"
        path = folder / (track_id + "." + ext)
        if ext == "txt":
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write("风格描述\n" + (row.prompt or "") + "\n\n歌词\n" + (row.lyrics or "") + "\n")
        elif not path.is_file():
            with self.store.locked("operation", blocking=False):
                self.cache_audio(row)
        require(path.is_file(), "本地文件已不存在。")
        return path

    def track(self, track_id, owner_user_id=None, is_admin: bool = False):
        row = get_track(self.store.scope, track_id, owner_user_id=owner_user_id, is_admin=is_admin)
        if row is None:
            raise VoiceError("音乐记录不存在。", 404)
        return track_dict(row, include_text=True)

    def delete(self, track_id, owner_user_id=None, is_admin: bool = False):
        require(TRACK_ID_PATTERN.fullmatch(track_id), "文件标识无效。")
        row = get_track(self.store.scope, track_id, owner_user_id=owner_user_id, is_admin=is_admin)
        if row is None:
            raise VoiceError("音乐记录不存在。", 404)
        remove_track(self.store.scope, track_id, owner_user_id=owner_user_id, is_admin=is_admin)
        path = self.store.folder / "music" / (track_id + ".mp3")
        if path.is_file():
            path.unlink()
