# 日志文件
import configparser
import json
from datetime import datetime, date
import hashlib
import secrets

from peewee import *

conf = configparser.ConfigParser()
conf.read('conf/conf.ini')
db = SqliteDatabase(conf['log']['sqlite3_file'])

class Log(Model):
    username = CharField()  # 用户名字段
    modelname = CharField()  # 模型名字段
    usage = IntegerField()  # 用量字段
    request_text = TextField()  # 请求原文字段

    class Meta:
        database = db  # 指定数据库

# 会话表模型
class Dialog(Model):
    username = CharField()  # 用户名字段
    chattype = CharField()  # 对话类型
    modelname = CharField()  # 模型名字段
    dialog_name = CharField()  # 会话名字段
    start_date = DateField()  # 发起时间字段
    context = TextField()  # 上下文字段

    class Meta:
        database = db  # 指定数据库
        indexes = (
            (('username', 'chattype', 'dialog_name'), True),  # 定义唯一索引，假设对话名不能重复吧
        )
# 模型标记
class ModelMeta(Model):
    model_name = CharField()  # 模型名称
    model_desc = CharField()  # 模型用途描述
    model_type = IntegerField(default=1) # 模型的模态,1-文本，2-图像
    recommend = BooleanField()  # 是否推荐
    status_valid = BooleanField()  # 是否对外开放
    model_grp = CharField(default='')  # 模型分组

    class Meta:
        database = db  # 指定数据库
        indexes = (
            (('model_name', ), True),  # 定义唯一索引，确保模型名称不重复
        )

    def to_dict(self):
        """将模型实例转换为字典格式"""
        return {
            'id': self.id,
            'model_name': self.model_name,
            'model_desc': self.model_desc,
            'model_type': self.model_type,
            'recommend': self.recommend,
            'status_valid': self.status_valid,
            'model_grp': self.model_grp
        }
# system高级预设
class SystemPrompt(Model):
    role_name = CharField()  # 角色名称
    role_group = CharField()  # 角色分组
    role_desc = CharField()  # 角色描述
    role_content = TextField() # 角色提示词
    status_valid = BooleanField()  # 是否对外开放

    class Meta:
        database = db  # 指定数据库
        indexes = (
            (('role_name', 'role_group'), True),  # 定义唯一索引，确保角色名称不重复
        )

    def to_dict(self):
        """将模型实例转换为字典格式"""
        return {
            'id': self.id,
            'role_name': self.role_name,
            'role_group': self.role_group,
            'role_desc': self.role_desc,
            'role_content': self.role_content,
            'status_valid': self.status_valid
        }

class TestLimit(Model):
    user_ip = CharField()  # 用户ip
    user_count = IntegerField(default=0)  # 使用次数
    limit = IntegerField() # 上限

    class Meta:
        database = db  # 指定数据库
        indexes = (
            (('user_ip',), True),  # 定义唯一索引，确保每个IP只有一条记录
        )

class User(Model):
    username = CharField(unique=True)      # 用户名
    password_hash = CharField()            # 密码哈希值
    salt = CharField()                     # 密码盐值
    api_key = CharField(null=True)         # 用户专属API密钥
    role = CharField(default='user') # 账户是否激活
    is_active = BooleanField(default=True) # 账户是否激活
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

class Notification(Model):
    title = CharField()  # 通知标题
    content = TextField()  # 通知内容
    publish_time = DateTimeField(default=datetime.now)  # 发布时间
    status = CharField(default='active')  # 状态：active-有效，inactive-无效
    priority = IntegerField(default=0)  # 优先级，数字越大优先级越高
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)

    class Meta:
        database = db
        indexes = (
            (('status',), False),  # 状态索引
            (('priority',), False),  # 优先级索引
            (('publish_time',), False),  # 发布时间索引
        )

    def to_dict(self):
        """将通知实例转换为字典格式"""
        return {
            'id': self.id,
            'title': self.title,
            'content': self.content,
            'publish_time': self.publish_time.strftime('%Y-%m-%d %H:%M:%S') if self.publish_time else None,
            'status': self.status,
            'priority': self.priority,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S') if self.updated_at else None
        }

def init_db():
    # 创建表
    db.connect()
    db.create_tables([Log, Dialog, ModelMeta, SystemPrompt, TestLimit, User, Notification], safe=True)


def get_or_create_test_limit(user_ip: str, default_limit: int) -> TestLimit:
    """获取或创建 IP 限制记录"""
    record, created = TestLimit.get_or_create(
        user_ip=user_ip,
        defaults={'user_count': 0, 'limit': default_limit}
    )
    return record


def increment_test_limit(user_ip: str, default_limit: int) -> tuple[int, int]:
    """增加计数并返回 (当前计数, 限制值)"""
    record = get_or_create_test_limit(user_ip, default_limit)
    record.user_count += 1
    record.save()
    return record.user_count, record.limit


def check_test_limit_exceeded(user_ip: str, default_limit: int) -> bool:
    """检查是否超过限制（不增加计数）"""
    record = get_or_create_test_limit(user_ip, default_limit)
    return record.user_count >= record.limit

def set_log(user: str, usage: int, model: str, text: str):
    Log.create(username=user, usage=usage, modelname=model, request_text=text)

def set_dialog(user: str, model: str, chattype: str, dialog_name: str, context: str, id: int = None):
    time_str=datetime.now().strftime("%Y-%m-%d")
    if id is not None:
        # 更新现有对话
        Dialog.update(modelname=model, dialog_name=dialog_name, start_date=time_str, context=context).where(Dialog.id == id).execute()
        return id  # 返回更新的对话ID
    else:
        # 创建新对话
        return (Dialog.replace(username=user, chattype=chattype, modelname=model, dialog_name=dialog_name, start_date=time_str, context=context).execute())

def get_dialog_list(user: str, date: date):
    query = (Dialog.select(Dialog.id, Dialog.username, Dialog.chattype, Dialog.modelname, Dialog.dialog_name, Dialog.start_date)
             .where(Dialog.username == user, Dialog.start_date >= date)
             .order_by(Dialog.id.desc()))
    if query.exists():
        return [dialog for dialog in query.dicts().iterator()]
    else:
        return []

def get_dialog_context(user: str, id: int):
    try:
        query = Dialog.get(Dialog.username == user, Dialog.id == id)
        return query
    except DoesNotExist:
        return None


def delete_dialogs(user: str, dialog_ids: list) -> int:
    """删除指定用户的多个会话，返回实际删除数量"""
    if not dialog_ids:
        return 0
    query = Dialog.delete().where(
        (Dialog.username == user) & (Dialog.id.in_(dialog_ids))
    )
    return query.execute()


def update_dialog_title(user: str, dialog_id: int, new_title: str) -> bool:
    """更新指定对话的标题"""
    try:
        query = Dialog.update(dialog_name=new_title).where(
            (Dialog.username == user) & (Dialog.id == dialog_id)
        )
        rows_modified = query.execute()
        return rows_modified > 0
    except Exception as e:
        print(f"更新对话标题时发生错误: {e}")  # 添加调试信息
        return False


def get_model_meta_list(model_names: list = None, recommend: bool = None, status_valid: bool = None):
    """
    查询模型元数据列表，支持复合条件查询，所有参数均为可选项
    :param model_name: 模型名称（可选）
    :param recommend: 是否推荐（可选）
    :param status_valid: 是否对外有效（可选）
    :return: 符合条件的模型元数据列表
    """
    query = ModelMeta.select()

    # 根据参数添加过滤条件
    if model_names is not None:
        query = query.where(ModelMeta.model_name.in_(model_names))

    if recommend is not None:
        query = query.where(ModelMeta.recommend == recommend)

    if status_valid is not None:
        query = query.where(ModelMeta.status_valid == status_valid)

    # 返回字典格式的结果列表
    if query.exists():
        return [model for model in query.dicts().iterator()]
    else:
        return []

def get_system_prompt_list(status_valid: bool = None):
    """
    查询系统提示词列表
    """
    query = SystemPrompt.select()

    if status_valid is not None:
        query = query.where(SystemPrompt.status_valid == status_valid)

    # 返回字典格式的结果列表
    if query.exists():
        return [prompt for prompt in query.dicts().iterator()]
    else:
        return []


def get_system_prompts_by_group():
    """
    按role_group分类聚合系统提示词
    返回格式: { "group_name": [{"id": ..., "role_name": ..., "role_desc": ...}, ...] }
    注意：不再返回 role_content，由前端通过 ID 请求获取
    """
    query = SystemPrompt.select().where(SystemPrompt.status_valid == True)

    grouped_prompts = {}
    for prompt in query.dicts().iterator():
        group = prompt['role_group']
        if group not in grouped_prompts:
            grouped_prompts[group] = []

        # 只返回需要的字段，移除 role_content 以增强安全性
        grouped_prompts[group].append({
            'id': prompt['id'],  # 新增 id 字段
            'role_name': prompt['role_name'],
            'role_desc': prompt['role_desc']
        })

    return grouped_prompts


def get_system_prompt_by_id(prompt_id: int) -> dict:
    """
    根据 ID 获取系统提示词内容
    返回: {'id': ..., 'role_name': ..., 'role_desc': ..., 'role_content': ...}
    如果提示词不存在或不可用，返回 None
    """
    try:
        prompt = SystemPrompt.get_by_id(prompt_id)
        if not prompt or not prompt.status_valid:
            return None
        return {
            'id': prompt.id,
            'role_name': prompt.role_name,
            'role_desc': prompt.role_desc,
            'role_content': prompt.role_content
        }
    except DoesNotExist:
        return None
    except Exception as e:
        app.logger.error(f"获取系统提示词失败: {str(e)}")
        return None


def message_query(sql: str, params=None):
    """执行SQL查询，返回结果列表"""
    cursor = db.execute_sql(sql, params)
    # 获取列名
    columns = [desc[0] for desc in cursor.description] if cursor.description else []
    # 将结果转换为字典列表
    results = [dict(zip(columns, row)) for row in cursor.fetchall()]
    return results

def get_user_by_username(username: str, role: str = None):
    try:
        if not role :
            return User.get(User.username == username, User.is_active == True)
        else:
            return User.get(User.username == username, User.is_active == True, User.role == role)
    except DoesNotExist:
        return None

def verify_user_password(username: str, password: str, role: str = 'user') -> tuple:
    user = get_user_by_username(username, role)
    if not user:
        return False, "用户不存在或未授权", None
    if not user.verify_password(password):
        return False, "密码错误", None
    return True, None, user


def reset_user_password(username: str, new_password: str) -> tuple:
    """重置用户密码"""
    user = get_user_by_username(username)
    if not user:
        return False, "用户不存在"

    try:
        # 生成新密码哈希
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
    return User.create(username=username, password_hash=password_hash,
                       salt=salt, api_key=api_key, is_active=True)

def get_user_api_key(username: str) -> str:
    user = get_user_by_username(username)
    return user.api_key if user else None

def get_all_active_users() -> list:
    return [u.username for u in User.select().where(User.is_active == True)]

def user_exists_in_db() -> bool:
    return User.select().count() > 0


def get_notification_list(status: str = None, limit: int = None, offset: int = None):
    """
    查询通知公告列表
    :param status: 状态过滤（可选）
    :param limit: 限制数量（可选）
    :param offset: 偏移量（可选）
    :return: 通知列表
    """
    query = Notification.select().order_by(Notification.priority.desc(), Notification.publish_time.desc())

    if status is not None:
        query = query.where(Notification.status == status)

    if limit is not None:
        query = query.limit(limit)

    if offset is not None:
        query = query.offset(offset)

    if query.exists():
        return [notification.to_dict() for notification in query.iterator()]
    else:
        return []


def get_notification_count(status: str = None):
    """
    获取通知公告总数
    :param status: 状态过滤（可选）
    :return: 通知总数
    """
    query = Notification.select()

    if status is not None:
        query = query.where(Notification.status == status)

    return query.count()


def get_active_notifications(limit: int = 10):
    """
    获取有效的通知公告
    :param limit: 限制数量
    :return: 有效通知列表
    """
    return get_notification_list(status='active', limit=limit)


def create_notification(title: str, content: str, priority: int = 0, status: str = 'active') -> Notification:
    """
    创建通知公告
    :param title: 通知标题
    :param content: 通知内容
    :param priority: 优先级
    :param status: 状态
    :return: 通知实例
    """
    return Notification.create(
        title=title,
        content=content,
        priority=priority,
        status=status
    )


def update_notification(notification_id: int, **kwargs) -> bool:
    """
    更新通知公告
    :param notification_id: 通知ID
    :param kwargs: 更新的字段
    :return: 是否成功
    """
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
    """
    删除通知公告
    :param notification_id: 通知ID
    :return: 是否成功
    """
    try:
        notification = Notification.get_by_id(notification_id)
        notification.delete_instance()
        return True
    except DoesNotExist:
        return False



