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
)


def run_claude_chat_completion(
    client,
    model: str,
    dialogvo: List[Dict[str, Any]],
    max_tokens: int = 102400,
    logger: Optional[logging.Logger] = None,
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

    # 3. 构建请求参数
    api_params: Dict[str, Any] = {
        "model": model,
        "messages": cleaned_messages,
        "max_tokens": max_tokens,
    }
    if system_prompt:
        api_params["system"] = system_prompt

    # 4. 调用 API
    if logger:
        logger.info(f"Claude API 非流式请求: model={model}, messages_count={len(cleaned_messages)}")
    result = client.messages.create(**api_params)

    # 5. 解析响应并归一化
    content = ""
    for block in result.content:
        if block.type == "text":
            content += block.text

    total_tokens = (result.usage.input_tokens or 0) + (result.usage.output_tokens or 0)
    finish_reason = result.stop_reason or "end_turn"

    assistant_message = {"role": "assistant", "content": content}
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
