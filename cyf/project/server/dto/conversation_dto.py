from typing import Any, Dict, List, Optional


class DTOError(Exception):
    pass


def _to_int(value: Any, field: str) -> int:
    try:
        return int(value)
    except Exception:
        raise DTOError(f'{field} must be int')


def _parse_str_list_strict(value: Any, field: str) -> List[str]:
    if not isinstance(value, list):
        raise DTOError(f'{field} must be list')
    return [str(item).strip() for item in value if str(item).strip()]


def parse_create_master(data: Dict[str, Any]) -> Dict[str, Any]:
    title = (data.get('title') or '').strip()
    session_type = (data.get('session_type') or 'single').strip() or 'single'
    active_models = _parse_str_list_strict(data.get('active_models'), 'active_models')

    return {
        'title': title,
        'session_type': session_type,
        'active_models': active_models,
    }


def parse_master_id(data: Dict[str, Any]) -> Dict[str, Any]:
    return {'master_id': _to_int(data.get('master_id'), 'master_id')}


def parse_add_remove_model(data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        'master_id': _to_int(data.get('master_id'), 'master_id'),
        'model_id': (data.get('model_id') or '').strip(),
    }


def parse_master_delete(data: Dict[str, Any]) -> Dict[str, Any]:
    master_ids = data.get('master_ids')
    if master_ids is None:
        single_id = data.get('master_id')
        if single_id is not None:
            master_ids = [single_id]

    if isinstance(master_ids, str):
        try:
            import json
            master_ids = json.loads(master_ids)
        except Exception:
            master_ids = [item.strip() for item in master_ids.split(',') if item.strip()]

    if not isinstance(master_ids, list):
        raise DTOError('master_ids must be list')

    parsed_ids = []
    for item in master_ids:
        mid = _to_int(item, 'master_id')
        if mid > 0:
            parsed_ids.append(mid)

    parsed_ids = list(dict.fromkeys(parsed_ids))
    if not parsed_ids:
        raise DTOError('master_ids is empty')

    return {'master_ids': parsed_ids}


def parse_round_send(data: Dict[str, Any]) -> Dict[str, Any]:
    attachments = data.get('attachments') or []
    if isinstance(attachments, str):
        try:
            import json
            attachments = json.loads(attachments)
        except Exception:
            attachments = []

    if not isinstance(attachments, list):
        raise DTOError('attachments must be list')

    system_prompt_id = data.get('system_prompt_id')
    max_response_tokens = data.get('max_response_tokens')

    return {
        'master_id': _to_int(data.get('master_id'), 'master_id'),
        'user_prompt': (data.get('user_prompt') or '').strip(),
        'attachments': attachments,
        'system_prompt_id': int(system_prompt_id) if system_prompt_id not in (None, '') else None,
        'max_response_tokens': int(max_response_tokens) if max_response_tokens not in (None, '') else None,
    }


def parse_retry_cell(data: Dict[str, Any]) -> Dict[str, Any]:
    system_prompt_id = data.get('system_prompt_id')
    max_response_tokens = data.get('max_response_tokens')
    return {
        'round_id': _to_int(data.get('round_id'), 'round_id'),
        'child_id': _to_int(data.get('child_id'), 'child_id'),
        'system_prompt_id': int(system_prompt_id) if system_prompt_id not in (None, '') else None,
        'max_response_tokens': int(max_response_tokens) if max_response_tokens not in (None, '') else None,
    }


def parse_stream_cell(data: Dict[str, Any]) -> Dict[str, Any]:
    system_prompt_id = data.get('system_prompt_id')
    max_response_tokens = data.get('max_response_tokens')
    request_id = (data.get('request_id') or '').strip() or None
    return {
        'round_id': _to_int(data.get('round_id'), 'round_id'),
        'child_id': _to_int(data.get('child_id'), 'child_id'),
        'system_prompt_id': int(system_prompt_id) if system_prompt_id not in (None, '') else None,
        'max_response_tokens': int(max_response_tokens) if max_response_tokens not in (None, '') else None,
        'request_id': request_id,
    }


def parse_pagination(data: Dict[str, Any]) -> Dict[str, int]:
    page = data.get('page', 1)
    page_size = data.get('page_size', 20)
    return {
        'page': _to_int(page, 'page'),
        'page_size': _to_int(page_size, 'page_size'),
    }


def parse_legacy_migrate(data: Dict[str, Any]) -> Dict[str, Any]:
    dialog_ids = data.get('dialog_ids')
    if dialog_ids is None:
        single_id = data.get('dialog_id')
        if single_id is not None:
            dialog_ids = [single_id]

    if isinstance(dialog_ids, str):
        try:
            import json
            dialog_ids = json.loads(dialog_ids)
        except Exception:
            dialog_ids = [dialog_ids]

    if not isinstance(dialog_ids, list):
        raise DTOError('dialog_ids must be list')

    parsed_ids = []
    for item in dialog_ids:
        did = _to_int(item, 'dialog_id')
        if did > 0:
            parsed_ids.append(did)

    if not parsed_ids:
        raise DTOError('dialog_ids is empty')

    raw_target_models = data.get('target_models')
    if raw_target_models is None:
        target_models = []
    else:
        target_models = _parse_str_list_strict(raw_target_models, 'target_models')

    return {
        'dialog_ids': list(dict.fromkeys(parsed_ids)),
        'target_models': list(dict.fromkeys(target_models)),
    }
