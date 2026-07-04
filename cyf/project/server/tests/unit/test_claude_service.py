"""Claude SDK 集成测试。

覆盖：
- is_claude_model: model_grp 路由判断
- get_model_grp_from_cache: 模型分组查询
- run_claude_chat_completion: mock Claude API 非流式调用
- stream_claude_chat: mock Claude API 流式调用
"""

from unittest.mock import MagicMock, patch

import pytest


# ============================================================================
# is_claude_model / get_model_grp_from_cache
# ============================================================================


class TestIsClaudeModel:
    def test_claude_group_returns_true(self):
        with patch("service.host_service.get_model_grp_from_cache", return_value="claude"):
            from service.host_service import is_claude_model

            assert is_claude_model("claude-sonnet-4-6") is True

    def test_gpt_group_returns_false(self):
        with patch("service.host_service.get_model_grp_from_cache", return_value="gpt"):
            from service.host_service import is_claude_model

            assert is_claude_model("gpt-4o") is False

    def test_empty_group_returns_false(self):
        with patch("service.host_service.get_model_grp_from_cache", return_value=""):
            from service.host_service import is_claude_model

            assert is_claude_model("unknown-model") is False

    def test_none_group_returns_false(self):
        with patch("service.host_service.get_model_grp_from_cache", return_value="gpt"):
            from service.host_service import is_claude_model

            assert is_claude_model("deepseek-v4") is False


class TestGetModelGrpFromCache:
    def test_returns_model_grp(self):
        with patch("service.host_service.runtime_state") as mock_rs:
            mock_rs.model_cache = {
                "models": [
                    {"id": "claude-sonnet-4-6", "model_grp": "claude"},
                    {"id": "gpt-4o", "model_grp": "gpt"},
                ]
            }
            from service.host_service import get_model_grp_from_cache

            assert get_model_grp_from_cache("claude-sonnet-4-6") == "claude"
            assert get_model_grp_from_cache("gpt-4o") == "gpt"

    def test_unknown_model_returns_empty(self):
        with patch("service.host_service.runtime_state") as mock_rs:
            mock_rs.model_cache = {"models": []}
            from service.host_service import get_model_grp_from_cache

            assert get_model_grp_from_cache("unknown") == ""

    def test_empty_cache_returns_empty(self):
        with patch("service.host_service.runtime_state") as mock_rs:
            mock_rs.model_cache = {}
            from service.host_service import get_model_grp_from_cache

            assert get_model_grp_from_cache("claude-sonnet") == ""

    def test_case_insensitive_match(self):
        with patch("service.host_service.runtime_state") as mock_rs:
            mock_rs.model_cache = {
                "models": [{"id": "Claude-Sonnet-4-6", "model_grp": "claude"}]
            }
            from service.host_service import get_model_grp_from_cache

            assert get_model_grp_from_cache("claude-sonnet-4-6") == "claude"


# ============================================================================
# run_claude_chat_completion — mock Claude API
# ============================================================================


class TestRunClaudeChatCompletion:
    def test_normal_response(self):
        from service.claude_service import run_claude_chat_completion

        mock_client = MagicMock()
        mock_content_block = MagicMock()
        mock_content_block.type = "text"
        mock_content_block.text = "Hello from Claude"
        mock_usage = MagicMock()
        mock_usage.input_tokens = 10
        mock_usage.output_tokens = 20
        mock_result = MagicMock()
        mock_result.content = [mock_content_block]
        mock_result.usage = mock_usage
        mock_result.stop_reason = "end_turn"
        mock_result.model_dump.return_value = {"content": "mock"}
        mock_client.messages.create.return_value = mock_result

        dialogvo = [{"role": "user", "content": "Hello"}]
        result = run_claude_chat_completion(mock_client, "claude-sonnet-4-6", dialogvo)

        assert result["role"] == "assistant"
        assert result["content"] == "Hello from Claude"
        assert result["finish_reason"] == "end_turn"
        assert result["usage"]["total_tokens"] == 30
        assert result["usage"]["input_tokens"] == 10
        assert result["usage"]["output_tokens"] == 20
        assert "parts" in result

    def test_with_system_prompt(self):
        from service.claude_service import run_claude_chat_completion

        mock_client = MagicMock()
        mock_content_block = MagicMock()
        mock_content_block.type = "text"
        mock_content_block.text = "I am helpful"
        mock_usage = MagicMock()
        mock_usage.input_tokens = 5
        mock_usage.output_tokens = 10
        mock_result = MagicMock()
        mock_result.content = [mock_content_block]
        mock_result.usage = mock_usage
        mock_result.stop_reason = "end_turn"
        mock_result.model_dump.return_value = {"content": "mock"}
        mock_client.messages.create.return_value = mock_result

        dialogvo = [
            {"role": "system", "content": "Be helpful"},
            {"role": "user", "content": "Hello"},
        ]
        result = run_claude_chat_completion(mock_client, "claude-sonnet-4-6", dialogvo)

        # 验证 system 被提取为单独参数
        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert call_kwargs["system"] == "Be helpful"
        # 验证 messages 中不再有 system 角色
        assert len(call_kwargs["messages"]) == 1
        assert call_kwargs["messages"][0]["role"] == "user"

    def test_multiple_text_blocks_concatenated(self):
        from service.claude_service import run_claude_chat_completion

        mock_client = MagicMock()
        block1 = MagicMock()
        block1.type = "text"
        block1.text = "Part 1 "
        block2 = MagicMock()
        block2.type = "text"
        block2.text = "Part 2"
        mock_usage = MagicMock()
        mock_usage.input_tokens = 5
        mock_usage.output_tokens = 10
        mock_result = MagicMock()
        mock_result.content = [block1, block2]
        mock_result.usage = mock_usage
        mock_result.stop_reason = "end_turn"
        mock_result.model_dump.return_value = {"content": "mock"}
        mock_client.messages.create.return_value = mock_result

        dialogvo = [{"role": "user", "content": "Hello"}]
        result = run_claude_chat_completion(mock_client, "claude-sonnet-4-6", dialogvo)

        assert result["content"] == "Part 1 Part 2"


# ============================================================================
# stream_claude_chat — mock Claude streaming
# ============================================================================


class TestStreamClaudeChat:
    def test_stream_events(self):
        from service.claude_service import stream_claude_chat

        # Mock stream events
        delta_event1 = MagicMock()
        delta_event1.type = "content_block_delta"
        delta_event1.delta = MagicMock()
        delta_event1.delta.text = "Hello"

        delta_event2 = MagicMock()
        delta_event2.type = "content_block_delta"
        delta_event2.delta = MagicMock()
        delta_event2.delta.text = " World"

        message_delta = MagicMock()
        message_delta.type = "message_delta"
        message_delta.delta = MagicMock()
        message_delta.delta.stop_reason = "end_turn"

        mock_stream = MagicMock()
        mock_stream.__iter__.return_value = [delta_event1, delta_event2, message_delta]
        mock_stream.__enter__.return_value = mock_stream
        mock_stream.__exit__.return_value = None

        mock_client = MagicMock()
        mock_client.messages.stream.return_value = mock_stream

        dialogvo = [{"role": "user", "content": "Hello"}]
        events = list(stream_claude_chat(mock_client, "claude-sonnet-4-6", dialogvo))

        assert len(events) == 3
        assert events[0] == ("text_delta", "Hello", None)
        assert events[1] == ("text_delta", " World", None)
        assert events[2] == ("done", "Hello World", "end_turn")

    def test_stream_with_system_prompt(self):
        from service.claude_service import stream_claude_chat

        delta_event = MagicMock()
        delta_event.type = "content_block_delta"
        delta_event.delta = MagicMock()
        delta_event.delta.text = "Response"

        message_delta = MagicMock()
        message_delta.type = "message_delta"
        message_delta.delta = MagicMock()
        message_delta.delta.stop_reason = "end_turn"

        mock_stream = MagicMock()
        mock_stream.__iter__.return_value = [delta_event, message_delta]
        mock_stream.__enter__.return_value = mock_stream
        mock_stream.__exit__.return_value = None

        mock_client = MagicMock()
        mock_client.messages.stream.return_value = mock_stream

        dialogvo = [
            {"role": "system", "content": "Be concise"},
            {"role": "user", "content": "Hello"},
        ]
        events = list(stream_claude_chat(mock_client, "claude-sonnet-4-6", dialogvo))

        # 验证 system 被提取
        call_kwargs = mock_client.messages.stream.call_args.kwargs
        assert call_kwargs["system"] == "Be concise"
        assert len(call_kwargs["messages"]) == 1

        assert events[-1] == ("done", "Response", "end_turn")

    def test_stream_empty_response(self):
        from service.claude_service import stream_claude_chat

        message_delta = MagicMock()
        message_delta.type = "message_delta"
        message_delta.delta = MagicMock()
        message_delta.delta.stop_reason = "max_tokens"

        mock_stream = MagicMock()
        mock_stream.__iter__.return_value = [message_delta]
        mock_stream.__enter__.return_value = mock_stream
        mock_stream.__exit__.return_value = None

        mock_client = MagicMock()
        mock_client.messages.stream.return_value = mock_stream

        dialogvo = [{"role": "user", "content": "Hello"}]
        events = list(stream_claude_chat(mock_client, "claude-sonnet-4-6", dialogvo))

        assert events[0] == ("done", "", "max_tokens")
