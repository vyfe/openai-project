from datetime import datetime

from peewee import DateTimeField, ForeignKeyField, IntegerField, Model, TextField

from db import db
from models.master_conversation import MasterConversation


class ConversationRound(Model):
    master = ForeignKeyField(MasterConversation, backref='rounds', on_delete='CASCADE')
    round_index = IntegerField()
    user_prompt = TextField()
    attachments_json = TextField(null=True)
    created_at = DateTimeField(default=datetime.now)

    class Meta:
        database = db
        indexes = (
            (('master', 'round_index'), True),
        )
