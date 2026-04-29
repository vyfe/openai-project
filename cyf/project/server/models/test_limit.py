from peewee import CharField, IntegerField, Model

from db import db


class TestLimit(Model):
    user_ip = CharField()
    user_count = IntegerField(default=0)
    limit = IntegerField()

    class Meta:
        database = db
        indexes = (
            (('user_ip',), True),
        )
