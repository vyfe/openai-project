import json
import uuid

from flask import Response

from conf.runtime import runtime_state
from model.repositories.log_repository import set_dialog, set_log
from service.chat_service import check_test_user_limit, convert_dialog_for_model, is_valid_model, prepare_dialog
from service.common_service import generate_sse_error, handle_api_exception
from service.dialog_context_service import build_dialog_context_payload, current_time_str, stamp_latest_user_message
from service.host_service import get_client_for_user, get_claude_client_for_user, is_claude_model
from service.claude_service import stream_claude_chat
from service.message_normalizer import build_parts_from_message, ensure_message_parts


def register_stream_request(request_id: str):
    with runtime_state.stream_cancel_lock:
        runtime_state.stream_cancel_registry[request_id] = {"cancelled": False, "stream": None}


def set_stream_object(request_id: str, stream_obj):
    with runtime_state.stream_cancel_lock:
        if request_id in runtime_state.stream_cancel_registry:
            runtime_state.stream_cancel_registry[request_id]["stream"] = stream_obj


def is_stream_cancelled(request_id: str) -> bool:
    with runtime_state.stream_cancel_lock:
        entry = runtime_state.stream_cancel_registry.get(request_id)
        return bool(entry and entry.get("cancelled"))


def cancel_stream_request(request_id: str) -> bool:
    stream_obj = None
    with runtime_state.stream_cancel_lock:
        entry = runtime_state.stream_cancel_registry.get(request_id)
        if not entry:
            return False
        entry["cancelled"] = True
        stream_obj = entry.get("stream")
    if stream_obj is not None:
        try:
            stream_obj.close()
        except Exception:
            pass
    return True


def cleanup_stream_request(request_id: str):
    with runtime_state.stream_cancel_lock:
        runtime_state.stream_cancel_registry.pop(request_id, None)


def build_stream_response(generator):
    return Response(
        generator,
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "close"},
    )


def stream_chat(user: str, payload, logger):
    request_id = payload.request_id or uuid.uuid4().hex
    model = payload.model
    limit_error = check_test_user_limit(user)
    if not limit_error["success"]:
        return build_stream_response(generate_sse_error(limit_error["msg"], "TEST_EXCEED"))
    if not is_valid_model(model):
        return build_stream_response(generate_sse_error("not supported user or model", "MODEL_ERROR"))
    dialogs = payload.dialog
    dialogvo, title = prepare_dialog(dialogs, payload.dialog_mode, payload.dialog_title, payload.system_prompt_id, logger)
    if dialogvo is None:
        return build_stream_response(generate_sse_error(title, "DIALOG_MODE_ERROR"))
    register_stream_request(request_id)

    def generate():
        full_content = ""
        was_cancelled = False
        url_index = None
        try:
            if is_stream_cancelled(request_id):
                return

            # === Claude 流式分支 ===
            if is_claude_model(model):
                claude_client, url_index = get_claude_client_for_user(user)
                stream_gen = stream_claude_chat(
                    client=claude_client,
                    model=model,
                    dialogvo=dialogvo,
                    max_tokens=payload.max_response_tokens or 102400,
                    logger=logger,
                )
                finish_reason = None
                for event in stream_gen:
                    if is_stream_cancelled(request_id):
                        was_cancelled = True
                        break
                    event_type = event[0]
                    if event_type == "text_delta":
                        content_piece = event[1]
                        full_content += content_piece
                        yield f"data: {json.dumps({'type': 'text_delta', 'content': content_piece, 'done': False})}\n\n"
                    elif event_type == "done":
                        _, content, finish_reason = event
                if was_cancelled:
                    return

            else:
                # === 原有 OpenAI 流式分支 ===
                api_params = {
                    "model": model,
                    "messages": convert_dialog_for_model(dialogvo, model, logger=logger),
                    "max_tokens": payload.max_response_tokens or 102400,
                    "stream": True,
                    "timeout": 300,
                }
                client, url_index = get_client_for_user(user)
                stream = client.chat.completions.create(**api_params)
                set_stream_object(request_id, stream)
                finish_reason = None
                for chunk in stream:
                    if is_stream_cancelled(request_id):
                        was_cancelled = True
                        try:
                            stream.close()
                        except Exception:
                            pass
                        break
                    if chunk.choices:
                        delta = chunk.choices[0].delta
                        if delta.content:
                            content_piece = delta.content
                            full_content += content_piece
                            yield f"data: {json.dumps({'type': 'text_delta', 'content': content_piece, 'done': False})}\n\n"
                        if chunk.choices[0].finish_reason:
                            finish_reason = chunk.choices[0].finish_reason
                if was_cancelled:
                    return

            # === 公共完成处理 ===
            tokens_used = len(full_content.encode("utf-8")) // 4
            set_log(user, tokens_used, model, json.dumps({"content": full_content}))
            request_messages = stamp_latest_user_message(dialogvo)
            assistant_time = current_time_str()
            assistant_message = {"role": "assistant", "content": full_content, "time": assistant_time}
            # 归一化为统一 MessagePart 协议
            assistant_message = ensure_message_parts(assistant_message)
            dialog_id = set_dialog(
                user,
                model,
                "chat",
                title,
                build_dialog_context_payload(request_messages + [assistant_message], payload.role_setting),
            )
            yield f"data: {json.dumps({'type': 'done', 'content': '', 'done': True, 'finish_reason': finish_reason, 'dialog_id': dialog_id, 'time': assistant_time})}\n\n"
        except Exception as api_exc:
            error_response = handle_api_exception(api_exc, logger, user=user, model=model, dialog_content=dialogs, url_index=url_index)
            yield f"data: {json.dumps({'content': error_response.get('msg', 'API请求失败'), 'done': True, 'error': error_response})}\n\n"
        finally:
            cleanup_stream_request(request_id)

    return build_stream_response(generate())
