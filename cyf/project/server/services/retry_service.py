from typing import Any, Dict, Optional

from models import ChildConversation, ConversationRound
from services import round_execution_service


class RetryError(Exception):
    pass


def retry_cell_once(
    user: str,
    round_id: int,
    child_id: int,
    system_prompt_id: Optional[int] = None,
    max_response_tokens: Optional[int] = None,
) -> Dict[str, Any]:
    round_obj = ConversationRound.select().where(ConversationRound.id == round_id).first()
    if not round_obj:
        raise RetryError('round not found')

    child = ChildConversation.select().where(ChildConversation.id == child_id, ChildConversation.master == round_obj.master_id).first()
    if not child:
        raise RetryError('child not found')

    prompt = round_obj.user_prompt
    if not prompt:
        raise RetryError('round prompt is empty')

    return round_execution_service.retry_single_cell(
        user=user,
        round_id=round_id,
        child_id=child_id,
        prompt=prompt,
        model_id=child.model_id,
        system_prompt_id=system_prompt_id,
        max_response_tokens=max_response_tokens,
    )
