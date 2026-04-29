import json
from typing import Any, Dict, List, Optional

from repositories import (
    ChildConversationRepo,
    MasterConversationRepo,
    RoundCellRepo,
    RoundRepo,
)

VALID_SESSION_TYPES = {'single', 'multi_compare'}
VALID_CHILD_STATUS = {'active', 'removed', 'failed'}
VALID_CELL_STATUS = {'idle', 'streaming', 'success', 'failed', 'skipped'}


class ConversationError(Exception):
    pass


def _assert_session_type(session_type: str):
    if session_type not in VALID_SESSION_TYPES:
        raise ConversationError(f'invalid session_type: {session_type}')


def _assert_child_status(status: str):
    if status not in VALID_CHILD_STATUS:
        raise ConversationError(f'invalid child status: {status}')


def _assert_cell_status(status: str):
    if status not in VALID_CELL_STATUS:
        raise ConversationError(f'invalid cell status: {status}')


def _child_to_dict(child) -> Dict[str, Any]:
    return {
        'child_id': child.id,
        'master_id': child.master_id,
        'model_id': child.model_id,
        'status': child.status,
        'backend_dialog_id': child.backend_dialog_id,
        'created_round_index': child.created_round_index,
        'created_at': child.created_at.strftime('%Y-%m-%d %H:%M:%S') if child.created_at else None,
        'updated_at': child.updated_at.strftime('%Y-%m-%d %H:%M:%S') if child.updated_at else None,
    }


def _round_to_dict(round_obj) -> Dict[str, Any]:
    return {
        'round_id': round_obj.id,
        'master_id': round_obj.master_id,
        'round_index': round_obj.round_index,
        'user_prompt': round_obj.user_prompt,
        'attachments': json.loads(round_obj.attachments_json or '[]'),
        'created_at': round_obj.created_at.strftime('%Y-%m-%d %H:%M:%S') if round_obj.created_at else None,
    }


def _cell_to_dict(cell) -> Dict[str, Any]:
    return {
        'cell_id': cell.id,
        'round_id': cell.round_id,
        'child_id': cell.child_id,
        'assistant_output': cell.assistant_output,
        'cell_status': cell.cell_status,
        'error': json.loads(cell.error_json) if cell.error_json else None,
        'latency_ms': cell.latency_ms,
        'request_id': cell.request_id,
        'updated_at': cell.updated_at.strftime('%Y-%m-%d %H:%M:%S') if cell.updated_at else None,
    }


def create_master(owner: str, title: str, session_type: str, active_models: List[str]) -> Dict[str, Any]:
    _assert_session_type(session_type)
    if not title:
        raise ConversationError('title is required')
    if not active_models:
        raise ConversationError('active_models is required')

    normalized_models = list(dict.fromkeys([m.strip() for m in active_models if m and m.strip()]))
    if not normalized_models:
        raise ConversationError('active_models is empty')

    master = MasterConversationRepo.create(
        owner=owner,
        title=title,
        session_type=session_type,
        active_models=normalized_models,
    )

    children = []
    for model_id in normalized_models:
        child = ChildConversationRepo.create(
            master_id=master.id,
            model_id=model_id,
            status='active',
            backend_dialog_id=None,
            created_round_index=0,
        )
        children.append(_child_to_dict(child))

    return {
        'master': MasterConversationRepo.to_dict(master),
        'children': children,
    }


def list_master(owner: str, page: int, page_size: int) -> Dict[str, Any]:
    page = max(page, 1)
    page_size = max(1, min(page_size, 100))
    offset = (page - 1) * page_size
    masters = MasterConversationRepo.list_by_owner(owner, limit=page_size, offset=offset)

    items = []
    for master in masters:
        d = MasterConversationRepo.to_dict(master)
        children = ChildConversationRepo.list_by_master(master.id, include_removed=False)
        d['active_model_count'] = len([c for c in children if c.status == 'active'])
        items.append(d)

    return {
        'list': items,
        'pagination': {
            'page': page,
            'page_size': page_size,
            'has_more': len(items) == page_size,
        },
    }


def delete_masters(owner: str, master_ids: List[int]) -> Dict[str, Any]:
    normalized_ids = list(dict.fromkeys([int(mid) for mid in master_ids if int(mid) > 0]))
    if not normalized_ids:
        raise ConversationError('master_ids is empty')

    deleted_count = MasterConversationRepo.delete_by_ids(owner=owner, master_ids=normalized_ids)
    return {
        'deleted_count': deleted_count,
        'requested_count': len(normalized_ids),
    }


def get_master_detail(owner: str, master_id: int) -> Dict[str, Any]:
    master = MasterConversationRepo.get(master_id, owner=owner)
    if not master:
        raise ConversationError('master not found')

    children = ChildConversationRepo.list_by_master(master_id, include_removed=True)
    rounds = RoundRepo.list_by_master(master_id)

    cells = []
    for round_obj in rounds:
        round_cells = RoundCellRepo.list_by_round(round_obj.id)
        cells.extend([_cell_to_dict(cell) for cell in round_cells])

    return {
        'master': MasterConversationRepo.to_dict(master),
        'children': [_child_to_dict(child) for child in children],
        'rounds': [_round_to_dict(r) for r in rounds],
        'cells': cells,
    }


def add_model(owner: str, master_id: int, model_id: str) -> Dict[str, Any]:
    if not model_id:
        raise ConversationError('model_id is required')

    master = MasterConversationRepo.get(master_id, owner=owner)
    if not master:
        raise ConversationError('master not found')

    existing = ChildConversationRepo.get_by_master_model(master_id, model_id)
    if existing:
        if existing.status == 'removed':
            ChildConversationRepo.update_status(existing.id, 'active')
            child = ChildConversationRepo.get_by_master_model(master_id, model_id)
        else:
            raise ConversationError('model already exists in master')
    else:
        latest_round_index = RoundRepo.get_latest_round_index(master_id)
        child = ChildConversationRepo.create(
            master_id=master_id,
            model_id=model_id,
            status='active',
            backend_dialog_id=None,
            created_round_index=latest_round_index,
        )

    rounds = RoundRepo.list_by_master(master_id)
    for r in rounds:
        if r.round_index < child.created_round_index:
            continue
        RoundCellRepo.upsert(
            r.id,
            child.id,
            cell_status='skipped',
            assistant_output='',
            error_json=None,
            latency_ms=None,
            request_id=None,
        )

    active_models = json.loads(master.active_models_json or '[]')
    if model_id not in active_models:
        active_models.append(model_id)
        MasterConversationRepo.update_active_models(master_id, active_models)
    MasterConversationRepo.touch(master_id)

    return {
        'child': _child_to_dict(child),
        'active_models': active_models,
    }


def remove_model(owner: str, master_id: int, model_id: str) -> Dict[str, Any]:
    master = MasterConversationRepo.get(master_id, owner=owner)
    if not master:
        raise ConversationError('master not found')

    child = ChildConversationRepo.get_by_master_model(master_id, model_id)
    if not child:
        raise ConversationError('child not found')

    ChildConversationRepo.update_status(child.id, 'removed')

    active_models = [m for m in json.loads(master.active_models_json or '[]') if m != model_id]
    MasterConversationRepo.update_active_models(master_id, active_models)
    MasterConversationRepo.touch(master_id)

    return {
        'child_id': child.id,
        'model_id': model_id,
        'status': 'removed',
        'active_models': active_models,
    }


def create_round(owner: str, master_id: int, user_prompt: str, attachments: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    if not user_prompt:
        raise ConversationError('user_prompt is required')

    master = MasterConversationRepo.get(master_id, owner=owner)
    if not master:
        raise ConversationError('master not found')

    next_round_index = RoundRepo.get_latest_round_index(master_id) + 1
    round_obj = RoundRepo.create(master_id, next_round_index, user_prompt, attachments)

    children = ChildConversationRepo.list_by_master(master_id, include_removed=True)
    created_cells = []
    for child in children:
        if child.status != 'active':
            continue
        cell = RoundCellRepo.upsert(
            round_obj.id,
            child.id,
            cell_status='idle',
            assistant_output='',
            error_json=None,
            latency_ms=None,
            request_id=None,
        )
        created_cells.append(_cell_to_dict(cell))

    MasterConversationRepo.touch(master_id)
    return {
        'round': _round_to_dict(round_obj),
        'cells': created_cells,
        'children': [_child_to_dict(c) for c in children if c.status == 'active'],
    }


def update_round_cell(
    owner: str,
    round_id: int,
    child_id: int,
    cell_status: str,
    assistant_output: Optional[str] = None,
    error: Optional[Dict[str, Any]] = None,
    latency_ms: Optional[int] = None,
    request_id: Optional[str] = None,
) -> Dict[str, Any]:
    _assert_cell_status(cell_status)

    from models import ChildConversation, ConversationRound, MasterConversation

    query = (
        ConversationRound.select(ConversationRound, MasterConversation)
        .join(MasterConversation)
        .where(ConversationRound.id == round_id, MasterConversation.owner == owner)
    )
    round_obj = query.first()
    if not round_obj:
        raise ConversationError('round not found')

    child = (
        ChildConversation.select()
        .where(ChildConversation.id == child_id, ChildConversation.master == round_obj.master_id)
        .first()
    )
    if not child:
        raise ConversationError('child not found')

    error_json = json.dumps(error, ensure_ascii=False) if error else None

    cell = RoundCellRepo.upsert(
        round_id,
        child_id,
        cell_status=cell_status,
        assistant_output=assistant_output,
        error_json=error_json,
        latency_ms=latency_ms,
        request_id=request_id,
    )

    MasterConversationRepo.touch(round_obj.master_id)
    return _cell_to_dict(cell)


def retry_cell(owner: str, round_id: int, child_id: int) -> Dict[str, Any]:
    # 先标记为 streaming，具体模型调用由 route/service 编排层触发
    cell = update_round_cell(
        owner=owner,
        round_id=round_id,
        child_id=child_id,
        cell_status='streaming',
        assistant_output='',
        error=None,
        latency_ms=None,
        request_id=None,
    )
    return {
        'cell': cell,
        'action': 'retry_started',
    }
