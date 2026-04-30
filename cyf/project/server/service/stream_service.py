import json
import uuid

from flask import Response

from conf.runtime import runtime_state
from model.repositories.log_repository import set_dialog, set_log
from service.chat_service import check_test_user_limit, convert_dialog_for_model, is_valid_model, prepare_dialog
from service.common_service import generate_sse_error, handle_api_exception
from service.host_service import get_client_for_user


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
        try:
            if is_stream_cancelled(request_id):
                return
            api_params = {
                "model": model,
                "messages": convert_dialog_for_model(dialogvo, model),
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
                        yield f"data: {json.dumps({'content': content_piece, 'done': False})}\n\n"
                    if chunk.choices[0].finish_reason:
                        finish_reason = chunk.choices[0].finish_reason
            if was_cancelled:
                return
            tokens_used = len(full_content.encode("utf-8")) // 4
            set_log(user, tokens_used, model, json.dumps({"content": full_content}))
            dialog_id = set_dialog(user, model, "chat", title, json.dumps(dialogvo + [{"role": "assistant", "content": full_content}]))
            yield f"data: {json.dumps({'content': '', 'done': True, 'finish_reason': finish_reason, 'dialog_id': dialog_id})}\n\n"
        except Exception as api_exc:
            error_response = handle_api_exception(api_exc, logger, user=user, model=model, dialog_content=dialogs, url_index=url_index)
            yield f"data: {json.dumps({'content': error_response.get('msg', 'API请求失败'), 'done': True, 'error': error_response})}\n\n"
        finally:
            cleanup_stream_request(request_id)

    return build_stream_response(generate())
