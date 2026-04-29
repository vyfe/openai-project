from datetime import datetime
from typing import Optional

from models import ChildConversation


class ChildConversationRepo:
    @staticmethod
    def create(master_id: int, model_id: str, status: str = 'active', backend_dialog_id: Optional[int] = None, created_round_index: int = 0) -> ChildConversation:
        return ChildConversation.create(
            master=master_id,
            model_id=model_id,
            status=status,
            backend_dialog_id=backend_dialog_id,
            created_round_index=created_round_index,
        )

    @staticmethod
    def list_by_master(master_id: int, include_removed: bool = True) -> list[ChildConversation]:
        query = ChildConversation.select().where(ChildConversation.master == master_id)
        if not include_removed:
            query = query.where(ChildConversation.status != 'removed')
        return list(query.order_by(ChildConversation.id.asc()))

    @staticmethod
    def get_by_master_model(master_id: int, model_id: str) -> Optional[ChildConversation]:
        return (
            ChildConversation.select()
            .where((ChildConversation.master == master_id) & (ChildConversation.model_id == model_id))
            .first()
        )

    @staticmethod
    def update_status(child_id: int, status: str) -> int:
        return (
            ChildConversation.update(status=status, updated_at=datetime.now())
            .where(ChildConversation.id == child_id)
            .execute()
        )

    @staticmethod
    def update_backend_dialog_id(child_id: int, backend_dialog_id: Optional[int]) -> int:
        return (
            ChildConversation.update(backend_dialog_id=backend_dialog_id, updated_at=datetime.now())
            .where(ChildConversation.id == child_id)
            .execute()
        )
