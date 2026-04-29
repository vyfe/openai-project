# 日志与数据访问兼容层
import json
from datetime import datetime, date
from typing import Optional

from peewee import DoesNotExist, TextField
from playhouse.migrate import SqliteMigrator, migrate

from db import conf, db
from models import (
    ChildConversation,
    ConversationRound,
    Dialog,
    Log,
    MasterConversation,
    ModelMeta,
    Notification,
    RoundCell,
    SystemPrompt,
    TestLimit,
    User,
)


# ==============================
# DB Init / Migration
# ==============================

def init_db():
    db.connect(reuse_if_open=True)
    db.create_tables(
        [
            Log,
            Dialog,
            ModelMeta,
            SystemPrompt,
            TestLimit,
            User,
            Notification,
            MasterConversation,
            ChildConversation,
            ConversationRound,
            RoundCell,
        ],
        safe=True,
    )
    ensure_schema()


def ensure_schema():
    """在启动时补齐缺失字段（仅增量列，不做破坏性变更）"""
    try:
        table_name = User._meta.table_name
        columns = {col.name for col in db.get_columns(table_name)}
        missing = []
        if 'browser_conf' not in columns:
            missing.append(('browser_conf', TextField(null=True)))
        if 'token' not in columns:
            missing.append(('token', TextField(null=True)))

        if missing:
            migrator = SqliteMigrator(db)
            for column_name, field in missing:
                migrate(migrator.add_column(table_name, column_name, field))
            print(f"[db] 已补齐字段: {', '.join(name for name, _ in missing)}")
    except Exception as e:
        print(f"[db] 自动更新表结构失败: {e}")


# ==============================
# Legacy chat log/dialog helpers
# ==============================

def set_log(user: str, usage: int, model: str, text: str):
    Log.create(username=user, usage=usage, modelname=model, request_text=text)


def set_dialog(user: str, model: str, chattype: str, dialog_name: str, context: str, id: int = None):
    time_str = datetime.now().strftime("%Y-%m-%d")
    if id is not None:
        Dialog.update(modelname=model, dialog_name=dialog_name, start_date=time_str, context=context).where(Dialog.id == id).execute()
        return id
    return Dialog.replace(
        username=user,
        chattype=chattype,
        modelname=model,
        dialog_name=dialog_name,
        start_date=time_str,
        context=context,
    ).execute()


def get_dialog_list(user: str, date_from: date):
    query = (
        Dialog.select(Dialog.id, Dialog.username, Dialog.chattype, Dialog.modelname, Dialog.dialog_name, Dialog.start_date)
        .where(Dialog.username == user, Dialog.start_date >= date_from)
        .order_by(Dialog.id.desc())
    )
    if query.exists():
        return [dialog for dialog in query.dicts().iterator()]
    return []


def get_dialog_context(user: str, id: int):
    try:
        return Dialog.get(Dialog.username == user, Dialog.id == id)
    except DoesNotExist:
        return None


def delete_dialogs(user: str, dialog_ids: list) -> int:
    if not dialog_ids:
        return 0
    query = Dialog.delete().where((Dialog.username == user) & (Dialog.id.in_(dialog_ids)))
    return query.execute()


def update_dialog_title(user: str, dialog_id: int, new_title: str) -> bool:
    try:
        rows_modified = Dialog.update(dialog_name=new_title).where((Dialog.username == user) & (Dialog.id == dialog_id)).execute()
        return rows_modified > 0
    except Exception as e:
        print(f"更新对话标题时发生错误: {e}")
        return False


# ==============================
# Model meta / prompt helpers
# ==============================

def get_model_meta_list(model_names: list = None, recommend: bool = None, status_valid: bool = None):
    query = ModelMeta.select()

    if model_names is not None:
        query = query.where(ModelMeta.model_name.in_(model_names))
    if recommend is not None:
        query = query.where(ModelMeta.recommend == recommend)
    if status_valid is not None:
        query = query.where(ModelMeta.status_valid == status_valid)

    if query.exists():
        return [model for model in query.dicts().iterator()]
    return []


def get_system_prompt_list(status_valid: bool = None):
    query = SystemPrompt.select()
    if status_valid is not None:
        query = query.where(SystemPrompt.status_valid == status_valid)
    if query.exists():
        return [prompt for prompt in query.dicts().iterator()]
    return []


def get_system_prompts_by_group():
    query = SystemPrompt.select().where(SystemPrompt.status_valid == True)
    grouped_prompts = {}
    for prompt in query.dicts().iterator():
        group = prompt['role_group']
        if group not in grouped_prompts:
            grouped_prompts[group] = []
        grouped_prompts[group].append(
            {
                'id': prompt['id'],
                'role_name': prompt['role_name'],
                'role_desc': prompt['role_desc'],
            }
        )
    return grouped_prompts


def get_system_prompt_by_id(prompt_id: int) -> dict:
    try:
        prompt = SystemPrompt.get_by_id(prompt_id)
        if not prompt or not prompt.status_valid:
            return None
        return {
            'id': prompt.id,
            'role_name': prompt.role_name,
            'role_desc': prompt.role_desc,
            'role_content': prompt.role_content,
        }
    except DoesNotExist:
        return None
    except Exception as e:
        print(f"获取系统提示词失败: {str(e)}")
        return None


# ==============================
# Generic SQL helper
# ==============================

def message_query(sql: str, params=None):
    cursor = db.execute_sql(sql, params)
    columns = [desc[0] for desc in cursor.description] if cursor.description else []
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


# ==============================
# User/TestLimit auth helpers
# ==============================

def get_or_create_test_limit(user_ip: str, default_limit: int) -> TestLimit:
    record, _created = TestLimit.get_or_create(user_ip=user_ip, defaults={'user_count': 0, 'limit': default_limit})
    return record


def increment_test_limit(user_ip: str, default_limit: int) -> tuple[int, int]:
    record = get_or_create_test_limit(user_ip, default_limit)
    record.user_count += 1
    record.save()
    return record.user_count, record.limit


def check_test_limit_exceeded(user_ip: str, default_limit: int) -> bool:
    record = get_or_create_test_limit(user_ip, default_limit)
    return record.user_count >= record.limit


def get_user_by_username(username: str, role: str = None):
    try:
        if not role:
            return User.get(User.username == username, User.is_active == True)
        return User.get(User.username == username, User.is_active == True, User.role == role)
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


def find_user_by_token(token: str, token_type: str = 'access') -> Optional[tuple]:
    if not token:
        return None
    users = User.select().where(User.is_active == True)
    token_key = 'access_token' if token_type == 'access' else 'refresh_token'
    for user in users:
        if not user.token:
            continue
        try:
            payload = json.loads(user.token)
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        if payload.get(token_key) == token:
            return user, payload
    return None


def get_active_token_count() -> int:
    return User.select().where((User.is_active == True) & (User.token.is_null(False))).count()


def verify_user_password(username: str, password: str, role: str = 'user') -> tuple:
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
        user.updated_at = datetime.now()
        user.save()
        return True, "密码重置成功"
    except Exception as e:
        return False, f"重置密码失败: {str(e)}"


def create_user(username: str, password: str, api_key: str = None):
    password_hash, salt = User.hash_password(password)
    return User.create(username=username, password_hash=password_hash, salt=salt, api_key=api_key, is_active=True)


def get_user_api_key(username: str) -> str:
    user = get_user_by_username(username)
    return user.api_key if user else None


def get_user_browser_conf(username: str) -> Optional[str]:
    user = get_user_by_username(username)
    return user.browser_conf if user else None


def set_user_browser_conf(username: str, browser_conf: str) -> tuple[bool, str]:
    user = get_user_by_username(username)
    if not user:
        return False, "用户不存在"
    try:
        user.browser_conf = browser_conf
        user.updated_at = datetime.now()
        user.save()
        return True, "保存成功"
    except Exception as e:
        return False, f"保存失败: {str(e)}"


def get_all_active_users() -> list:
    return [u.username for u in User.select().where(User.is_active == True)]


def user_exists_in_db() -> bool:
    return User.select().count() > 0


# ==============================
# Notification helpers
# ==============================

def get_notification_list(status: str = None, limit: int = None, offset: int = None):
    query = Notification.select().order_by(Notification.priority.desc(), Notification.publish_time.desc())
    if status is not None:
        query = query.where(Notification.status == status)
    if limit is not None:
        query = query.limit(limit)
    if offset is not None:
        query = query.offset(offset)

    if query.exists():
        return [notification.to_dict() for notification in query.iterator()]
    return []


def get_notification_count(status: str = None):
    query = Notification.select()
    if status is not None:
        query = query.where(Notification.status == status)
    return query.count()


def get_active_notifications(limit: int = 10):
    return get_notification_list(status='active', limit=limit)


def create_notification(title: str, content: str, priority: int = 0, status: str = 'active') -> Notification:
    return Notification.create(title=title, content=content, priority=priority, status=status)


def update_notification(notification_id: int, **kwargs) -> bool:
    try:
        notification = Notification.get_by_id(notification_id)
        if 'title' in kwargs:
            notification.title = kwargs['title']
        if 'content' in kwargs:
            notification.content = kwargs['content']
        if 'priority' in kwargs:
            notification.priority = kwargs['priority']
        if 'status' in kwargs:
            notification.status = kwargs['status']

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


# ==============================
# New conversation (A role scope)
# ==============================

def create_master_conversation(owner: str, title: str, session_type: str = 'single', active_models: Optional[list] = None):
    """[V2会话] 创建主会话（MasterConversation）。"""
    return MasterConversation.create(
        owner=owner,
        title=title,
        session_type=session_type,
        active_models_json=json.dumps(active_models or [], ensure_ascii=False),
    )


def create_child_conversation(master_id: int, model_id: str, status: str = 'active', backend_dialog_id: Optional[int] = None, created_round_index: int = 0):
    """[V2会话] 在主会话下创建子会话（ChildConversation）。"""
    return ChildConversation.create(
        master=master_id,
        model_id=model_id,
        status=status,
        backend_dialog_id=backend_dialog_id,
        created_round_index=created_round_index,
    )


def create_conversation_round(master_id: int, round_index: int, user_prompt: str, attachments: Optional[list] = None):
    """[V2会话] 创建回合（ConversationRound）。"""
    return ConversationRound.create(
        master=master_id,
        round_index=round_index,
        user_prompt=user_prompt,
        attachments_json=json.dumps(attachments or [], ensure_ascii=False),
    )


def upsert_round_cell(round_id: int, child_id: int, cell_status: str = 'idle', assistant_output: Optional[str] = None, error_json: Optional[str] = None, latency_ms: Optional[int] = None, request_id: Optional[str] = None):
    """[V2会话] 创建或更新回合单元（RoundCell）。用于流式增量写入与单元重试结果回填。"""
    existing = (
        RoundCell.select()
        .where((RoundCell.round == round_id) & (RoundCell.child == child_id))
        .first()
    )
    if existing:
        RoundCell.update(
            cell_status=cell_status,
            assistant_output=assistant_output,
            error_json=error_json,
            latency_ms=latency_ms,
            request_id=request_id,
            updated_at=datetime.now(),
        ).where(RoundCell.id == existing.id).execute()
        return RoundCell.get_by_id(existing.id)

    return RoundCell.create(
        round=round_id,
        child=child_id,
        cell_status=cell_status,
        assistant_output=assistant_output,
        error_json=error_json,
        latency_ms=latency_ms,
        request_id=request_id,
        updated_at=datetime.now(),
    )
