"""服务端工具注册与 OpenAI tool loop 单测。"""

from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest


def test_normalize_enabled_tools_deduplicates_and_parses_json():
    from service.tools.registry import normalize_enabled_tools

    assert normalize_enabled_tools('["web_search", "web_search"]') == ["web_search"]
    assert normalize_enabled_tools([" WEB_SEARCH ", "unknown"]) == ["web_search", "unknown"]


def test_validate_enabled_tools_respects_server_and_model_network_policy():
    from service.tools.registry import ToolConfigurationError, validate_enabled_tools

    with patch("service.tools.registry.runtime_state") as runtime:
        runtime.model_cache = {"models": [{"id": "offline", "allow_net": False}]}
        runtime.settings.google_web_search_enabled = True
        with pytest.raises(ToolConfigurationError, match="未开启联网"):
            validate_enabled_tools(["web_search"], "offline")


def test_google_search_response_normalization_extracts_sources():
    from service.tools.google_web_search import _normalize_response

    result = _normalize_response(
        {
            "steps": [
                {"type": "model_output", "content": [{"type": "text", "text": "摘要"}], "annotations": [{"title": "来源", "url": "https://example.com"}]}
            ]
        },
        max_sources=8,
    )
    assert result == {"text": "摘要", "sources": [{"title": "来源", "url": "https://example.com"}]}

    result = _normalize_response(
        {"outputs": [{"type": "google_search_result", "result": [{"title": "结果", "url": "https://google.example"}]}, {"type": "text", "text": "答案", "annotations": [{"source": "https://source.example"}]}]},
        max_sources=8,
    )
    assert result["sources"] == [
        {"title": "结果", "url": "https://google.example"},
        {"title": "https://source.example", "url": "https://source.example"},
    ]


def test_google_search_execute_uses_server_side_key_and_url_context():
    from service.tools import google_web_search

    settings = SimpleNamespace(
        google_web_search_enabled=True,
        google_web_search_api_key="secret",
        google_web_search_model="gemini-test",
        google_web_search_base_url="https://google.test/v1beta",
        google_web_search_timeout_seconds=10,
        google_web_search_max_sources=8,
    )
    response = SimpleNamespace(
        raise_for_status=lambda: None,
        json=lambda: {"steps": [{"type": "model_output", "content": [{"type": "text", "text": "ok"}]}]},
    )
    with patch.object(google_web_search.runtime_state, "settings", settings), patch.object(google_web_search.requests, "post", return_value=response) as post:
        result = google_web_search.execute({"query": "latest news", "urls": ["https://example.com"]})

    assert result["text"] == "ok"
    assert post.call_args.kwargs["headers"]["x-goog-api-key"] == "secret"
    assert {"type": "url_context"} in post.call_args.kwargs["json"]["tools"]


def test_openai_tool_loop_executes_call_then_continues():
    from service.tool_loop import run_openai_tool_loop

    first = SimpleNamespace(
        choices=[SimpleNamespace(
            message=SimpleNamespace(
                role="assistant",
                content=None,
                tool_calls=[SimpleNamespace(
                    id="call_1",
                    type="function",
                    function=SimpleNamespace(name="web_search", arguments='{"query":"OpenAI"}'),
                )],
            ),
            finish_reason="tool_calls",
        )],
        usage=SimpleNamespace(prompt_tokens=2, completion_tokens=1, total_tokens=3),
    )
    final = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(role="assistant", content="最终答案", tool_calls=[]), finish_reason="stop")],
        usage=SimpleNamespace(prompt_tokens=4, completion_tokens=2, total_tokens=6),
    )
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=Mock(side_effect=[first, final]))))

    with patch("service.tool_loop.execute_tool_call", return_value={"name": "web_search", "text": "搜索摘要", "sources": []}):
        result = run_openai_tool_loop(client, "gpt-test", [{"role": "user", "content": "查一下"}], 100, ["web_search"])

    assert result["content"] == "最终答案"
    assert result["usage"]["total_tokens"] == 9
    assert result["parts"][-1]["type"] == "tool_result"
    assert client.chat.completions.create.call_count == 2


def test_openai_stream_tool_loop_emits_tool_result_and_final_text():
    from service.tool_loop import stream_openai_tool_loop

    call_delta = SimpleNamespace(
        index=0,
        id="call_1",
        function=SimpleNamespace(name="web_search", arguments='{"query":"AI"}'),
    )
    stream_one = [
        SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=None, tool_calls=[call_delta]), finish_reason=None)]),
        SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=None, tool_calls=[]), finish_reason="tool_calls")]),
    ]
    stream_two = [
        SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="最终答案", tool_calls=[]), finish_reason=None)]),
        SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=None, tool_calls=[]), finish_reason="stop")]),
    ]
    create = Mock(side_effect=[stream_one, stream_two])
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))

    with patch("service.tool_loop.execute_tool_call", return_value={"name": "web_search", "text": "摘要", "sources": []}):
        events = list(stream_openai_tool_loop(client, "gpt-test", [{"role": "user", "content": "查一下"}], 100, ["web_search"]))

    assert [event["type"] for event in events] == ["tool_call", "tool_result", "text_delta", "done"]
    assert events[-1]["content"] == "最终答案"
    assert events[-1]["parts"][-1]["type"] == "tool_result"
