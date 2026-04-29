from db import db
from models import (
    ChildConversation,
    ConversationRound,
    MasterConversation,
    RoundCell,
)


def ensure_new_conversation_tables() -> None:
    db.connect(reuse_if_open=True)
    db.create_tables(
        [
            MasterConversation,
            ChildConversation,
            ConversationRound,
            RoundCell,
        ],
        safe=True,
    )
