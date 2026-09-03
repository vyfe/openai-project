"""im_delivery_service 单元测试 — 覆盖 markdown 卡片 schema + send_channel_content 路径分流。

防止后续重构把 msg_type='text' 当成默认（飞书 text 不渲染 markdown），或把卡片 schema 改飞书不认。
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from service.quant.im_delivery_service import (
    feishu_content_card,
    send_channel_content,
    send_feishu_card,
    send_feishu_text,
)


def _fake_client(message_id: str = "om_test_xxx") -> MagicMock:
    """构造假的飞书 client，im.v1.message.create 返回 code=0。"""
    client = MagicMock()
    response = MagicMock()
    response.code = 0
    response.msg = "success"
    response.data = MagicMock()
    response.data.message_id = message_id
    client.im.v1.message.create.return_value = response
    return client


CHANNEL = {
    "channel_id": 1,
    "channel_type": "feishu_app",
    "config": {"receive_id": "oc_test_chat_xxx", "receive_id_type": "chat_id"},
    "channel_target": "feishu:chat_id:oc_t...",
}


class TestFeishuContentCard:
    """feishu_content_card 构造的 JSON 必须能被飞书接受：wide_screen_mode + plain_text header + markdown elements。"""

    def test_basic_schema(self):
        payload = json.loads(feishu_content_card("测试报告", "# 标题\n\n- 条目 1\n- 条目 2"))
        assert payload["config"] == {"wide_screen_mode": True}
        assert payload["header"]["title"]["tag"] == "plain_text"
        assert payload["header"]["title"]["content"] == "测试报告"
        assert isinstance(payload["elements"], list) and len(payload["elements"]) == 1
        elem = payload["elements"][0]
        assert elem["tag"] == "markdown"
        assert "# 标题" in elem["content"]
        assert "- 条目 1" in elem["content"]

    def test_empty_title_falls_back_to_default(self):
        payload = json.loads(feishu_content_card("", "正文"))
        assert payload["header"]["title"]["content"] == "量化推送"

    def test_whitespace_only_title_falls_back_to_default(self):
        payload = json.loads(feishu_content_card("   ", "正文"))
        assert payload["header"]["title"]["content"] == "量化推送"

    def test_long_title_is_truncated_to_80_chars(self):
        long_title = "A" * 200
        payload = json.loads(feishu_content_card(long_title, "x"))
        assert len(payload["header"]["title"]["content"]) == 80

    def test_long_markdown_is_truncated_with_marker(self):
        long_md = "x" * 5000
        payload = json.loads(feishu_content_card("title", long_md))
        content = payload["elements"][0]["content"]
        assert len(content) <= 3800
        assert "已截断展示" in content

    def test_markdown_under_limit_passes_through(self):
        md = "x" * 1000
        payload = json.loads(feishu_content_card("title", md))
        assert payload["elements"][0]["content"] == md

    def test_ensure_ascii_false_preserves_chinese(self):
        payload = json.loads(feishu_content_card("量化日报", "中文内容"))
        assert payload["header"]["title"]["content"] == "量化日报"
        assert payload["elements"][0]["content"] == "中文内容"


class TestSendFeishuCard:
    """send_feishu_card 必须发 msg_type='interactive' + 卡片 content。"""

    def test_sends_interactive_msg_type(self):
        with patch(
            "service.quant.im_delivery_service.require_feishu_client",
            return_value=_fake_client(),
        ):
            result = send_feishu_card(CHANNEL, "测试报告", "# 标题\n\n正文")
        assert result["message_type"] == "interactive"
        # request_payload 应当走 msg_type='interactive'
        assert result["request_payload"]["msg_type"] == "interactive"
        # content 应当是 JSON 字符串，能解析成卡片 schema
        content_dict = json.loads(result["request_payload"]["content"])
        assert content_dict["header"]["title"]["content"] == "测试报告"
        assert content_dict["elements"][0]["tag"] == "markdown"

    def test_missing_receive_id_raises(self):
        bad_channel = {
            "channel_id": 1,
            "channel_type": "feishu_app",
            "config": {"receive_id_type": "chat_id"},  # 没有 receive_id
            "channel_target": "",
        }
        with pytest.raises(ValueError, match="缺少 receive_id"):
            send_feishu_card(bad_channel, "title", "body")

    def test_fake_client_gets_called_with_card_content(self):
        fake = _fake_client(message_id="om_abc_123")
        with patch(
            "service.quant.im_delivery_service.require_feishu_client",
            return_value=fake,
        ):
            send_feishu_card(CHANNEL, "T", "M")
        fake.im.v1.message.create.assert_called_once()
        result_payload = result = fake.im.v1.message.create.call_args[0][0]
        assert result_payload.request_body.msg_type == "interactive"
        body = json.loads(result_payload.request_body.content)
        assert body["elements"][0]["content"] == "M"


class TestSendFeishuText:
    """send_feishu_text 仍走 text msg_type（reply / 兼容路径）。"""

    def test_sends_text_msg_type(self):
        with patch(
            "service.quant.im_delivery_service.require_feishu_client",
            return_value=_fake_client(),
        ):
            result = send_feishu_text(CHANNEL, "纯文本消息")
        assert result["message_type"] == "text"
        assert result["request_payload"]["msg_type"] == "text"
        content_dict = json.loads(result["request_payload"]["content"])
        assert content_dict["text"] == "纯文本消息"

    def test_missing_receive_id_raises(self):
        bad_channel = {"channel_id": 1, "channel_type": "feishu_app", "config": {}, "channel_target": ""}
        with pytest.raises(ValueError, match="缺少 receive_id"):
            send_feishu_text(bad_channel, "x")


class TestSendChannelContent:
    """send_channel_content 是推送入口：默认走 interactive 卡片，传 message_type='text' 才走纯文本。"""

    def test_default_goes_interactive(self):
        with patch(
            "service.quant.im_delivery_service.require_feishu_client",
            return_value=_fake_client(),
        ) as fake_require:
            result = send_channel_content(CHANNEL, "# 标题\n\n正文", title="测试报告")
        assert result["message_type"] == "interactive"
        fake_require.assert_called_once()
        content_dict = json.loads(result["request_payload"]["content"])
        assert content_dict["header"]["title"]["content"] == "测试报告"
        # markdown 内容里的 # 标题直接由飞书 markdown 渲染，不会在 plain_text header 重复
        assert content_dict["elements"][0]["content"] == "# 标题\n\n正文"

    def test_explicit_text_message_type_keeps_text_path(self):
        with patch(
            "service.quant.im_delivery_service.require_feishu_client",
            return_value=_fake_client(),
        ):
            result = send_channel_content(CHANNEL, "纯文本", title="x", message_type="text")
        assert result["message_type"] == "text"

    def test_default_title_used_when_omitted(self):
        with patch(
            "service.quant.im_delivery_service.require_feishu_client",
            return_value=_fake_client(),
        ):
            result = send_channel_content(CHANNEL, "body")
        content_dict = json.loads(result["request_payload"]["content"])
        assert content_dict["header"]["title"]["content"] == "量化推送"