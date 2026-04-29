from peewee import CharField, IntegerField, Model, TextField

from db import db


class Log(Model):
    username = CharField()
    modelname = CharField()
    usage = IntegerField()
    request_text = TextField()

    class Meta:
        database = db
