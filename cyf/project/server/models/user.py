from datetime import datetime
import hashlib
import secrets

from peewee import BooleanField, CharField, DateTimeField, Model, TextField

from db import db


class User(Model):
    username = CharField(unique=True)
    password_hash = CharField()
    salt = CharField()
    api_key = CharField(null=True)
    token = TextField(null=True)
    browser_conf = TextField(null=True)
    role = CharField(default='user')
    is_active = BooleanField(default=True)
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)

    class Meta:
        database = db
        indexes = ((('username',), True),)

    @staticmethod
    def hash_password(password: str, salt: str = None) -> tuple:
        if salt is None:
            salt = secrets.token_hex(16)
        password_hash = hashlib.sha256((password + salt).encode()).hexdigest()
        return password_hash, salt

    def verify_password(self, password: str) -> bool:
        password_hash, _ = User.hash_password(password, self.salt)
        return password_hash == self.password_hash
