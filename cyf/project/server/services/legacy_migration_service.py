import json
from typing import Any, Dict, List

import sqlitelog
from repositories import ChildConversationRepo, MasterConversationRepo, RoundCellRepo, RoundRepo


class LegacyMigrationError(Exception):
    pass


def _safe_load_context(raw: str) -> List[Dict[str, Any]]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _normalize_title(dialog_name: str, dialog_id: int) -> str:
    title = (dialog_name or '').strip()
    return title if title else f'迁移会话 #{dialog_id}'


def _normalize_models(legacy_model: str, target_models: List[str]) -> List[str]:
    if target_models:
        # V1 迁移到 V2 默认保持单子会话：仅保留第一个模型
        first = str(target_models[0]).strip() if target_models else ''
        return [first] if first else [legacy_model]
    return [legacy_model]


def migrate_one_dialog(user: str, dialog_id: int, target_models: List[str]) -> Dict[str, Any]:
    dialog = sqlitelog.get_dialog_context(user, dialog_id)
    if not dialog:
        raise LegacyMigrationError(f'dialog not found: {dialog_id}')

    models = _normalize_models(dialog.modelname, target_models)
    if not models:
        raise LegacyMigrationError(f'no models for dialog: {dialog_id}')

    session_type = 'multi_compare' if len(models) > 1 else 'single'
    master = MasterConversationRepo.create(
        owner=user,
        title=_normalize_title(dialog.dialog_name, dialog_id),
        session_type=session_type,
        active_models=models,
    )

    children = []
    for model_id in models:
        child = ChildConversationRepo.create(
            master_id=master.id,
            model_id=model_id,
            status='active',
            backend_dialog_id=dialog.id,
            created_round_index=0,
        )
        children.append(child)

    primary_child = children[0]
    legacy_context = _safe_load_context(dialog.context)
    round_index = 0
    current_user_prompt = None
    pending_attachments: List[Any] = []

    migrated_rounds = 0
    migrated_cells = 0

    for msg in legacy_context:
        role = (msg.get('role') or '').strip()
        if role == 'user':
            current_user_prompt = str(msg.get('content') or '').strip()
            pending_attachments = []
            if not current_user_prompt:
                current_user_prompt = '[空白用户输入]'
        elif role == 'assistant' and current_user_prompt is not None:
            round_index += 1
            round_obj = RoundRepo.create(
                master_id=master.id,
                round_index=round_index,
                user_prompt=current_user_prompt,
                attachments=pending_attachments,
            )
            migrated_rounds += 1

            assistant_output = str(msg.get('content') or msg.get('desc') or '')
            for idx, child in enumerate(children):
                if idx == 0:
                    RoundCellRepo.upsert(
                        round_obj.id,
                        child.id,
                        cell_status='success',
                        assistant_output=assistant_output,
                        error_json=None,
                        latency_ms=None,
                        request_id=f'legacy:{dialog_id}:{round_index}:{child.id}',
                    )
                else:
                    RoundCellRepo.upsert(
                        round_obj.id,
                        child.id,
                        cell_status='skipped',
                        assistant_output='',
                        error_json=None,
                        latency_ms=None,
                        request_id=f'legacy:{dialog_id}:{round_index}:{child.id}',
                    )
                migrated_cells += 1

            current_user_prompt = None
            pending_attachments = []

    # 处理尾部仅 user 无 assistant 的情况
    if current_user_prompt is not None:
        round_index += 1
        round_obj = RoundRepo.create(
            master_id=master.id,
            round_index=round_index,
            user_prompt=current_user_prompt,
            attachments=pending_attachments,
        )
        migrated_rounds += 1
        for child in children:
            RoundCellRepo.upsert(
                round_obj.id,
                child.id,
                cell_status='skipped',
                assistant_output='',
                error_json=None,
                latency_ms=None,
                request_id=f'legacy:{dialog_id}:{round_index}:{child.id}',
            )
            migrated_cells += 1

    MasterConversationRepo.touch(master.id)

    return {
        'legacy_dialog_id': dialog.id,
        'master_id': master.id,
        'title': master.title,
        'models': models,
        'round_count': migrated_rounds,
        'cell_count': migrated_cells,
        'primary_child_id': primary_child.id,
    }


def migrate_dialogs(user: str, dialog_ids: List[int], target_models: List[str]) -> Dict[str, Any]:
    migrated = []
    failed = []
    for dialog_id in dialog_ids:
        try:
            migrated.append(migrate_one_dialog(user, dialog_id, target_models))
        except Exception as e:
            failed.append({'dialog_id': dialog_id, 'error': str(e)})

    return {
        'migrated': migrated,
        'failed': failed,
        'migrated_count': len(migrated),
        'failed_count': len(failed),
    }
