"""im_channel_service 集成测试 — 覆盖历史遗留字段 schema 不一致 bug。

历史教训：quant_im_channel 表有 webhook_url TEXT NOT NULL 列（来源不明，可能手工
ALTER 添加），但 Python QuantImChannel entity 没声明，导致 create_im_channel 100%
抛 NOT NULL constraint failed。本次测试断言：entity 修复后 create_im_channel 不传
webhook_url 也能成功，且 to_dict 把它返回。
"""
from __future__ import annotations

import pytest

from quant.entities import QuantImChannel
from service.quant.im_channel_service import create_im_channel, get_im_channel, update_im_channel


class TestCreateImChannelWebhookUrlRegression:
    """防止 entity/DB schema 不一致回归。"""

    def test_create_without_webhook_url_succeeds(self):
        """create_im_channel 不传 webhook_url 也能成功（entity 应有 default=''）。"""
        record = create_im_channel(
            name="regression-test-channel",
            config={"receive_id": "oc_test_xxx", "receive_id_type": "chat_id"},
        )
        try:
            assert record["name"] == "regression-test-channel"
            assert record["webhook_url"] == ""
            # 真实落库也能取出来
            stored = QuantImChannel.get_by_id(record["id"])
            assert stored.webhook_url == ""
        finally:
            # 清理（conftest 通常会清，但显式删避免名字冲突）
            QuantImChannel.delete().where(QuantImChannel.name == "regression-test-channel").execute()

    def test_to_dict_includes_webhook_url(self):
        """to_dict 返回 webhook_url 字段，让前端 / 上层 API 保持稳定。"""
        record = create_im_channel(
            name="to-dict-channel",
            config={"receive_id": "oc_test_yyy", "receive_id_type": "chat_id"},
        )
        try:
            assert "webhook_url" in record
            assert record["webhook_url"] == ""
            # 二次读取（get_im_channel 走 to_dict 路径）也保持一致
            refetched = get_im_channel(record["id"])
            assert "webhook_url" in refetched
            assert refetched["webhook_url"] == ""
        finally:
            QuantImChannel.delete().where(QuantImChannel.name == "to-dict-channel").execute()

    def test_update_preserves_webhook_url(self):
        """update_im_channel 不应误清 webhook_url（保持 '' 不变）。"""
        record = create_im_channel(
            name="update-channel",
            config={"receive_id": "oc_test_zzz", "receive_id_type": "chat_id"},
        )
        try:
            update_im_channel(record["id"], description="更新后描述")
            refetched = get_im_channel(record["id"])
            assert refetched["webhook_url"] == ""
            assert refetched["description"] == "更新后描述"
        finally:
            QuantImChannel.delete().where(QuantImChannel.name == "update-channel").execute()