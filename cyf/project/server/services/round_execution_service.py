import time
import uuid
from typing import Any, Dict, List, Optional

import sqlitelog
from services import conversation_service


class RoundExecutionError(Exception):
    pass


def _build_dialog_array_from_round_prompt(user_prompt: str, system_prompt: Optional[str] = None) -> List[Dict[str, Any]]:
    dialog = []
    if system_prompt and system_prompt.strip():
        dialog.append({'role': 'system', 'content': system_prompt.strip()})
    dialog.append({'role': 'user', 'content': user_prompt})
    return dialog


def _call_model_once(
    user: str,
    model_id: str,
    prompt: str,
    system_prompt_id: Optional[int] = None,
    max_response_tokens: Optional[int] = None,
) -> Dict[str, Any]:
    dialog_array = _build_dialog_array_from_round_prompt(prompt)
    if system_prompt_id:
        system_prompt = sqlitelog.get_system_prompt_by_id(system_prompt_id)
        if system_prompt:
            dialog_array = [m for m in dialog_array if m.get('role') != 'system']
            dialog_array.insert(0, {'role': 'system', 'content': system_prompt['role_content']})

    api_params = {
        'model': model_id,
        'messages': dialog_array,
        'max_tokens': max_response_tokens or 102400,
    }

    started = time.time()
    # 通过 server.py 获取客户端（带 host 黑名单逻辑）
    import server
    client, url_index = server.get_client_for_user(user)

    try:
        result = client.chat.completions.create(**api_params)
    except Exception as api_e:
        error = server.handle_api_exception(api_e, user=user, model=model_id, dialog_content=prompt, url_index=url_index)
        raise RoundExecutionError(error.get('msg') or str(api_e))

    latency_ms = int((time.time() - started) * 1000)
    content = result.choices[0].message.content if result.choices else ''

    return {
        'assistant_output': content,
        'finish_reason': result.choices[0].finish_reason if result.choices else None,
        'latency_ms': latency_ms,
        'raw': result.to_dict() if hasattr(result, 'to_dict') else {},
    }


def execute_round_fanout(
    user: str,
    master_id: int,
    round_id: int,
    user_prompt: str,
    children: List[Dict[str, Any]],
    system_prompt_id: Optional[int] = None,
    max_response_tokens: Optional[int] = None,
) -> Dict[str, Any]:
    request_group_id = uuid.uuid4().hex
    result_cells = []

    for child in children:
        child_id = child['child_id']
        model_id = child['model_id']
        request_id = f"{request_group_id}:{round_id}:{child_id}"

        conversation_service.update_round_cell(
            owner=user,
            round_id=round_id,
            child_id=child_id,
            cell_status='streaming',
            assistant_output='',
            error=None,
            latency_ms=None,
            request_id=request_id,
        )

        try:
            response = _call_model_once(
                user=user,
                model_id=model_id,
                prompt=user_prompt,
                system_prompt_id=system_prompt_id,
                max_response_tokens=max_response_tokens,
            )
            updated = conversation_service.update_round_cell(
                owner=user,
                round_id=round_id,
                child_id=child_id,
                cell_status='success',
                assistant_output=response['assistant_output'],
                error=None,
                latency_ms=response['latency_ms'],
                request_id=request_id,
            )
            result_cells.append(updated)
        except Exception as e:
            updated = conversation_service.update_round_cell(
                owner=user,
                round_id=round_id,
                child_id=child_id,
                cell_status='failed',
                assistant_output='',
                error={'msg': str(e)},
                latency_ms=None,
                request_id=request_id,
            )
            result_cells.append(updated)

    return {
        'round_id': round_id,
        'cells': result_cells,
    }


def retry_single_cell(
    user: str,
    round_id: int,
    child_id: int,
    prompt: str,
    model_id: str,
    system_prompt_id: Optional[int] = None,
    max_response_tokens: Optional[int] = None,
) -> Dict[str, Any]:
    request_id = f"retry:{uuid.uuid4().hex}:{round_id}:{child_id}"
    conversation_service.update_round_cell(
        owner=user,
        round_id=round_id,
        child_id=child_id,
        cell_status='streaming',
        assistant_output='',
        error=None,
        latency_ms=None,
        request_id=request_id,
    )

    try:
        response = _call_model_once(
            user=user,
            model_id=model_id,
            prompt=prompt,
            system_prompt_id=system_prompt_id,
            max_response_tokens=max_response_tokens,
        )
        cell = conversation_service.update_round_cell(
            owner=user,
            round_id=round_id,
            child_id=child_id,
            cell_status='success',
            assistant_output=response['assistant_output'],
            error=None,
            latency_ms=response['latency_ms'],
            request_id=request_id,
        )
        return {'cell': cell}
    except Exception as e:
        cell = conversation_service.update_round_cell(
            owner=user,
            round_id=round_id,
            child_id=child_id,
            cell_status='failed',
            assistant_output='',
            error={'msg': str(e)},
            latency_ms=None,
            request_id=request_id,
        )
        return {'cell': cell}
