from datetime import datetime

from peewee import CharField, DateTimeField, ForeignKeyField, IntegerField, Model, TextField

from db import db
from models.child_conversation import ChildConversation
from models.conversation_round import ConversationRound


class RoundCell(Model):
    round = ForeignKeyField(ConversationRound, backref='cells', on_delete='CASCADE')
    child = ForeignKeyField(ChildConversation, backref='cells', on_delete='CASCADE')
    assistant_output = TextField(null=True)
    cell_status = CharField(default='idle')
    error_json = TextField(null=True)
    latency_ms = IntegerField(null=True)
    request_id = CharField(null=True)
    updated_at = DateTimeField(default=datetime.now)

    class Meta:
        database = db
        indexes = (
            (('round', 'child'), True),
        )
