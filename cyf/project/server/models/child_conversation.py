from datetime import datetime

from peewee import CharField, DateTimeField, ForeignKeyField, IntegerField, Model

from db import db
from models.master_conversation import MasterConversation


class ChildConversation(Model):
    master = ForeignKeyField(MasterConversation, backref='children', on_delete='CASCADE')
    model_id = CharField()
    status = CharField(default='active')
    backend_dialog_id = IntegerField(null=True)
    created_round_index = IntegerField(default=0)
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)

    class Meta:
        database = db
        indexes = (
            (('master', 'model_id'), True),
        )
