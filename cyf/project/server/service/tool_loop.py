"""跨 provider 的模型工具调用循环。

这里不负责决定是否启用工具；调用方先通过 ``validate_enabled_tools`` 校验，
再把本模块的 loop 接到原有聊天链路。这样普通请求仍只有一次原有 API 调用。
"""

from __future__ import annotations

import json
from typing import Any, Callable, Dict, Iterable, List, Optional

from service.llm_usage_service import normalize_usage
from service.message_normalizer import PART_TOOL_RESULT
from service.tools.registry import execute_tool, get_tool_definitions, serialize_tool_result


class ToolLoopError(RuntimeError):
    """模型连续调用工具但未能在限制轮数内完成回答。"""


def as_dict(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    for method in ("model_dump", "to_dict"):
        if hasattr(value, method):
            try:
                result = getattr(value, method)()
                if isinstance(result, dict):
                    return result
            except Exception:
                pass
    if hasattr(value, "__dict__"):
        return {key: item for key, item in vars(value).items() if not key.startswith("_")}
    return {}


def sanitize_provider_messages(messages: Iterable[Any]) -> List[Dict[str, Any]]:
    """移除项目内部字段，避免 ``parts/time`` 被错误发送给上游模型。"""
    sanitized: List[Dict[str, Any]] = []
    for message in messages:
        item = as_dict(message)
        if not item:
            continue
        clean = {key: value for key, value in item.items() if key in {"role", "content", "name", "tool_calls", "tool_call_id"}}
        if clean.get("role") and ("content" in clean or clean.get("tool_calls")):
            sanitized.append(clean)
    return sanitized


def _tool_part(result: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "type": PART_TOOL_RESULT,
        "name": result.get("name"),
        "text": result.get("text", ""),
        "data": {"sources": result.get("sources", []), "error": result.get("error")},
    }


def execute_tool_call(name: str, raw_arguments: Any, logger=None) -> Dict[str, Any]:
    try:
        arguments = raw_arguments if isinstance(raw_arguments, dict) else json.loads(raw_arguments or "{}")
        if not isinstance(arguments, dict):
            raise ValueError("工具参数必须是 JSON 对象")
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        return {"name": name, "text": "", "sources": [], "error": f"工具参数解析失败: {exc}"}
    try:
        return execute_tool(name, arguments, logger=logger)
    except Exception as exc:  # 工具错误回传模型，让模型决定如何向用户解释
        if logger:
            logger.warning("工具执行失败 name=%s error=%s", name, exc)
        return {"name": name, "text": "", "sources": [], "error": str(exc)}


def _merge_usage(total: Dict[str, int], current: Any) -> Dict[str, int]:
    usage = normalize_usage(current)
    for key, value in usage.items():
        total[key] = total.get(key, 0) + int(value or 0)
    return total


def _openai_message_tool_calls(message: Any) -> List[Dict[str, Any]]:
    item = as_dict(message)
    calls = item.get("tool_calls") or getattr(message, "tool_calls", None) or []
    normalized = []
    for call in calls:
        call_dict = as_dict(call)
        function = as_dict(call_dict.get("function"))
        if not function:
            function = as_dict(getattr(call, "function", None))
        name = str(function.get("name") or "").strip()
        if not name:
            continue
        normalized.append({
            "id": str(call_dict.get("id") or getattr(call, "id", "") or ""),
            "type": call_dict.get("type") or "function",
            "name": name,
            "arguments": function.get("arguments", "{}"),
        })
    return normalized


def run_openai_tool_loop(
    client,
    model: str,
    messages: Iterable[Any],
    max_tokens: int,
    tool_names: Iterable[str],
    logger=None,
    max_rounds: int = 3,
) -> Dict[str, Any]:
    """OpenAI Chat Completions 非流式工具循环。"""
    current_messages = sanitize_provider_messages(messages)
    definitions = get_tool_definitions(tool_names, provider="openai")
    usage: Dict[str, int] = {}
    tool_parts: List[Dict[str, Any]] = []
    last_response = None

    for _ in range(max(1, max_rounds)):
        last_response = client.chat.completions.create(
            model=model,
            messages=current_messages,
            max_tokens=max_tokens,
            tools=definitions,
            tool_choice="auto",
        )
        usage = _merge_usage(usage, getattr(last_response, "usage", None))
        choice = last_response.choices[0]
        message = choice.message
        calls = _openai_message_tool_calls(message)
        if not calls:
            content = getattr(message, "content", None) or as_dict(message).get("content") or ""
            parts = ([{"type": "text", "text": content}] if content else []) + tool_parts
            return {
                "role": getattr(message, "role", None) or "assistant",
                "content": content,
                "parts": parts,
                "finish_reason": getattr(choice, "finish_reason", None) or "stop",
                "usage": usage,
                "raw_response": as_dict(last_response),
            }

        assistant_item = as_dict(message)
        if not assistant_item:
            assistant_item = {"role": "assistant", "content": getattr(message, "content", None)}
        assistant_item["role"] = assistant_item.get("role") or "assistant"
        assistant_item["tool_calls"] = [
            {
                "id": call["id"],
                "type": call["type"],
                "function": {"name": call["name"], "arguments": call["arguments"]},
            }
            for call in calls
        ]
        current_messages.append(assistant_item)
        for call in calls:
            result = execute_tool_call(call["name"], call["arguments"], logger=logger)
            tool_parts.append(_tool_part(result))
            current_messages.append({
                "role": "tool",
                "tool_call_id": call["id"],
                "content": serialize_tool_result(result),
            })

    raise ToolLoopError(f"工具调用超过最大轮数（{max_rounds}）")


def stream_openai_tool_loop(
    client,
    model: str,
    messages: Iterable[Any],
    max_tokens: int,
    tool_names: Iterable[str],
    logger=None,
    max_rounds: int = 3,
    is_cancelled: Optional[Callable[[], bool]] = None,
    on_stream: Optional[Callable[[Any], None]] = None,
):
    """OpenAI Chat Completions 流式工具循环，产出统一 dict 事件。"""
    current_messages = sanitize_provider_messages(messages)
    definitions = get_tool_definitions(tool_names, provider="openai")
    all_content = ""
    tool_parts: List[Dict[str, Any]] = []

    for _ in range(max(1, max_rounds)):
        stream = client.chat.completions.create(
            model=model,
            messages=current_messages,
            max_tokens=max_tokens,
            stream=True,
            timeout=300,
            tools=definitions,
            tool_choice="auto",
        )
        if on_stream:
            on_stream(stream)
        turn_content = ""
        tool_calls: Dict[int, Dict[str, Any]] = {}
        finish_reason = None
        for chunk in stream:
            if is_cancelled and is_cancelled():
                return
            choices = getattr(chunk, "choices", None) or []
            if not choices:
                continue
            choice = choices[0]
            delta = getattr(choice, "delta", None)
            if delta is not None:
                text = getattr(delta, "content", None) or as_dict(delta).get("content") or ""
                if text:
                    turn_content += text
                    all_content += text
                    yield {"type": "text_delta", "content": text}
                for call_delta in getattr(delta, "tool_calls", None) or as_dict(delta).get("tool_calls", []) or []:
                    call = as_dict(call_delta)
                    index = int(call.get("index", 0))
                    state = tool_calls.setdefault(index, {"id": "", "name": "", "arguments": ""})
                    state["id"] = state["id"] or str(call.get("id") or "")
                    function = as_dict(call.get("function"))
                    state["name"] = state["name"] or str(function.get("name") or "")
                    state["arguments"] += str(function.get("arguments") or "")
            finish_reason = getattr(choice, "finish_reason", None) or finish_reason

        calls = [call for call in tool_calls.values() if call.get("name")]
        if not calls:
            parts = ([{"type": "text", "text": all_content}] if all_content else []) + tool_parts
            yield {"type": "done", "content": all_content, "finish_reason": finish_reason or "stop", "parts": parts}
            return

        yield {"type": "tool_call", "calls": [{"name": call["name"], "arguments": call["arguments"]} for call in calls]}
        current_messages.append({
            "role": "assistant",
            "content": turn_content or None,
            "tool_calls": [
                {"id": call["id"], "type": "function", "function": {"name": call["name"], "arguments": call["arguments"]}}
                for call in calls
            ],
        })
        for call in calls:
            result = execute_tool_call(call["name"], call["arguments"], logger=logger)
            part = _tool_part(result)
            tool_parts.append(part)
            yield {"type": "tool_result", "part": part}
            current_messages.append({
                "role": "tool",
                "tool_call_id": call["id"],
                "content": serialize_tool_result(result),
            })

    raise ToolLoopError(f"工具调用超过最大轮数（{max_rounds}）")
