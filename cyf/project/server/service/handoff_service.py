import json

from model.repositories.log_repository import get_dialog_context, set_dialog, set_log
from service.chat_service import convert_dialog_for_model
from service.claude_service import run_claude_chat_completion
from service.common_service import handle_api_exception
from service.dialog_context_service import build_dialog_context_payload, current_time_str, parse_dialog_payload
from service.host_service import get_client_for_user, get_claude_client_for_user, is_claude_model
from service.llm_usage_service import normalize_usage
from service.message_normalizer import build_parts_from_message, ensure_message_parts
from service.model_service import is_valid_model


HANDOFF_SYSTEM_PROMPT = """你是 Codex 的 handoff 上下文压缩助手。
请把下面完整会话压缩成一份可直接放入新对话继续工作的交接摘要。
必须保留：
1. 用户的目标和当前任务状态
2. 已确认的重要事实、关键结论和约束
3. 已完成/未完成的动作
4. 文件、链接、接口、模型、配置、错误信息等关键线索
5. 下一步最应该执行的操作

要求：
- 使用中文
- 结构清晰、简洁但不要丢失可执行细节
- 不要编造会话中不存在的信息
- 对不确定内容明确标注“不确定”或“待验证”
"""


def _truncate_title(title: str, max_length: int = 180) -> str:
    title = (title or "未命名对话").strip()
    return title[:max_length]


def _build_handoff_title(source_title: str) -> str:
    timestamp = current_time_str().replace(":", "").replace(" ", "_")
    return f"交接摘要 - {_truncate_title(source_title)} - {timestamp}"


def _render_dialog_messages(messages: list[dict]) -> str:
    rendered = []
    for index, message in enumerate(messages, start=1):
        if not isinstance(message, dict):
            continue
        rendered.append(json.dumps({
            "index": index,
            "role": message.get("role", ""),
            "time": message.get("time", ""),
            "content": message.get("content", ""),
            "url": message.get("url", ""),
            "parts": message.get("parts", []),
        }, ensure_ascii=False))
    return "\n".join(rendered)


def _build_handoff_user_content(source_dialog, messages: list[dict]) -> str:
    return "\n\n".join([
        f"源对话标题：{source_dialog.dialog_name}",
        f"源对话模型：{source_dialog.modelname}",
        "完整会话内容（JSON Lines）：",
        _render_dialog_messages(messages),
    ])


def create_handoff_dialog(user: str, dialog_id: int, model_override: str = "", logger=None) -> tuple[dict, int]:
    if not dialog_id:
        return {"success": False, "msg": "dialog_id 不能为空"}, 200

    source_dialog = get_dialog_context(user, int(dialog_id))
    if not source_dialog:
        return {"success": False, "msg": "对话不存在或无权限"}, 200

    messages, role_setting, _ = parse_dialog_payload(source_dialog.context)
    if not messages:
        return {"success": False, "msg": "源对话没有可压缩的上下文"}, 200

    model = (model_override or source_dialog.modelname or "").strip()
    if not is_valid_model(model):
        return {"success": False, "msg": "not supported user or model"}, 200

    handoff_user_content = _build_handoff_user_content(source_dialog, messages)
    handoff_messages = [
        {"role": "system", "content": HANDOFF_SYSTEM_PROMPT},
        {"role": "user", "content": handoff_user_content},
    ]
    max_tokens = 16384

    url_index = 0
    try:
        if is_claude_model(model):
            client, url_index = get_claude_client_for_user(user)
            result_data = run_claude_chat_completion(
                client=client,
                model=model,
                dialogvo=handoff_messages,
                max_tokens=max_tokens,
                logger=logger,
            )
            summary = result_data.get("content", "")
            usage = normalize_usage(result_data.get("usage", {}))
            raw_response = result_data.get("raw_response", {})
            parts = result_data.get("parts", build_parts_from_message({"content": summary}))
        else:
            client, url_index = get_client_for_user(user)
            result = client.chat.completions.create(
                model=model,
                messages=convert_dialog_for_model(handoff_messages, model, logger=logger),
                max_tokens=max_tokens,
            )
            summary = result.choices[0].message.content or ""
            usage = normalize_usage(result.usage)
            raw_response = result.to_dict()
            parts = build_parts_from_message({"content": summary})
    except Exception as api_exc:
        return handle_api_exception(api_exc, logger, user=user, model=model, dialog_content=messages, url_index=url_index), 200

    set_log(user, usage.get("total_tokens", 0), model, json.dumps(raw_response, ensure_ascii=False))

    created_at = current_time_str()
    saved_messages = [
        {"role": "user", "content": handoff_user_content, "time": created_at},
        ensure_message_parts({"role": "assistant", "content": summary, "parts": parts, "time": created_at}),
    ]
    title = _build_handoff_title(source_dialog.dialog_name)
    new_dialog_id = set_dialog(
        user,
        model,
        "chat",
        title,
        build_dialog_context_payload(saved_messages, role_setting, usage),
    )

    return {
        "success": True,
        "data": {
            "dialog_id": new_dialog_id,
            "dialog_name": title,
            "modelname": model,
            "usage": usage,
        },
    }, 200
