from datetime import datetime

from peewee import CharField, DateTimeField, IntegerField, Model, TextField

from db import db


class Notification(Model):
    title = CharField()
    content = TextField()
    publish_time = DateTimeField(default=datetime.now)
    status = CharField(default='active')
    priority = IntegerField(default=0)
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)

    class Meta:
        database = db
        indexes = (
            (('status',), False),
            (('priority',), False),
            (('publish_time',), False),
        )

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'content': self.content,
            'publish_time': self.publish_time.strftime('%Y-%m-%d %H:%M:%S') if self.publish_time else None,
            'status': self.status,
            'priority': self.priority,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S') if self.updated_at else None,
        }
