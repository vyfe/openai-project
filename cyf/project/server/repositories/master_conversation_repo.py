import json
from datetime import datetime
from typing import Any, Optional

from models import MasterConversation


class MasterConversationRepo:
    @staticmethod
    def create(owner: str, title: str, session_type: str = 'single', active_models: Optional[list[str]] = None) -> MasterConversation:
        return MasterConversation.create(
            owner=owner,
            title=title,
            session_type=session_type,
            active_models_json=json.dumps(active_models or [], ensure_ascii=False),
        )

    @staticmethod
    def get(master_id: int, owner: Optional[str] = None) -> Optional[MasterConversation]:
        query = MasterConversation.select().where(MasterConversation.id == master_id)
        if owner:
            query = query.where(MasterConversation.owner == owner)
        return query.first()

    @staticmethod
    def list_by_owner(owner: str, limit: int = 20, offset: int = 0) -> list[MasterConversation]:
        query = (
            MasterConversation.select()
            .where(MasterConversation.owner == owner)
            .order_by(MasterConversation.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(query)

    @staticmethod
    def update_active_models(master_id: int, active_models: list[str]) -> int:
        return (
            MasterConversation.update(
                active_models_json=json.dumps(active_models, ensure_ascii=False),
                updated_at=datetime.now(),
            )
            .where(MasterConversation.id == master_id)
            .execute()
        )

    @staticmethod
    def touch(master_id: int) -> int:
        return (
            MasterConversation.update(updated_at=datetime.now())
            .where(MasterConversation.id == master_id)
            .execute()
        )

    @staticmethod
    def delete_by_ids(owner: str, master_ids: list[int]) -> int:
        if not master_ids:
            return 0
        return (
            MasterConversation.delete()
            .where(
                MasterConversation.owner == owner,
                MasterConversation.id.in_(master_ids),
            )
            .execute()
        )

    @staticmethod
    def to_dict(master: MasterConversation) -> dict[str, Any]:
        return {
            'id': master.id,
            'owner': master.owner,
            'title': master.title,
            'session_type': master.session_type,
            'active_models': json.loads(master.active_models_json or '[]'),
            'created_at': master.created_at.strftime('%Y-%m-%d %H:%M:%S') if master.created_at else None,
            'updated_at': master.updated_at.strftime('%Y-%m-%d %H:%M:%S') if master.updated_at else None,
        }
