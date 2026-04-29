from peewee import CharField, DateField, Model, TextField

from db import db


class Dialog(Model):
    username = CharField()
    chattype = CharField()
    modelname = CharField()
    dialog_name = CharField()
    start_date = DateField()
    context = TextField()

    class Meta:
        database = db
        indexes = (
            (('username', 'chattype', 'dialog_name'), True),
        )
