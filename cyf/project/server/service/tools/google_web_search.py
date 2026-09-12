"""Google 托管搜索工具适配器。

模型先发起 ``web_search`` tool call，服务端才执行本适配器；不会在模型请求前
预先搜索。适配器使用 Google Gemini Interactions API 的 ``google_search`` /
``url_context`` 工具，返回给模型的是可序列化的摘要和来源列表。
"""

from __future__ import annotations

import json
from typing import Any, Dict, Iterable, List, Optional

import requests

from conf.runtime import runtime_state


class GoogleWebSearchError(RuntimeError):
    """Google 搜索执行失败。"""


def tool_definition() -> Dict[str, Any]:
    """返回 OpenAI Chat Completions function tool 定义。"""
    return {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "搜索互联网获取最新信息，并返回摘要及可引用来源。仅在确实需要联网时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "要搜索的问题或关键词"},
                    "urls": {
                        "type": "array",
                        "description": "可选。需要进一步读取的网页 URL，最多 5 个。",
                        "items": {"type": "string"},
                        "maxItems": 5,
                    },
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    }


def claude_tool_definition() -> Dict[str, Any]:
    """返回 Anthropic Messages API tool 定义。"""
    definition = tool_definition()["function"]
    return {
        "name": definition["name"],
        "description": definition["description"],
        "input_schema": definition["parameters"],
    }


def _as_dict(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "to_dict"):
        return value.to_dict()
    return {}


def _extract_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        chunks = []
        for item in value:
            item_dict = _as_dict(item)
            text = item_dict.get("text")
            if text:
                chunks.append(str(text))
        return "".join(chunks)
    item_dict = _as_dict(value)
    return str(item_dict.get("text", "") or "")


def _iter_steps(response: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    steps = response.get("steps") or response.get("outputs") or response.get("output") or []
    if isinstance(steps, dict):
        steps = [steps]
    return (step for step in steps if isinstance(step, dict))


def _normalize_response(response: Dict[str, Any], max_sources: int) -> Dict[str, Any]:
    texts: List[str] = []
    sources: List[Dict[str, str]] = []
    seen_urls = set()

    def add_source(item: Dict[str, Any]):
        url = str(item.get("url") or item.get("uri") or item.get("source") or "").strip()
        if not url or url in seen_urls:
            return
        title = str(item.get("title") or item.get("name") or url).strip()
        seen_urls.add(url)
        sources.append({"title": title, "url": url})

    def collect_sources(value: Any):
        if isinstance(value, list):
            for item in value:
                collect_sources(item)
            return
        if not isinstance(value, dict):
            return
        if value.get("url") or value.get("uri") or value.get("source"):
            add_source(value)
        for key in ("sources", "results", "result", "search_suggestions", "annotations"):
            nested = value.get(key)
            if nested:
                collect_sources(nested)

    for step in _iter_steps(response):
        step_type = str(step.get("type") or "")
        if step_type in {"model_output", "text", "output_text"}:
            text = _extract_text(step.get("content") or step.get("output") or step.get("text"))
            if text:
                texts.append(text)
            collect_sources(step.get("annotations") or [])
        if step_type in {"google_search_call", "web_search_call", "url_context_call"}:
            collect_sources(step)
        if step_type in {"google_search_result", "url_context_result"}:
            collect_sources(step.get("result") or step)
        collect_sources(step)

    text = "\n\n".join(texts).strip()
    if not text:
        text = _extract_text(response.get("output_text") or response.get("text"))
    if not sources:
        collect_sources(response)
    return {"text": text, "sources": sources[:max_sources]}


def execute(arguments: Dict[str, Any], logger=None) -> Dict[str, Any]:
    """执行 Google 搜索并返回稳定的 tool result 结构。"""
    settings = runtime_state.settings
    query = str(arguments.get("query") or "").strip()[:2000]
    raw_urls = arguments.get("urls") or []
    if isinstance(raw_urls, str):
        raw_urls = [raw_urls]
    urls = [str(url).strip() for url in raw_urls if str(url).strip()][:5]
    if not query and not urls:
        raise GoogleWebSearchError("网络搜索需要提供 query 或 urls")

    enabled = bool(getattr(settings, "google_web_search_enabled", False))
    api_key = str(getattr(settings, "google_web_search_api_key", "") or "").strip()
    if not enabled or not api_key:
        raise GoogleWebSearchError("网络搜索未配置，请在服务端 [tools] 段启用 Google API Key")

    base_url = str(
        getattr(settings, "google_web_search_base_url", "https://generativelanguage.googleapis.com/v1beta")
        or "https://generativelanguage.googleapis.com/v1beta"
    ).rstrip("/")
    model = str(getattr(settings, "google_web_search_model", "gemini-2.5-flash") or "gemini-2.5-flash")
    timeout = max(5, int(getattr(settings, "google_web_search_timeout_seconds", 30) or 30))
    max_sources = max(1, int(getattr(settings, "google_web_search_max_sources", 8) or 8))
    prompt = query or "请读取并总结这些网页：" + "\n".join(urls)
    tools = [{"type": "google_search"}]
    if urls:
        tools.append({"type": "url_context"})
        prompt += "\n\n请优先读取以下 URL：\n" + "\n".join(urls)

    if logger:
        logger.info("执行 Google web_search: query_length=%s, urls=%s", len(query), len(urls))
    try:
        response = requests.post(
            f"{base_url}/interactions",
            headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
            json={"model": model, "input": prompt, "tools": tools},
            timeout=timeout,
        )
        response.raise_for_status()
        body = response.json()
    except requests.RequestException as exc:
        raise GoogleWebSearchError(f"Google 网络搜索请求失败: {exc}") from exc
    except (TypeError, ValueError) as exc:
        raise GoogleWebSearchError("Google 网络搜索返回了无效 JSON") from exc

    result = _normalize_response(body, max_sources)
    if not result["text"] and not result["sources"]:
        raise GoogleWebSearchError("Google 网络搜索未返回可用内容")
    return result


def serialize_result(result: Dict[str, Any]) -> str:
    return json.dumps(result, ensure_ascii=False)
