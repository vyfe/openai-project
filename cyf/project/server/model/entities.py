import hashlib
import json
import secrets
from datetime import datetime

from peewee import BooleanField, CharField, DateField, DateTimeField, FloatField, IntegerField, Model, TextField

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
    allow_net = BooleanField(default=False)
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
            "allow_net": self.allow_net,
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
    # 兼容字段：仅投影为 admin/user，真实授权一律读取 user_role 表。
    role = CharField(default="user")
    is_active = BooleanField(default=True)
    deleted_at = DateTimeField(null=True)
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


class UserRole(BaseModel):
    """用户与角色的成员关系表，授权的唯一来源。"""

    user_id = IntegerField(index=True)
    role = CharField()
    created_at = DateTimeField(default=datetime.now)

    class Meta:
        database = db
        table_name = "user_role"
        indexes = ((("user_id", "role"), True),)


class PlatformSchemaMigration(BaseModel):
    """平台库迁移版本表；启动时校验关键版本，缺失即阻止业务启动。"""

    version = CharField(primary_key=True)
    applied_at = DateTimeField(default=datetime.now)
    note = TextField(default="")

    class Meta:
        database = db
        table_name = "platform_schema_migration"


class VoiceAssetOwnership(BaseModel):
    """自定义音色的归属记录；系统音色共享，不写入本表。"""

    scope = CharField()
    voice_id = CharField()
    owner_user_id = IntegerField(index=True)
    created_at = DateTimeField(default=datetime.now)

    class Meta:
        database = db
        table_name = "voice_asset_ownership"
        indexes = ((("scope", "voice_id"), True),)


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


class VoiceAccountState(BaseModel):
    scope = CharField(primary_key=True)
    state_json = TextField(default="{}")

    class Meta:
        table_name = "voice_account_state"


class VoiceReading(BaseModel):
    id = CharField(primary_key=True)
    scope = CharField(index=True)
    owner_user_id = IntegerField(null=True, index=True)
    title = CharField()
    source_text = TextField()
    voice_id = CharField()
    model = CharField()
    speed = FloatField(default=0.9)
    volume = FloatField(default=1)
    pitch = IntegerField(default=0)
    emotion = CharField(default="")
    status = CharField(default="generating")
    audio_url = TextField(null=True)
    url_expires_at = DateTimeField(null=True)
    duration_seconds = FloatField(null=True)
    usage_characters = IntegerField(null=True)
    usage_voice_count = IntegerField(default=0)
    size = IntegerField(default=0)
    error_message = TextField(null=True)
    created_at = DateTimeField(default=datetime.utcnow)

    class Meta:
        table_name = "voice_reading"
        indexes = ((("scope", "created_at"), False),)


class MusicTrack(BaseModel):
    id = CharField(primary_key=True)
    scope = CharField(index=True)
    owner_user_id = IntegerField(null=True, index=True)
    title = CharField()
    prompt = TextField(null=True)
    lyrics = TextField(null=True)
    model = CharField()
    instrumental = BooleanField(default=False)
    lyrics_optimizer = BooleanField(default=False)
    status = CharField(default="generating")
    cover_feature_id = TextField(null=True)
    reference_duration = FloatField(null=True)
    audio_url = TextField(null=True)
    url_expires_at = DateTimeField(null=True)
    duration_seconds = FloatField(null=True)
    size = IntegerField(default=0)
    error_message = TextField(null=True)
    created_at = DateTimeField(default=datetime.utcnow)

    class Meta:
        table_name = "music_track"
        indexes = ((("scope", "created_at"), False),)


ALL_MODELS = [
    Log,
    Dialog,
    ModelMeta,
    SystemPrompt,
    TestLimit,
    User,
    UserRole,
    PlatformSchemaMigration,
    VoiceAssetOwnership,
    Notification,
    VoiceAccountState,
    VoiceReading,
    MusicTrack,
]
