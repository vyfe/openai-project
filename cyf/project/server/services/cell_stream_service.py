import json
import time
import uuid
from typing import Any, Dict, Optional

import sqlitelog
from repositories import ChildConversationRepo, LegacyDialogRepo, RoundRepo
from services import conversation_service, stream_runtime_service


class CellStreamError(Exception):
    pass


def _build_sse_data(payload: Dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _build_dialog_array_from_child_history(user: str, child: Dict[str, Any], prompt: str, system_prompt_id: Optional[int] = None):
    backend_dialog_id = child.get('backend_dialog_id')
    dialogvo = []
    if backend_dialog_id:
        legacy_dialog = sqlitelog.get_dialog_context(user, backend_dialog_id)
        if legacy_dialog and legacy_dialog.context:
            try:
                context = json.loads(legacy_dialog.context)
                if isinstance(context, list):
                    dialogvo = [m for m in context if isinstance(m, dict) and m.get('role') in ('system', 'user', 'assistant')]
            except Exception:
                dialogvo = []

    if system_prompt_id:
        system_prompt = sqlitelog.get_system_prompt_by_id(int(system_prompt_id))
        if system_prompt:
            dialogvo = [m for m in dialogvo if m.get('role') != 'system']
            dialogvo.insert(0, {'role': 'system', 'content': system_prompt.get('role_content', '')})

    dialogvo.append({'role': 'user', 'content': prompt})
    return dialogvo


def _load_round_and_child(owner: str, round_id: int, child_id: int):
    from models import ChildConversation, ConversationRound, MasterConversation

    round_obj = (
        ConversationRound.select(ConversationRound, MasterConversation)
        .join(MasterConversation)
        .where(ConversationRound.id == round_id, MasterConversation.owner == owner)
        .first()
    )
    if not round_obj:
        raise CellStreamError('round not found')

    child_obj = (
        ChildConversation.select()
        .where(ChildConversation.id == child_id, ChildConversation.master == round_obj.master_id)
        .first()
    )
    if not child_obj:
        raise CellStreamError('child not found')

    if child_obj.status != 'active':
        raise CellStreamError('child is not active')

    child = {
        'child_id': child_obj.id,
        'master_id': child_obj.master_id,
        'model_id': child_obj.model_id,
        'backend_dialog_id': child_obj.backend_dialog_id,
    }
    return round_obj, child


def stream_round_cell(
    user: str,
    round_id: int,
    child_id: int,
    system_prompt_id: Optional[int] = None,
    max_response_tokens: Optional[int] = None,
    request_id: Optional[str] = None,
):
    round_obj, child = _load_round_and_child(user, round_id, child_id)
    prompt = round_obj.user_prompt
    if not prompt:
        raise CellStreamError('round prompt is empty')

    rid = request_id or f"v2:{uuid.uuid4().hex}:{round_id}:{child_id}"
    stream_runtime_service.register_runtime(rid, {'round_id': round_id, 'child_id': child_id})

    conversation_service.update_round_cell(
        owner=user,
        round_id=round_id,
        child_id=child_id,
        cell_status='streaming',
        assistant_output='',
        error=None,
        latency_ms=None,
        request_id=rid,
    )

    def generate():
        full_content = ''
        started = time.time()
        url_index = None
        stream = None
        import server
        try:
            dialogvo = _build_dialog_array_from_child_history(user, child, prompt, system_prompt_id)
            api_params = {
                'model': child['model_id'],
                'messages': server.convert_dialog_for_model(dialogvo, child['model_id']),
                'max_tokens': max_response_tokens or 102400,
                'stream': True,
                'timeout': 300,
            }
            client, url_index = server.get_client_for_user(user)
            stream = client.chat.completions.create(**api_params)
            finish_reason = None
            for chunk in stream:
                if stream_runtime_service.is_cancelled(rid):
                    try:
                        stream.close()
                    except Exception:
                        pass
                    yield _build_sse_data({'done': True, 'cancelled': True, 'request_id': rid})
                    return

                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                if delta and delta.content:
                    piece = delta.content
                    full_content += piece
                    yield _build_sse_data({
                        'done': False,
                        'round_id': round_id,
                        'child_id': child_id,
                        'content': piece,
                        'request_id': rid,
                    })
                if chunk.choices[0].finish_reason:
                    finish_reason = chunk.choices[0].finish_reason

            latency_ms = int((time.time() - started) * 1000)
            updated = conversation_service.update_round_cell(
                owner=user,
                round_id=round_id,
                child_id=child_id,
                cell_status='success',
                assistant_output=full_content,
                error=None,
                latency_ms=latency_ms,
                request_id=rid,
            )

            # 子会话独立保存：落到 legacy Dialog，维护 backend_dialog_id
            child_dialog_id = child.get('backend_dialog_id')
            title = f"{round_obj.master_id}-{child['model_id']}"
            new_dialog_id = LegacyDialogRepo.set_dialog(
                user=user,
                model=child['model_id'],
                chattype='chat',
                dialog_name=title,
                context=json.dumps(dialogvo + [{'role': 'assistant', 'content': full_content}], ensure_ascii=False),
                dialog_id=child_dialog_id,
            )
            if not child_dialog_id and new_dialog_id:
                ChildConversationRepo.update_backend_dialog_id(child['child_id'], new_dialog_id)

            yield _build_sse_data({
                'done': True,
                'finish_reason': finish_reason,
                'round_id': round_id,
                'child_id': child_id,
                'request_id': rid,
                'cell': updated,
            })
        except Exception as e:
            error_msg = str(e)
            if url_index is not None:
                err = server.handle_api_exception(
                    e, user=user, model=child['model_id'], dialog_content=prompt, url_index=url_index
                )
                error_msg = err.get('msg') or error_msg
            updated = conversation_service.update_round_cell(
                owner=user,
                round_id=round_id,
                child_id=child_id,
                cell_status='failed',
                assistant_output='',
                error={'msg': error_msg},
                latency_ms=None,
                request_id=rid,
            )
            yield _build_sse_data({
                'done': True,
                'round_id': round_id,
                'child_id': child_id,
                'request_id': rid,
                'error': {'msg': error_msg},
                'cell': updated,
            })
        finally:
            stream_runtime_service.cleanup_runtime(rid)

    return rid, generate


def cancel_stream_cell(request_id: str) -> bool:
    return stream_runtime_service.cancel_runtime(request_id)
