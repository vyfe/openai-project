from peewee import BooleanField, CharField, Model, TextField

from db import db


class SystemPrompt(Model):
    role_name = CharField()
    role_group = CharField()
    role_desc = CharField()
    role_content = TextField()
    status_valid = BooleanField()

    class Meta:
        database = db
        indexes = (
            (('role_name', 'role_group'), True),
        )

    def to_dict(self):
        return {
            'id': self.id,
            'role_name': self.role_name,
            'role_group': self.role_group,
            'role_desc': self.role_desc,
            'role_content': self.role_content,
            'status_valid': self.status_valid,
        }
