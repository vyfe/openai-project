from datetime import datetime

from peewee import CharField, DateTimeField, Model, TextField

from db import db


class MasterConversation(Model):
    owner = CharField()
    title = CharField()
    session_type = CharField(default='single')
    active_models_json = TextField(default='[]')
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)

    class Meta:
        database = db
        indexes = (
            (('owner', 'updated_at'), False),
        )
