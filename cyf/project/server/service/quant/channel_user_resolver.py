"""channel → 绑定用户 反向查询。

私聊 p2p 虚拟 channel 的 config_json 已存 receive_id=open_id，反查 QuantFeishuUserBinding 拿到 username。
群聊 channel 通常没有 user 关联，返回 None（保持全量透传行为）。
"""

from __future__ import annotations

import json
from typing import Optional


def resolve_channel_user(channel_id: int) -> Optional[dict]:
    """从 channel 反查绑定用户。

    返回 {"channel_id", "channel_name", "username", "open_id", "chat_id"} 或 None。
    群聊无绑定 / binding 不存在 / channel 不存在 → 返回 None。
    """
    from quant.entities import QuantImChannel, QuantFeishuUserBinding

    try:
        record = QuantImChannel.get_by_id(channel_id)
    except Exception:
        return None

    try:
        config = json.loads(record.config_json or "{}") if record.config_json else {}
    except (ValueError, TypeError):
        config = {}

    receive_id = str(config.get("receive_id") or "").strip()
    receive_id_type = str(config.get("receive_id_type") or "").strip().lower()

    # 只有 receive_id_type=open_id 的私聊通道才能反查到用户
    if receive_id_type != "open_id" or not receive_id:
        return None

    binding = QuantFeishuUserBinding.get_or_none(
        QuantFeishuUserBinding.feishu_open_id == receive_id
    )
    if not binding:
        return None

    return {
        "channel_id": record.id,
        "channel_name": record.name,
        "username": binding.username,
        "open_id": receive_id,
        "chat_id": str(config.get("inbound_chat_id") or "").strip(),
    }
