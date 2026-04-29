from peewee import BooleanField, CharField, IntegerField, Model

from db import db


class ModelMeta(Model):
    model_name = CharField()
    model_desc = CharField()
    model_type = IntegerField(default=1)
    recommend = BooleanField()
    status_valid = BooleanField()
    model_grp = CharField(default='')

    class Meta:
        database = db
        indexes = (
            (('model_name',), True),
        )

    def to_dict(self):
        return {
            'id': self.id,
            'model_name': self.model_name,
            'model_desc': self.model_desc,
            'model_type': self.model_type,
            'recommend': self.recommend,
            'status_valid': self.status_valid,
            'model_grp': self.model_grp,
        }
