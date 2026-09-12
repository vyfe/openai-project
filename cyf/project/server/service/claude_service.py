"""Claude SDK 集成服务。

封装 Anthropic Messages API 的调用逻辑（非流式和流式），
与现有 OpenAI 路径并行，由 model_grp=claude 触发路由。
"""

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from service.message_normalizer import (
    build_parts_from_message,
    convert_dialog_for_claude,
    ensure_message_parts,
    extract_system_from_dialog,
    PART_TOOL_RESULT,
)
from service.tool_loop import as_dict, execute_tool_call, sanitize_provider_messages
from service.tools.registry import get_tool_definitions, serialize_tool_result


def run_claude_chat_completion(
    client,
    model: str,
    dialogvo: List[Dict[str, Any]],
    max_tokens: int = 102400,
    logger: Optional[logging.Logger] = None,
    tool_names: Optional[List[str]] = None,
    max_tool_rounds: int = 3,
) -> Dict[str, Any]:
    """调用 Claude Messages API（非流式），返回归一化响应。

    返回格式与 run_chat_completion 的响应格式一致：
    {
        "role": "assistant",
        "content": "...",
        "parts": [...],
        "finish_reason": "end_turn",
        "usage": {"total_tokens": ..., "input_tokens": ..., "output_tokens": ...},
    }
    """
    # 1. 转换消息格式（包括 FILE_URL -> Claude image block）
    converted_dialog = convert_dialog_for_claude(dialogvo, logger=logger)

    # 2. 提取 system 消息
    cleaned_messages, system_prompt = extract_system_from_dialog(converted_dialog)

    # 无工具时保持原有单次请求路径。
    if not tool_names:
        api_params: Dict[str, Any] = {
            "model": model,
            "messages": cleaned_messages,
            "max_tokens": max_tokens,
        }
        if system_prompt:
            api_params["system"] = system_prompt
        if logger:
            logger.info(f"Claude API 非流式请求: model={model}, messages_count={len(cleaned_messages)}")
        result = client.messages.create(**api_params)
        content = "".join(block.text for block in result.content if getattr(block, "type", "") == "text")
        total_tokens = (result.usage.input_tokens or 0) + (result.usage.output_tokens or 0)
        finish_reason = result.stop_reason or "end_turn"
        tool_parts: List[Dict[str, Any]] = []
    else:
        result, content, finish_reason, total_tokens, tool_parts = _run_claude_tool_loop(
            client=client,
            model=model,
            cleaned_messages=cleaned_messages,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            tool_names=tool_names,
            max_tool_rounds=max_tool_rounds,
            logger=logger,
        )

    assistant_message = {"role": "assistant", "content": content}
    if tool_parts:
        assistant_message["parts"] = tool_parts
    assistant_message = ensure_message_parts(assistant_message)

    response_data: Dict[str, Any] = {
        "role": "assistant",
        "content": content,
        "parts": assistant_message.get("parts", build_parts_from_message({"content": content})),
        "finish_reason": finish_reason,
        "usage": {
            "total_tokens": total_tokens,
            "input_tokens": result.usage.input_tokens or 0,
            "output_tokens": result.usage.output_tokens or 0,
        },
        "raw_response": result.model_dump() if hasattr(result, "model_dump") else str(result),
    }
    return response_data


def _claude_block_dict(block: Any) -> Dict[str, Any]:
    item = as_dict(block)
    if item:
        return item
    return {key: getattr(block, key) for key in ("type", "id", "name", "input", "text") if hasattr(block, key)}


def _run_claude_tool_loop(
    client,
    model: str,
    cleaned_messages: List[Dict[str, Any]],
    system_prompt: Optional[str],
    max_tokens: int,
    tool_names: List[str],
    max_tool_rounds: int,
    logger=None,
):
    messages = sanitize_provider_messages(cleaned_messages)
    definitions = get_tool_definitions(tool_names, provider="claude")
    total_tokens = 0
    tool_parts: List[Dict[str, Any]] = []
    last_result = None

    for _ in range(max(1, max_tool_rounds)):
        api_params: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "tools": definitions,
            "tool_choice": {"type": "auto"},
        }
        if system_prompt:
            api_params["system"] = system_prompt
        if logger:
            logger.info("Claude API 工具请求: model=%s, messages_count=%s", model, len(messages))
        last_result = client.messages.create(**api_params)
        usage = getattr(last_result, "usage", None)
        total_tokens += int(getattr(usage, "input_tokens", 0) or 0) + int(getattr(usage, "output_tokens", 0) or 0)
        blocks = [_claude_block_dict(block) for block in (getattr(last_result, "content", None) or [])]
        tool_blocks = [block for block in blocks if block.get("type") == "tool_use" and block.get("name")]
        if not tool_blocks:
            content = "".join(str(block.get("text") or "") for block in blocks if block.get("type") == "text")
            parts = ([{"type": "text", "text": content}] if content else []) + tool_parts
            return last_result, content, getattr(last_result, "stop_reason", None) or "end_turn", total_tokens, parts

        messages.append({"role": "assistant", "content": blocks})
        result_blocks = []
        for block in tool_blocks:
            result = execute_tool_call(block["name"], block.get("input") or {}, logger=logger)
            part = {
                "type": PART_TOOL_RESULT,
                "name": result.get("name"),
                "text": result.get("text", ""),
                "data": {"sources": result.get("sources", []), "error": result.get("error")},
            }
            tool_parts.append(part)
            result_blocks.append({
                "type": "tool_result",
                "tool_use_id": block.get("id", ""),
                "content": serialize_tool_result(result),
                "is_error": bool(result.get("error")),
            })
        messages.append({"role": "user", "content": result_blocks})

    raise RuntimeError(f"工具调用超过最大轮数（{max_tool_rounds}）")


def stream_claude_chat(
    client,
    model: str,
    dialogvo: List[Dict[str, Any]],
    max_tokens: int = 102400,
    logger: Optional[logging.Logger] = None,
):
    """调用 Claude Messages API（流式），生成 SSE 事件流。

    产出元组 (event_type, content, finish_reason) 供 stream_service.py 消费：
    - ("text_delta", text_content, None) — 文本增量
    - ("done", full_content, finish_reason) — 完成

    如果出错，抛出异常，由调用方处理。
    """
    # 1. 转换消息格式
    converted_dialog = convert_dialog_for_claude(dialogvo, logger=logger)

    # 2. 提取 system 消息
    cleaned_messages, system_prompt = extract_system_from_dialog(converted_dialog)

    # 3. 构建请求参数
    api_params: Dict[str, Any] = {
        "model": model,
        "messages": cleaned_messages,
        "max_tokens": max_tokens,
    }
    if system_prompt:
        api_params["system"] = system_prompt

    if logger:
        logger.info(f"Claude API 流式请求: model={model}, messages_count={len(cleaned_messages)}")

    # 4. 使用 stream 上下文管理器
    full_content = ""
    finish_reason = None

    with client.messages.stream(**api_params) as stream:
        for event in stream:
            if event.type == "content_block_delta":
                delta = event.delta
                if hasattr(delta, "text") and delta.text:
                    content_piece = delta.text
                    full_content += content_piece
                    yield ("text_delta", content_piece, None)
            elif event.type == "message_delta":
                if hasattr(event, "delta") and hasattr(event.delta, "stop_reason"):
                    finish_reason = event.delta.stop_reason

    # 5. 完成事件
    yield ("done", full_content, finish_reason or "end_turn")


def stream_claude_tool_loop(
    client,
    model: str,
    dialogvo: List[Dict[str, Any]],
    max_tokens: int = 102400,
    tool_names: Optional[List[str]] = None,
    max_tool_rounds: int = 3,
    logger: Optional[logging.Logger] = None,
    is_cancelled=None,
    on_stream=None,
):
    """Claude 流式工具循环，产出与 OpenAI loop 相同的 dict 事件。"""
    converted_dialog = convert_dialog_for_claude(dialogvo, logger=logger)
    messages, system_prompt = extract_system_from_dialog(converted_dialog)
    messages = sanitize_provider_messages(messages)
    definitions = get_tool_definitions(tool_names or [], provider="claude")
    all_content = ""
    tool_parts: List[Dict[str, Any]] = []

    for _ in range(max(1, max_tool_rounds)):
        api_params: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "tools": definitions,
            "tool_choice": {"type": "auto"},
        }
        if system_prompt:
            api_params["system"] = system_prompt
        turn_text = ""
        tool_blocks: List[Dict[str, Any]] = []
        current_tool: Optional[Dict[str, Any]] = None
        stop_reason = None
        with client.messages.stream(**api_params) as stream:
            if on_stream:
                on_stream(stream)
            for event in stream:
                if is_cancelled and is_cancelled():
                    return
                event_type = getattr(event, "type", "")
                if event_type == "content_block_start":
                    block = _claude_block_dict(getattr(event, "content_block", None))
                    if block.get("type") == "tool_use":
                        current_tool = {"type": "tool_use", "id": block.get("id", ""), "name": block.get("name", ""), "input_json": ""}
                        tool_blocks.append(current_tool)
                elif event_type == "content_block_delta":
                    delta = _claude_block_dict(getattr(event, "delta", None))
                    if delta.get("type") == "text_delta" and delta.get("text"):
                        text = str(delta["text"])
                        turn_text += text
                        all_content += text
                        yield {"type": "text_delta", "content": text}
                    elif delta.get("type") == "input_json_delta" and current_tool is not None:
                        current_tool["input_json"] += str(delta.get("partial_json") or "")
                elif event_type == "message_delta":
                    delta = _claude_block_dict(getattr(event, "delta", None))
                    stop_reason = delta.get("stop_reason") or stop_reason
        if is_cancelled and is_cancelled():
            return
        if not tool_blocks or stop_reason not in {"tool_use", "tool_calls"}:
            parts = ([{"type": "text", "text": all_content}] if all_content else []) + tool_parts
            yield {"type": "done", "content": all_content, "finish_reason": stop_reason or "end_turn", "parts": parts}
            return

        yield {"type": "tool_call", "calls": [{"name": block["name"]} for block in tool_blocks]}
        assistant_blocks = [{"type": "text", "text": turn_text}] if turn_text else []
        for block in tool_blocks:
            try:
                block_input = json.loads(block["input_json"] or "{}")
            except json.JSONDecodeError:
                block_input = {}
            assistant_blocks.append({"type": "tool_use", "id": block["id"], "name": block["name"], "input": block_input})
        messages.append({"role": "assistant", "content": assistant_blocks})
        result_blocks = []
        for block in tool_blocks:
            result = execute_tool_call(block["name"], block["input_json"], logger=logger)
            part = {
                "type": "tool_result",
                "name": result.get("name"),
                "text": result.get("text", ""),
                "data": {"sources": result.get("sources", []), "error": result.get("error")},
            }
            tool_parts.append(part)
            yield {"type": "tool_result", "part": part}
            result_blocks.append({
                "type": "tool_result",
                "tool_use_id": block["id"],
                "content": serialize_tool_result(result),
                "is_error": bool(result.get("error")),
            })
        messages.append({"role": "user", "content": result_blocks})

    raise RuntimeError(f"工具调用超过最大轮数（{max_tool_rounds}）")
