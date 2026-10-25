"""音色台账、云端管理和朗读文件；按 MiniMax 凭据隔离本地数据。"""
import os
import re
import secrets
from datetime import datetime, timedelta, timezone

from conf.runtime import runtime_state
from model.entities import VoiceReading
from model.repositories.minimax_repository import (
    get_account_state, get_reading, list_readings, reading_dict, save_account_state,
)
from service.minimax_audio import cache_audio
from service.minimax_client import (
    MODELS, MiniMaxClient, VoiceError, numeric, read_sample, require,
    text_value, validate_new_voice_id,
)
from service.minimax_store import MiniMaxStore

# 复刻音色 7 天内没有正式调用会被官方删除，保活在到期前补一次短文本合成。
KEEPALIVE_WINDOW_DAYS = 7
KEEPALIVE_LEAD_DAYS = 1
KEEPALIVE_DEFAULT_HOUR = 3
KEEPALIVE_DEFAULT_MINUTE = 17


def now():
    return datetime.now(timezone.utc).isoformat()


def keepalive_text(moment):
    """保活用的短文本：播报当前日期时间。"""
    return f"现在是{moment.year}年{moment.month}月{moment.day}日{moment.hour}时{moment.minute}分。"


def _parse_moment(value):
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        moment = datetime.fromisoformat(value.strip())
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def merged_voices(state):
    merged = {}
    for voice in state["cloud_voices"]:
        local = state["voices"].get(voice["voice_id"], {})
        merged[voice["voice_id"]] = {**voice, **local, "status": "active"}
    for voice_id, voice in state["voices"].items():
        if voice_id not in merged:
            merged[voice_id] = {**voice, "voice_id": voice_id}
    return sorted(merged.values(), key=lambda v: (v["voice_type"] == "system", v.get("alias", v["voice_id"]).lower()))


class MiniMaxVoiceService:
    def __init__(self, settings=None):
        self.settings = settings or runtime_state.settings
        # 语音合成与音色复刻可能用两把不同的密钥：Token Plan 只能合成，复刻走计费密钥。
        self.client = MiniMaxClient(self.settings)
        self.clone_client = MiniMaxClient(self.settings, api_key=self.settings.minimax_clone_api_key or None,
                                           region=self.settings.minimax_clone_region)
        # 音色台账必须与音色列表同源，否则复刻出来的音色在云端列表里对不上。
        self.store = MiniMaxStore(self.settings, api_key=self.settings.minimax_clone_api_key or None,
                                  region=self.settings.minimax_clone_region,
                                  state_loader=get_account_state, state_saver=save_account_state)

    def snapshot(self):
        state = self.store.read()
        return {
            "config": {
                "ready": self.client.ready, "region": self.client.region,
                "key_kind": self.settings.minimax_key_kind, "model": self.settings.minimax_model,
                "base_url": self.client.base_url, "timeout_seconds": self.client.timeout,
                "config_path": self.settings.conf_path, "storage_dir": str(self.store.folder.parent),
                "clone_ready": self.clone_client.ready, "clone_region": self.clone_client.region,
                "clone_base_url": self.clone_client.base_url,
                "clone_dedicated": self.settings.minimax_clone_api_key != self.settings.minimax_api_key,
            },
            "models": MODELS, "voices": merged_voices(state), "history": list_readings(self.store.scope),
            "default_voice_id": state["default_voice_id"], "last_sync": state["last_sync"],
        }

    def sync(self):
        result = self.clone_client.request("/v1/get_voice", {"voice_type": "all"})
        voices = []
        for field, kind in (("system_voice", "system"), ("voice_cloning", "voice_cloning"), ("voice_generation", "voice_generation")):
            for row in result.get(field) or []:
                if not isinstance(row.get("voice_id"), str) or not row["voice_id"]:
                    continue
                desc = row.get("description") or []
                voices.append({
                    "voice_id": row["voice_id"], "voice_type": kind,
                    "alias": row.get("voice_name") or row["voice_id"],
                    "description": " / ".join(map(str, desc)) if isinstance(desc, list) else str(desc),
                    "created_time": str(row.get("created_time", "")), "status": "active",
                })
        def update(state):
            state["cloud_voices"] = voices
            state["last_sync"] = now()
            for voice in voices:
                if voice["voice_id"] in state["voices"]:
                    state["voices"][voice["voice_id"]]["status"] = "active"
                elif voice["voice_type"] != "system":
                    # 云端已存在的自定义音色也要纳入保活，否则复刻在别处的音色 7 天后仍会被删除。
                    state["voices"][voice["voice_id"]] = {**voice, "status": "active"}
        self.store.update(update)
        return {"count": len(voices)}

    def clone(self, data, files):
        voice_id = text_value(data, "voice_id", 256)
        validate_new_voice_id(voice_id)
        alias = text_value(data, "alias", 80)
        require(data.get("consent") is True, "请确认录音属于你本人，或已取得声音本人的授权。")
        sample = read_sample(files.get("sample"), data.get("sample_duration"))
        prompt = read_sample(files["prompt"], data.get("prompt_duration"), True) if files.get("prompt") else None
        prompt_text = text_value(data, "prompt_text", 200, bool(prompt))
        require(not prompt_text or prompt is not None, "请上传与示例文本对应的短音频。")
        for flag in ("need_noise_reduction", "need_volume_normalization"):
            require(isinstance(data.get(flag, False), bool), "降噪与音量归一化必须是开关值。")
        require(not any(v["voice_id"] == voice_id for v in merged_voices(self.store.read())), "音色 ID 已有记录，请使用新 ID。")
        payload = {"file_id": self.clone_client.upload(sample, "voice_clone"), "voice_id": voice_id}
        for flag in ("need_noise_reduction", "need_volume_normalization"):
            payload[flag] = data.get(flag, False)
        if prompt:
            payload["clone_prompt"] = {"prompt_audio": self.clone_client.upload(prompt, "prompt_audio"), "prompt_text": prompt_text}
        record = {"voice_id": voice_id, "alias": alias, "voice_type": "voice_cloning", "description": "由录音复刻",
                  "created_time": now(), "status": "unknown"}
        self.store.update(lambda s: s["voices"].__setitem__(voice_id, record))
        try:
            result = self.clone_client.request("/v1/voice_clone", payload)
            sensitive = result.get("input_sensitive")
            if (isinstance(sensitive, dict) and sensitive.get("type", 0) != 0) or sensitive is True:
                raise VoiceError("录音未通过 MiniMax 检查，请更换录音。", 502)
        except VoiceError as exc:
            if not exc.uncertain:
                self.store.update(lambda s: s["voices"].pop(voice_id, None))
            raise
        self.store.update(lambda s: s["voices"][voice_id].update(status="pending"))
        return {"voice_id": voice_id}

    def preference(self, data):
        voice_id = text_value(data, "voice_id", 256)
        alias = text_value(data, "alias", 80, False)
        require(isinstance(data.get("make_default", False), bool), "make_default 必须是开关值。")
        def update(state):
            known = next((v for v in merged_voices(state) if v["voice_id"] == voice_id), None)
            require(known is not None, "音色记录不存在，请先同步云端音色。")
            if alias:
                state["voices"][voice_id] = {**known, "alias": alias}
            if data.get("make_default"):
                state["default_voice_id"] = voice_id
        self.store.update(update)

    def delete(self, data):
        voice_id = text_value(data, "voice_id", 256)
        require(data.get("confirmation") == voice_id, "请输入完整音色 ID 确认删除。")
        known = next((v for v in merged_voices(self.store.read()) if v["voice_id"] == voice_id), None)
        require(known is not None, "音色记录不存在，请先同步云端音色。")
        require(known["voice_type"] in ("voice_cloning", "voice_generation"), "系统音色不能删除。")
        self.clone_client.request("/v1/delete_voice", {"voice_id": voice_id, "voice_type": known["voice_type"]})
        def update(state):
            state["voices"].pop(voice_id, None)
            state["cloud_voices"] = [v for v in state["cloud_voices"] if v["voice_id"] != voice_id]
            if state["default_voice_id"] == voice_id:
                state["default_voice_id"] = ""
        self.store.update(update)

    def _synthesis_client(self, voice_id):
        """复刻音色首次使用要一次性付“音色费用”，这笔钱只走账户余额。

        订阅密钥（如 Token Plan）的额度不覆盖这笔费用，余额为 0 时官方返回 1008，
        因此尚未激活的自定义音色先用计费凭据合成；系统音色和已激活音色照常用订阅凭据。
        """
        voice = self.store.read()["voices"].get(voice_id, {})
        if voice.get("voice_type") in ("voice_cloning", "voice_generation") and voice.get("status") != "active":
            return self.clone_client
        return self.client

    def synthesize(self, data):
        voice_id = text_value(data, "voice_id", 256)
        text = text_value(data, "text", 9999)
        title = text_value(data, "title", 100, False) or "语音合成"
        model = data.get("model", self.settings.minimax_model)
        require(model in MODELS, "请选择支持的语音模型。")
        speed = numeric(data.get("speed", 0.9), 0.5, 2, "语速")
        volume = numeric(data.get("volume", 1), 0.1, 10, "音量")
        pitch = numeric(data.get("pitch", 0), -12, 12, "音调", True)
        emotion = data.get("emotion", "")
        require(emotion in ("", "calm", "happy", "sad"), "情绪选项无效。")
        voice_setting = {"voice_id": voice_id, "speed": speed, "vol": volume, "pitch": pitch}
        if emotion:
            voice_setting["emotion"] = emotion
        audio_id = datetime.now().strftime("%Y%m%d-%H%M%S-") + secrets.token_hex(4)
        record = VoiceReading.create(id=audio_id, scope=self.store.scope, title=title, source_text=text,
            voice_id=voice_id, model=model, speed=speed, volume=volume, pitch=pitch, emotion=emotion)
        payload = {
            "model": model, "text": text, "stream": False, "output_format": "url", "language_boost": "Chinese",
            "voice_setting": voice_setting,
            "audio_setting": {"sample_rate": 32000, "bitrate": 128000, "format": "mp3", "channel": 1},
        }
        client = self._synthesis_client(voice_id)
        try:
            result = client.request("/v1/t2a_v2", payload)
        except VoiceError as exc:
            # 1008 是明确失败（未产生音频、未计费），换计费凭据重试一次是安全的。
            if exc.code != 1008 or client is self.clone_client:
                record.status = "unknown" if exc.uncertain else "failed"
                record.error_message = str(exc)
                record.save()
                raise
            result = self.clone_client.request("/v1/t2a_v2", payload)
        audio_url = (result.get("data") or {}).get("audio")
        if not isinstance(audio_url, str) or not audio_url.startswith("https://"):
            record.status = "unknown"
            record.error_message = "云端未返回有效的 HTTPS 音频链接，可能已计费，请先检查云端记录。"
            record.save()
            raise VoiceError(record.error_message, 502, uncertain=True)
        extra = result.get("extra_info") or {}
        duration = extra.get("audio_length")
        record.audio_url = audio_url
        record.url_expires_at = datetime.utcnow() + timedelta(hours=24)
        record.duration_seconds = duration / 1000 if isinstance(duration, (int, float)) else None
        record.usage_characters = extra.get("usage_characters")
        record.usage_voice_count = extra.get("usage_voice_count", 0)
        record.status = "remote_ready"
        record.save()  # 先保存临时链接，随后下载失败也不丢失生成结果。
        def update(state):
            if voice_id in state["voices"]:
                state["voices"][voice_id]["status"] = "active"
                state["voices"][voice_id]["last_activated_at"] = now()
        self.store.update(update)
        try:
            self.cache_audio(record)
        except (VoiceError, OSError):
            record.error_message = "云端音频已生成，链接和正文已保存；本地备份未完成，可从记录重试下载。"
            record.save()
        return reading_dict(record)

    def cache_audio(self, record):
        cache_audio(self.store, self.client, record, "audio")

    def audio_path(self, audio_id, ext):
        require(ext in ("mp3", "txt") and re.fullmatch(r"[0-9]{8}-[0-9]{6}-[a-f0-9]{8}", audio_id), "文件标识无效。")
        row = get_reading(self.store.scope, audio_id)
        require(row is not None, "文件不存在于当前密钥的朗读记录。")
        path = self.store.folder / "audio" / (audio_id + "." + ext)
        if ext == "txt":
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(row.source_text)
        elif not path.is_file():
            with self.store.locked("operation", blocking=False):
                self.cache_audio(row)
        require(path.is_file(), "本地文件已不存在。")
        return path

    def reading(self, audio_id):
        row = get_reading(self.store.scope, audio_id)
        require(row is not None, "朗读记录不存在。")
        return reading_dict(row, include_text=True)

    # ---------- 音色保活 ----------

    def _deadline(self, voice, moment):
        """音色保活截止时间：最后一次正式调用 + 7 天。"""
        anchor = _parse_moment(voice.get("last_activated_at")) or _parse_moment(voice.get("created_time"))
        return anchor + timedelta(days=KEEPALIVE_WINDOW_DAYS) if anchor else None

    def keepalive_status(self):
        state = self.store.read()
        config = state.get("keepalive") or {}
        moment = datetime.now(timezone.utc)
        disabled = set(config.get("disabled_voices") or [])
        items = []
        for voice_id, voice in state["voices"].items():
            if voice.get("voice_type") == "system":
                continue
            deadline = self._deadline(voice, moment)
            items.append({
                "voice_id": voice_id,
                "deadline": deadline.isoformat() if deadline else None,
                "days_left": (deadline - moment).days if deadline else None,
                "disabled": voice_id in disabled,
                "activated_at": voice.get("last_activated_at"),
                "keepalive_count": voice.get("keepalive_count", 0),
            })
        return {
            "enabled": config.get("enabled", True),
            "hour": config.get("hour", KEEPALIVE_DEFAULT_HOUR),
            "minute": config.get("minute", KEEPALIVE_DEFAULT_MINUTE),
            "voices": items,
        }

    def update_keepalive(self, data):
        enabled = data.get("enabled")
        require(isinstance(enabled, bool), "保活开关必须是布尔值。")
        hour = numeric(data.get("hour", KEEPALIVE_DEFAULT_HOUR), 0, 23, "执行小时", True)
        minute = numeric(data.get("minute", KEEPALIVE_DEFAULT_MINUTE), 0, 59, "执行分钟", True)
        disabled = data.get("disabled_voices", [])
        require(isinstance(disabled, list) and all(isinstance(item, str) for item in disabled),
                "禁用列表必须是字符串数组。")
        def update(state):
            state["keepalive"] = {"enabled": enabled, "hour": hour, "minute": minute,
                                  "disabled_voices": sorted(set(disabled))}
        self.store.update(update)

    def keepalive_due(self, moment=None):
        moment = moment or datetime.now(timezone.utc)
        state = self.store.read()
        config = state.get("keepalive") or {}
        if not config.get("enabled", True):
            return []
        disabled = set(config.get("disabled_voices") or [])
        due = []
        for voice_id, voice in state["voices"].items():
            if voice_id in disabled or voice.get("voice_type") == "system":
                continue
            deadline = self._deadline(voice, moment)
            if deadline and deadline - moment <= timedelta(days=KEEPALIVE_LEAD_DAYS):
                due.append(voice_id)
        return due

    def run_keepalive(self, moment=None):
        """为到期音色补一次短文本合成；不落本地音频，只刷新激活时间。"""
        moment = moment or datetime.now(timezone.utc)
        text = keepalive_text(moment)
        results = []
        for voice_id in self.keepalive_due(moment):
            try:
                # 用音色所属账号的凭据调用，确保一定调得到该音色。
                self.clone_client.request("/v1/t2a_v2", {
                    "model": self.settings.minimax_model, "text": text, "stream": False, "output_format": "url",
                    "language_boost": "Chinese",
                    "voice_setting": {"voice_id": voice_id, "speed": 0.9, "vol": 1, "pitch": 0},
                    "audio_setting": {"sample_rate": 32000, "bitrate": 128000, "format": "mp3", "channel": 1},
                })
                self._mark_activated(voice_id, moment, keepalive=True)
                results.append({"voice_id": voice_id, "ok": True})
            except VoiceError as exc:
                self._mark_keepalive_error(voice_id, str(exc))
                results.append({"voice_id": voice_id, "ok": False, "error": str(exc)})
        return {"attempted": len(results), "results": results}

    def _mark_activated(self, voice_id, moment, keepalive=False):
        def update(state):
            voice = state["voices"].get(voice_id)
            if voice is None:
                return
            voice["status"] = "active"
            voice["last_activated_at"] = moment.isoformat()
            if keepalive:
                voice["keepalive_count"] = voice.get("keepalive_count", 0) + 1
                voice["last_keepalive_at"] = moment.isoformat()
        self.store.update(update)

    def _mark_keepalive_error(self, voice_id, message):
        def update(state):
            voice = state["voices"].get(voice_id)
            if voice is not None:
                voice["last_keepalive_error"] = message[:500]
        self.store.update(update)

    def profile(self):
        state = self.store.read()
        require(bool(state["default_voice_id"]), "请先在音色库设置默认音色。")
        return {"provider": "minimax", "region": self.client.region, "voice_id": state["default_voice_id"],
                "model": self.settings.minimax_model, "language_boost": "Chinese", "speed": 0.9, "volume": 1, "pitch": 0}
