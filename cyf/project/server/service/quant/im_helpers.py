from __future__ import annotations

import json


CHANNEL_FEISHU_APP = "feishu_app"


def json_loads(value, default):
    if value in (None, ""):
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(str(value))
    except Exception:
        return default


def normalize_mentions(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value or "").strip()
    if not text:
        return []
    if text.startswith("["):
        parsed = json_loads(text, [])
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]
    return [item.strip() for item in text.split(",") if item.strip()]


def to_bool(value, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value in (None, ""):
        return default
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def truncate_text(content: str, limit: int = 9000) -> str:
    text = str(content or "").strip()
    if len(text) <= limit:
        return text
    return f"{text[:limit - 24]}\n\n内容过长，已截断展示。"


def truncate_markdown(content: str, limit: int = 3800) -> str:
    text = str(content or "").strip()
    if len(text) <= limit:
        return text
    return f"{text[:limit - 24]}\n\n> 内容过长，已截断展示。"


def mask_secret(text: str, keep: int = 6) -> str:
    value = str(text or "")
    if len(value) <= keep * 2:
        return value
    return f"{value[:keep]}...{value[-keep:]}"


def mask_feishu_target(config: dict) -> str:
    receive_id_type = str(config.get("receive_id_type") or "chat_id")
    receive_id = str(config.get("receive_id") or "")
    return f"feishu:{receive_id_type}:{mask_secret(receive_id)}" if receive_id else "feishu:app"


def normalize_channel_type(value: str) -> str:
    channel_type = str(value or CHANNEL_FEISHU_APP).strip() or CHANNEL_FEISHU_APP
    if channel_type != CHANNEL_FEISHU_APP:
        raise ValueError(f"不支持的 IM 通道类型: {channel_type}")
    return channel_type

