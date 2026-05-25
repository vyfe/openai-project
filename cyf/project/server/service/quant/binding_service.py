"""飞书用户 ↔ 慧聊用户绑定服务"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from model.entities import User
from quant.entities import QuantFeishuUserBinding


def bind_user(feishu_open_id: str, username: str, password: str) -> dict:
    """绑定飞书用户到慧聊用户。先验证慧聊用户名密码，再写入绑定。"""
    if not feishu_open_id or not username:
        raise ValueError("feishu_open_id 和 username 不能为空")

    user = User.get_or_none(User.username == username, User.is_active == True)
    if not user:
        raise ValueError(f"慧聊用户不存在: {username}")
    if not user.verify_password(password):
        raise ValueError("密码错误")

    now = datetime.now()
    binding, created = QuantFeishuUserBinding.get_or_create(
        feishu_open_id=feishu_open_id,
        defaults={"username": username, "bound_at": now, "updated_at": now},
    )
    if not created:
        # 更新已有绑定
        binding.username = username
        binding.updated_at = now
        binding.save()

    return binding.to_dict()


def unbind_user(feishu_open_id: str) -> bool:
    """解绑飞书用户"""
    binding = QuantFeishuUserBinding.get_or_none(
        QuantFeishuUserBinding.feishu_open_id == feishu_open_id
    )
    if binding:
        binding.delete_instance()
        return True
    return False


def get_binding(feishu_open_id: str) -> Optional[dict]:
    """查询绑定关系"""
    binding = QuantFeishuUserBinding.get_or_none(
        QuantFeishuUserBinding.feishu_open_id == feishu_open_id
    )
    return binding.to_dict() if binding else None


def get_username_by_feishu(feishu_open_id: str) -> Optional[str]:
    """通过飞书 open_id 获取慧聊用户名，无绑定时返回 None"""
    binding = QuantFeishuUserBinding.get_or_none(
        QuantFeishuUserBinding.feishu_open_id == feishu_open_id
    )
    return binding.username if binding else None


def get_feishu_id_by_username(username: str) -> Optional[str]:
    """通过慧聊用户名获取飞书 open_id"""
    binding = QuantFeishuUserBinding.get_or_none(
        QuantFeishuUserBinding.username == username
    )
    return binding.feishu_open_id if binding else None


def list_all_bindings() -> list[dict]:
    """列出所有绑定关系（管理用）"""
    return [b.to_dict() for b in QuantFeishuUserBinding.select().iterator()]
