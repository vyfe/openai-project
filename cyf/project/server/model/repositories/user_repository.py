import json
from datetime import datetime
from typing import Iterable, Optional

from peewee import DoesNotExist

from model.db import db
from model.entities import Notification, TestLimit, User, UserRole
from service.permission_service import (
    ROLE_ADMIN,
    ROLE_CHAT,
    ROLE_SET,
    sort_roles,
    to_compat_role,
)


def message_query(sql: str, params=None):
    cursor = db.execute_sql(sql, params)
    columns = [desc[0] for desc in cursor.description] if cursor.description else []
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def get_user_by_username(username: str, role: str = None):
    try:
        if not role:
            return User.get(User.username == username, User.is_active == True, User.deleted_at.is_null(True))
        return User.get(User.username == username, User.is_active == True, User.deleted_at.is_null(True), User.role == role)
    except DoesNotExist:
        return None


def get_user_token_payload(username: str) -> Optional[dict]:
    user = get_user_by_username(username)
    if not user or not user.token:
        return None
    try:
        payload = json.loads(user.token)
        if isinstance(payload, dict):
            return payload
    except Exception:
        pass
    return None


def set_user_token_payload(username: str, payload: Optional[dict]) -> bool:
    user = get_user_by_username(username)
    if not user:
        return False
    try:
        user.token = json.dumps(payload, ensure_ascii=False) if payload else None
        user.updated_at = datetime.now()
        user.save()
        return True
    except Exception:
        return False


def find_user_by_token(token: str, token_type: str = "access") -> Optional[tuple]:
    if not token:
        return None
    token_key = "access_token" if token_type == "access" else "refresh_token"
    for user in User.select().where((User.is_active == True) & User.deleted_at.is_null(True)):
        if not user.token:
            continue
        try:
            payload = json.loads(user.token)
        except Exception:
            continue
        if isinstance(payload, dict) and payload.get(token_key) == token:
            return user, payload
    return None


def get_active_token_count() -> int:
    return User.select().where(((User.is_active == True) & User.deleted_at.is_null(True)) & (User.token.is_null(False))).count()


def verify_user_password(username: str, password: str, role: str = "user") -> tuple:
    user = get_user_by_username(username, role)
    if not user:
        return False, "用户不存在或未授权", None
    if not user.verify_password(password):
        return False, "密码错误", None
    return True, None, user


def reset_user_password(username: str, new_password: str) -> tuple:
    user = get_user_by_username(username)
    if not user:
        return False, "用户不存在"
    try:
        password_hash, salt = User.hash_password(new_password)
        user.password_hash = password_hash
        user.salt = salt
        user.token = None
        user.updated_at = datetime.now()
        user.save()
        return True, "密码重置成功"
    except Exception as exc:
        return False, f"重置密码失败: {exc}"


def create_user(username: str, password: str, api_key: str = None, roles: Iterable[str] = None):
    """创建账号并写入角色；缺省只开通聊天。"""
    password_hash, salt = User.hash_password(password)
    normalized = sort_roles(roles if roles is not None else [ROLE_CHAT])
    with db.atomic():
        user = User.create(
            username=username,
            password_hash=password_hash,
            salt=salt,
            api_key=api_key,
            is_active=True,
            role=to_compat_role(normalized),
        )
        for role in normalized:
            UserRole.create(user_id=user.id, role=role)
    return user


def get_user_api_key(username: str) -> str:
    user = get_user_by_username(username)
    return user.api_key if user else None


def get_user_browser_conf(username: str) -> Optional[str]:
    user = get_user_by_username(username)
    return user.browser_conf if user else None


#: 浏览器配置中保存的默认音色偏好键（普通用户专属，不写全局 VoiceAccountState）
BROWSER_CONF_DEFAULT_VOICE_KEY = "huiliao_default_voice_id"


def get_user_browser_conf_map(username: str) -> dict:
    """把 browser_conf JSON 解析为字典；非法内容按空字典处理。"""
    raw = get_user_browser_conf(username) or ""
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def set_user_browser_conf_value(username: str, key: str, value) -> bool:
    """只更新 browser_conf 中的单个键，保留其它配置。"""
    payload = get_user_browser_conf_map(username)
    payload[key] = value
    success, _ = set_user_browser_conf(username, json.dumps(payload, ensure_ascii=False))
    return success


def set_user_browser_conf(username: str, browser_conf: str) -> tuple[bool, str]:
    user = get_user_by_username(username)
    if not user:
        return False, "用户不存在"
    try:
        user.browser_conf = browser_conf
        user.updated_at = datetime.now()
        user.save()
        return True, "保存成功"
    except Exception as exc:
        return False, f"保存失败: {exc}"


def get_all_active_users() -> list:
    return [u.username for u in User.select().where((User.is_active == True) & User.deleted_at.is_null(True))]


# ---------------------------------------------------------------------------
# 角色（授权唯一来源：user_role 表）
# ---------------------------------------------------------------------------

def get_user_roles(user_id: int) -> list:
    """读取单个用户的角色列表，按固定顺序返回。"""
    if not user_id:
        return []
    rows = UserRole.select().where(UserRole.user_id == user_id)
    return sort_roles([row.role for row in rows])


def get_roles_for_users(user_ids: Iterable[int]) -> dict:
    """批量读取多个用户的角色，避免列表接口逐行查询。"""
    unique_ids = {int(uid) for uid in (user_ids or []) if uid}
    if not unique_ids:
        return {}
    grouped = {uid: [] for uid in unique_ids}
    for row in UserRole.select().where(UserRole.user_id.in_(unique_ids)):
        if row.role in ROLE_SET:
            grouped[row.user_id].append(row.role)
    return {uid: sort_roles(roles) for uid, roles in grouped.items()}


def replace_user_roles(user_id: int, roles: Iterable[str]) -> list:
    """原子替换用户角色，并同步兼容字段 ``User.role``。"""
    normalized = sort_roles(roles or [])
    with db.atomic():
        UserRole.delete().where(UserRole.user_id == user_id).execute()
        for role in normalized:
            UserRole.create(user_id=user_id, role=role)
        User.update(role=to_compat_role(normalized)).where(User.id == user_id).execute()
    return normalized


def count_active_admins(exclude_user_id: int = None) -> int:
    """统计启用管理员数量，用于保护最后一个启用管理员。"""
    query = (
        UserRole
        .select()
        .join(User, on=(User.id == UserRole.user_id))
        .where((UserRole.role == ROLE_ADMIN) & ((User.is_active == True) & User.deleted_at.is_null(True)))
    )
    if exclude_user_id is not None:
        query = query.where(User.id != int(exclude_user_id))
    return query.count()


def filter_user_ids_by_role(role: str, only_active: bool = False) -> list:
    """按成员关系筛选用户 ID（组合角色账号也能命中）。"""
    query = UserRole.select(UserRole.user_id).where(UserRole.role == role)
    user_ids = [row.user_id for row in query]
    if not user_ids:
        return []
    user_query = User.select(User.id).where(User.id.in_(user_ids))
    if only_active:
        user_query = user_query.where((User.is_active == True) & User.deleted_at.is_null(True))
    return [row.id for row in user_query]


def user_exists_in_db() -> bool:
    return User.select().count() > 0


def get_or_create_test_limit(user_ip: str, default_limit: int) -> TestLimit:
    record, _ = TestLimit.get_or_create(user_ip=user_ip, defaults={"user_count": 0, "limit": default_limit})
    return record


def increment_test_limit(user_ip: str, default_limit: int) -> tuple[int, int]:
    record = get_or_create_test_limit(user_ip, default_limit)
    record.user_count += 1
    record.save()
    return record.user_count, record.limit


def check_test_limit_exceeded(user_ip: str, default_limit: int) -> bool:
    record = get_or_create_test_limit(user_ip, default_limit)
    return record.user_count >= record.limit


def get_notification_list(status: str = None, limit: int = None, offset: int = None):
    query = Notification.select().order_by(Notification.priority.desc(), Notification.publish_time.desc())
    if status is not None:
        query = query.where(Notification.status == status)
    if limit is not None:
        query = query.limit(limit)
    if offset is not None:
        query = query.offset(offset)
    return [notification.to_dict() for notification in query.iterator()] if query.exists() else []


def get_notification_count(status: str = None):
    query = Notification.select()
    if status is not None:
        query = query.where(Notification.status == status)
    return query.count()


def get_active_notifications(limit: int = 10):
    return get_notification_list(status="active", limit=limit)


def create_notification(title: str, content: str, priority: int = 0, status: str = "active") -> Notification:
    return Notification.create(title=title, content=content, priority=priority, status=status)


def update_notification(notification_id: int, **kwargs) -> bool:
    try:
        notification = Notification.get_by_id(notification_id)
        if "title" in kwargs:
            notification.title = kwargs["title"]
        if "content" in kwargs:
            notification.content = kwargs["content"]
        if "priority" in kwargs:
            notification.priority = kwargs["priority"]
        if "status" in kwargs:
            notification.status = kwargs["status"]
        notification.updated_at = datetime.now()
        notification.save()
        return True
    except DoesNotExist:
        return False


def delete_notification(notification_id: int) -> bool:
    try:
        notification = Notification.get_by_id(notification_id)
        notification.delete_instance()
        return True
    except DoesNotExist:
        return False
