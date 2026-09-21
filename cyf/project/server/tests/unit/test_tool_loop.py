"""服务端工具注册与 OpenAI tool loop 单测。"""

from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest


def test_normalize_enabled_tools_deduplicates_and_parses_json():
    from service.tools.registry import normalize_enabled_tools

    assert normalize_enabled_tools('["web_search", "web_search"]') == ["web_search"]
    assert normalize_enabled_tools([" WEB_SEARCH ", "unknown"]) == ["web_search", "unknown"]


def test_validate_enabled_tools_respects_local_search_server_switch():
    from service.tools.registry import ToolConfigurationError, validate_enabled_tools

    with patch("service.tools.registry.runtime_state") as runtime:
        runtime.model_cache = {"models": [{"id": "offline", "allow_net": False}]}
        runtime.settings.web_search_enabled = True
        assert validate_enabled_tools(["web_search"]) == ["web_search"]
        runtime.settings.web_search_enabled = False
        with pytest.raises(ToolConfigurationError, match="未启用网络搜索"):
            validate_enabled_tools(["web_search"])


def test_local_search_parses_duckduckgo_and_bing_results():
    from service.tools.local_web_search import _parse_search_results

    duckduckgo_html = """
        <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fnews">示例新闻</a>
        <a class="result__snippet">摘要内容</a>
    """
    assert _parse_search_results(duckduckgo_html, 5) == [
        {"title": "示例新闻", "url": "https://example.com/news", "snippet": "摘要内容"}
    ]

    bing_html = """
        <li class="b_algo"><h2><a href="https://example.org/doc">官方文档</a></h2><div class="b_caption"><p>文档摘要</p></div></li>
    """
    assert _parse_search_results(bing_html, 5) == [
        {"title": "官方文档", "url": "https://example.org/doc", "snippet": "文档摘要"}
    ]


def test_local_search_logs_parser_diagnostics_when_no_results():
    from service.tools import local_web_search

    response = SimpleNamespace(
        status_code=200,
        url="https://html.duckduckgo.com/html/?q=%E8%8B%B1%E7%BB%B4%E5%85%8B",
        headers={"Content-Type": "text/html; charset=UTF-8"},
        text="<html><body>captcha challenge</body></html>",
        raise_for_status=Mock(),
    )
    session = SimpleNamespace(post=Mock(return_value=response))
    logger = Mock()

    with pytest.raises(local_web_search.LocalWebSearchError, match="challenge"):
        local_web_search._search(session, "英维克", ["duckduckgo"], 10, 5, logger=logger)

    parse_call = next(
        call for call in logger.warning.call_args_list if call.args and call.args[0].startswith("本地搜索结果解析")
    )
    assert parse_call.args[1] == "duckduckgo"
    assert parse_call.args[3] == "wt-wt"
    assert parse_call.args[-3] == "captcha,challenge"
    assert parse_call.args[-2] is True
    assert parse_call.args[-1] == 0
    assert session.post.call_args_list[0].kwargs["data"] == {
        "q": "英维克",
        "b": "",
        "kl": "wt-wt",
        "kp": "-1",
    }
    assert session.post.call_args_list[0].kwargs["headers"]["Sec-Fetch-Mode"] == "navigate"
    assert session.post.call_args_list[0].kwargs["headers"]["Referer"] == "https://html.duckduckgo.com/"


def test_local_search_execute_reads_public_pages_without_api_key():
    from service.tools import local_web_search

    settings = SimpleNamespace(
        web_search_enabled=True,
        web_search_engines="duckduckgo,bing",
        web_search_timeout_seconds=10,
        web_search_max_sources=5,
        web_search_max_page_chars=4000,
        web_search_max_context_chars=16000,
        web_search_max_download_bytes=1048576,
    )
    search_results = [{"title": "搜索标题", "url": "https://example.com", "snippet": "搜索摘要"}]
    with (
        patch.object(local_web_search.runtime_state, "settings", settings),
        patch.object(local_web_search, "_search", return_value=(search_results, "duckduckgo")) as search,
        patch.object(
            local_web_search,
            "_get_public_page",
            return_value=("https://example.com", "<html><title>页面标题</title><body>网页正文</body></html>"),
        ) as get_page,
    ):
        result = local_web_search.execute({"query": "latest news"})

    assert result["provider"] == "local:duckduckgo"
    assert result["sources"] == [{"title": "页面标题", "url": "https://example.com"}]
    assert "网页正文" in result["text"]
    search.assert_called_once()
    get_page.assert_called_once()


def test_local_search_rejects_private_addresses():
    from service.tools.local_web_search import _is_public_url

    with patch("service.tools.local_web_search.socket.getaddrinfo", return_value=[(None, None, None, None, ("127.0.0.1", 80))]):
        assert _is_public_url("http://example.test") is False


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
