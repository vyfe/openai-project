from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from quant.entities import QuantImChannel
from service.quant.im_helpers import CHANNEL_FEISHU_APP, json_loads, mask_feishu_target, normalize_channel_type, normalize_mentions, to_bool


def normalize_feishu_config(config) -> dict:
    payload = json_loads(config, {}) or {}
    receive_id = str(
        payload.get("receive_id")
        or payload.get("chat_id")
        or payload.get("open_id")
        or payload.get("user_id")
        or ""
    ).strip()
    receive_id_type = str(payload.get("receive_id_type") or "").strip()
    if not receive_id_type:
        if receive_id.startswith("oc_"):
            receive_id_type = "chat_id"
        elif receive_id.startswith("ou_"):
            receive_id_type = "open_id"
        else:
            receive_id_type = "chat_id"
    if receive_id_type not in ("chat_id", "open_id", "user_id", "union_id", "email"):
        raise ValueError("飞书 receive_id_type 仅支持 chat_id/open_id/user_id/union_id/email")
    return {
        "receive_id": receive_id,
        "receive_id_type": receive_id_type,
        "reply_in_thread": to_bool(payload.get("reply_in_thread"), default=False),
        "inbound_chat_id": str(payload.get("inbound_chat_id") or (receive_id if receive_id_type == "chat_id" else "")).strip(),
    }


def normalize_channel_config(channel_type: str, config=None) -> dict:
    if channel_type == CHANNEL_FEISHU_APP:
        normalized = normalize_feishu_config(config)
        if not normalized.get("receive_id"):
            raise ValueError("飞书通道需要配置 receive_id")
        return normalized
    raise ValueError(f"不支持的 IM 通道类型: {channel_type}")


def list_im_channels(status: Optional[str] = None, channel_type: Optional[str] = None) -> list[dict]:
    query = QuantImChannel.select().order_by(QuantImChannel.id.desc())
    if status:
        query = query.where(QuantImChannel.status == status)
    if channel_type:
        query = query.where(QuantImChannel.channel_type == channel_type)
    return [item.to_dict() for item in query.iterator()]


def get_im_channel(channel_id: int) -> dict:
    return QuantImChannel.get_by_id(channel_id).to_dict()


def create_im_channel(
    *,
    name: str,
    channel_type: str = CHANNEL_FEISHU_APP,
    status: str = "active",
    mention_list=None,
    description: str = "",
    config=None,
) -> dict:
    if not str(name or "").strip():
        raise ValueError("name 不能为空")
    final_channel_type = normalize_channel_type(channel_type)
    final_config = normalize_channel_config(final_channel_type, config=config)
    record = QuantImChannel.create(
        name=str(name or "").strip(),
        channel_type=final_channel_type,
        status=str(status or "active").strip() or "active",
        config_json=json.dumps(final_config, ensure_ascii=False),
        mention_list_json=json.dumps(normalize_mentions(mention_list), ensure_ascii=False),
        description=str(description or "").strip(),
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    return record.to_dict()


def update_im_channel(channel_id: int, **updates) -> dict:
    record = QuantImChannel.get_by_id(channel_id)
    next_channel_type = normalize_channel_type(updates.get("channel_type", record.channel_type))
    next_config = json_loads(updates.get("config", record.config_json), {}) if "config" in updates else json_loads(record.config_json, {})
    if "name" in updates:
        record.name = str(updates["name"] or "").strip()
    if "channel_type" in updates:
        record.channel_type = next_channel_type
    if "config" in updates or "channel_type" in updates:
        record.config_json = json.dumps(normalize_channel_config(next_channel_type, config=next_config), ensure_ascii=False)
    if "status" in updates:
        record.status = str(updates["status"] or "active").strip() or "active"
    if "mention_list" in updates:
        record.mention_list_json = json.dumps(normalize_mentions(updates["mention_list"]), ensure_ascii=False)
    if "description" in updates:
        record.description = str(updates["description"] or "").strip()
    record.updated_at = datetime.now()
    record.save()
    return record.to_dict()


def delete_im_channel(channel_id: int) -> bool:
    record = QuantImChannel.get_by_id(channel_id)
    record.delete_instance()
    return True


def load_channel(channel_id: Optional[int] = None) -> dict:
    if not channel_id:
        raise ValueError("飞书通道需要指定 channel_id")
    channel = QuantImChannel.get_by_id(channel_id).to_dict()
    if channel["status"] != "active":
        raise ValueError("当前 IM 通道未启用")
    config = channel.get("config") or {}
    if channel["channel_type"] != CHANNEL_FEISHU_APP:
        raise ValueError("当前版本仅支持飞书通道")
    return {
        "channel_id": channel["id"],
        "channel_type": channel["channel_type"],
        "config": config,
        "mention_list": channel.get("mention_list", []),
        "channel_target": mask_feishu_target(config),
    }


def available_im_channel_options() -> list[dict]:
    return [{"id": item["id"], "name": item["name"], "channel_type": item["channel_type"], "status": item["status"]} for item in list_im_channels(status="active")]
