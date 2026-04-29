import json
from typing import Optional

from models import ConversationRound


class RoundRepo:
    @staticmethod
    def create(master_id: int, round_index: int, user_prompt: str, attachments: Optional[list] = None) -> ConversationRound:
        return ConversationRound.create(
            master=master_id,
            round_index=round_index,
            user_prompt=user_prompt,
            attachments_json=json.dumps(attachments or [], ensure_ascii=False),
        )

    @staticmethod
    def list_by_master(master_id: int) -> list[ConversationRound]:
        return list(
            ConversationRound.select()
            .where(ConversationRound.master == master_id)
            .order_by(ConversationRound.round_index.asc())
        )

    @staticmethod
    def get_latest_round_index(master_id: int) -> int:
        latest = (
            ConversationRound.select()
            .where(ConversationRound.master == master_id)
            .order_by(ConversationRound.round_index.desc())
            .first()
        )
        return latest.round_index if latest else 0
