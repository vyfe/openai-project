# 日志文件
import configparser
import json
from datetime import datetime, date

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
    recommend = BooleanField()  # 是否推荐
    status_valid = BooleanField()  # 是否对外开放

    class Meta:
        database = db  # 指定数据库
        indexes = (
            (('model_name',), True),  # 定义唯一索引，确保模型名称不重复
        )

    def to_dict(self):
        """将模型实例转换为字典格式"""
        return {
            'id': self.id,
            'model_name': self.model_name,
            'model_desc': self.model_desc,
            'recommend': self.recommend,
            'status_valid': self.status_valid
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

def init_db():
    # 创建表
    db.connect()
    db.create_tables([Log, Dialog, ModelMeta, SystemPrompt], safe=True)

def set_log(user: str, usage: int, model: str, text: str):
    Log.create(username=user, usage=usage, modelname=model, request_text=text)

def set_dialog(user: str, model: str, chattype: str, dialog_name: str, context: str):
    time_str=datetime.now().strftime("%Y-%m-%d")
    Dialog.replace(username=user, chattype=chattype, modelname=model, dialog_name=dialog_name, start_date=time_str, context=context).execute()

def get_dialog_list(user: str, date: date):
    query = (Dialog.select(Dialog.id, Dialog.username, Dialog.chattype, Dialog.dialog_name, Dialog.start_date)
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
        return []


def delete_dialogs(user: str, dialog_ids: list) -> int:
    """删除指定用户的多个会话，返回实际删除数量"""
    if not dialog_ids:
        return 0
    query = Dialog.delete().where(
        (Dialog.username == user) & (Dialog.id.in_(dialog_ids))
    )
    return query.execute()


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
    返回格式: { "group_name": [{"role_name": ..., "role_desc": ..., "role_content": ...}, ...] }
    """
    query = SystemPrompt.select().where(SystemPrompt.status_valid == True)

    grouped_prompts = {}
    for prompt in query.dicts().iterator():
        group = prompt['role_group']
        if group not in grouped_prompts:
            grouped_prompts[group] = []

        # 只返回需要的字段
        grouped_prompts[group].append({
            'role_name': prompt['role_name'],
            'role_desc': prompt['role_desc'],
            'role_content': prompt['role_content']
        })

    return grouped_prompts


def message_query(sql: str, params=None):
    return json.dumps(db.execute_sql(sql, params).fetchall())





