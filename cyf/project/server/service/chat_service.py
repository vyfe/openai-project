import json
import uuid

from openai.types.chat import ChatCompletionUserMessageParam

from conf.runtime import runtime_state
from model.repositories.log_repository import set_dialog, set_log
from model.repositories.model_meta_repository import get_system_prompt_by_id
from model.repositories.user_repository import check_test_limit_exceeded, get_user_api_key, increment_test_limit
from service.common_service import handle_api_exception
from service.dialog_context_service import build_dialog_context_payload, current_time_str, stamp_latest_user_message
from service.host_service import get_client_for_user
from service.message_normalizer import (
    build_parts_from_message,
    convert_dialog_for_multimodal,
    ensure_message_parts,
    is_multimodal_model,
    strip_file_url_markers,
)
from service.model_service import is_valid_model


def is_gemini_model(model_name: str) -> bool:
    return "gemini" in model_name.lower()


def convert_message_for_gemini(message: dict) -> dict:
    from service.image_service import FILE_URL_PATTERN

    content = message.get("content", "")
    if isinstance(content, list):
        return message
    file_urls = FILE_URL_PATTERN.findall(content)
    if not file_urls:
        return message
    text_content = FILE_URL_PATTERN.sub("", content).strip()
    content_array = []
    if text_content:
        content_array.append({"type": "text", "text": text_content})
    for url in file_urls:
        content_array.append({"type": "file_url", "file_url": url})
    return {"role": message.get("role"), "content": content_array}


def convert_dialog_for_model(dialogvo: list, model: str, logger=None) -> list:
    """根据模型类型转换对话格式。

    - Gemini 模型：转换为 {type: "file_url"} 格式
    - 多模态模型（model_type=3）：将 [FILE_URL:...] 转为 base64 image_url 内容块
    - 其他模型：保持原样
    """
    if is_gemini_model(model):
        return [convert_message_for_gemini(msg) for msg in dialogvo]
    if is_multimodal_model(model):
        return convert_dialog_for_multimodal(dialogvo, logger=logger)
    return dialogvo


def extract_title_from_dialog(dialogvo: list, max_length: int = 50) -> str:
    for msg in dialogvo:
        if msg.get("role") == "user":
            content = strip_file_url_markers(msg.get("content", ""))
            if not content:
                continue
            return content[:max_length] + "..." if len(content) > max_length else content
    return "Untitled"


def parse_dialog_mode(dialogs, dialog_mode, dialog_title=None):
    if dialog_mode == "single":
        dialogvo = [ChatCompletionUserMessageParam(role="user", content=dialogs)]
        title = dialog_title or strip_file_url_markers(dialogs)
    elif dialog_mode == "multi":
        dialogvo = json.loads(dialogs)
        title = dialog_title or extract_title_from_dialog(dialogvo)
    else:
        return None, "not supported dialog_mode"
    return dialogvo, title


def check_test_user_limit(user: str) -> dict:
    default_test_api_key = runtime_state.settings.default_api_key
    user_api_key = get_user_api_key(user)
    is_test_key_user = (not user_api_key) or (user_api_key == default_test_api_key)
    if not is_test_key_user:
        return {"success": True}
    if check_test_limit_exceeded(user, runtime_state.settings.test_ip_default_limit):
        return {
            "success": False,
            "msg": runtime_state.settings.test_exceed_msg,
            "error_type": "TEST_LIMIT_EXCEEDED",
        }
    increment_test_limit(user, runtime_state.settings.test_ip_default_limit)
    return {"success": True}


def prepare_dialog(dialogs: str, dialog_mode: str, dialog_title: str, system_prompt_id: str, logger):
    dialogvo, title = parse_dialog_mode(dialogs, dialog_mode, dialog_title)
    if dialogvo is None:
        return None, title
    if system_prompt_id:
        system_prompt = get_system_prompt_by_id(int(system_prompt_id))
        if system_prompt:
            dialogvo = [msg for msg in dialogvo if msg.get("role") != "system"]
            dialogvo.insert(0, {"role": "system", "content": system_prompt["role_content"]})
            logger.info(f"已添加系统提示词 ID: {system_prompt_id}")
    return dialogvo, title


def run_chat_completion(user: str, payload, logger):
    model = payload.model
    if not is_valid_model(model):
        return {"msg": "not supported user or model"}, 200
    limit_error = check_test_user_limit(user)
    if not limit_error["success"]:
        return limit_error, 200
    dialogs = payload.dialog
    dialogvo, title = prepare_dialog(dialogs, payload.dialog_mode, payload.dialog_title, payload.system_prompt_id, logger)
    if dialogvo is None:
        return {"msg": title}, 200
    api_params = {
        "model": model,
        "messages": convert_dialog_for_model(dialogvo, model, logger=logger),
        "max_tokens": payload.max_response_tokens or 102400,
    }
    try:
        client, url_index = get_client_for_user(user)
        result = client.chat.completions.create(**api_params)
        tokens = result.usage.total_tokens
        set_log(user, tokens, model, json.dumps(result.to_dict()))
        request_messages = stamp_latest_user_message(dialogvo)
        assistant_time = current_time_str()
        assistant_message = result.choices[0].message.to_dict()
        assistant_message["time"] = assistant_time
        # 归一化为统一 MessagePart 协议
        assistant_message = ensure_message_parts(assistant_message)
        dialog_id = set_dialog(
            user,
            model,
            "chat",
            title,
            build_dialog_context_payload(request_messages + [assistant_message], payload.role_setting),
        )
        response_data = {
            "role": result.choices[0].message.role,
            "content": result.choices[0].message.content,
            "parts": assistant_message.get("parts", build_parts_from_message({"content": result.choices[0].message.content})),
            "finish_reason": result.choices[0].finish_reason,
            "time": assistant_time,
        }
        if dialog_id:
            response_data["dialog_id"] = dialog_id
        return response_data, 200
    except Exception as api_exc:
        return handle_api_exception(api_exc, logger, user=user, model=model, dialog_content=dialogs, url_index=url_index), 200
