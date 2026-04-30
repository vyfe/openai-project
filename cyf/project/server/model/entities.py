import hashlib
import json
import secrets
from datetime import datetime

from peewee import BooleanField, CharField, DateField, DateTimeField, IntegerField, Model, TextField

from model.db import db


class BaseModel(Model):
    class Meta:
        database = db


class Log(BaseModel):
    username = CharField()
    modelname = CharField()
    usage = IntegerField()
    request_text = TextField()


class Dialog(BaseModel):
    username = CharField()
    chattype = CharField()
    modelname = CharField()
    dialog_name = CharField()
    start_date = DateField()
    context = TextField()

    class Meta:
        database = db
        indexes = ((( "username", "chattype", "dialog_name"), True),)


class ModelMeta(BaseModel):
    model_name = CharField()
    model_desc = CharField()
    model_type = IntegerField(default=1)
    recommend = BooleanField()
    status_valid = BooleanField()
    model_grp = CharField(default="")

    class Meta:
        database = db
        indexes = ((( "model_name",), True),)

    def to_dict(self):
        return {
            "id": self.id,
            "model_name": self.model_name,
            "model_desc": self.model_desc,
            "model_type": self.model_type,
            "recommend": self.recommend,
            "status_valid": self.status_valid,
            "model_grp": self.model_grp,
        }


class SystemPrompt(BaseModel):
    role_name = CharField()
    role_group = CharField()
    role_desc = CharField()
    role_content = TextField()
    status_valid = BooleanField()

    class Meta:
        database = db
        indexes = ((( "role_name", "role_group"), True),)

    def to_dict(self):
        return {
            "id": self.id,
            "role_name": self.role_name,
            "role_group": self.role_group,
            "role_desc": self.role_desc,
            "role_content": self.role_content,
            "status_valid": self.status_valid,
        }


class TestLimit(BaseModel):
    user_ip = CharField()
    user_count = IntegerField(default=0)
    limit = IntegerField()

    class Meta:
        database = db
        indexes = ((( "user_ip",), True),)


class User(BaseModel):
    username = CharField(unique=True)
    password_hash = CharField()
    salt = CharField()
    api_key = CharField(null=True)
    token = TextField(null=True)
    browser_conf = TextField(null=True)
    role = CharField(default="user")
    is_active = BooleanField(default=True)
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)

    class Meta:
        database = db
        indexes = ((( "username",), True),)

    @staticmethod
    def hash_password(password: str, salt: str = None) -> tuple:
        if salt is None:
            salt = secrets.token_hex(16)
        password_hash = hashlib.sha256((password + salt).encode()).hexdigest()
        return password_hash, salt

    def verify_password(self, password: str) -> bool:
        password_hash, _ = User.hash_password(password, self.salt)
        return password_hash == self.password_hash


class Notification(BaseModel):
    title = CharField()
    content = TextField()
    publish_time = DateTimeField(default=datetime.now)
    status = CharField(default="active")
    priority = IntegerField(default=0)
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)

    class Meta:
        database = db
        indexes = (
            (("status",), False),
            (("priority",), False),
            (("publish_time",), False),
        )

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "publish_time": self.publish_time.strftime("%Y-%m-%d %H:%M:%S") if self.publish_time else None,
            "status": self.status,
            "priority": self.priority,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }


ALL_MODELS = [Log, Dialog, ModelMeta, SystemPrompt, TestLimit, User, Notification]
