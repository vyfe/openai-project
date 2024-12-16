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

def init_db():
    # 创建表
    db.connect()
    db.create_tables([Log, Dialog])

def set_log(user: str, usage: int, model: str, text: str):
    Log.create(username=user, usage=usage, modelname=model, request_text=text)

def set_dialog(user: str, model: str, chattype: str, dialog_name: str, context: str):
    time_str=datetime.now().strftime("%Y-%m-%d")
    Dialog.replace(username=user, chattype=chattype, modelname=model, dialog_name=dialog_name, start_date=time_str, context=context).execute()

def get_dialog_list(user: str, date: date):
    query = (Dialog.select(Dialog.username, Dialog.chattype, Dialog.dialog_name, Dialog.start_date)
             .where(Dialog.username == user, Dialog.start_date >= date))
    if query.exists():
        return [dialog for dialog in query.dicts().iterator()]
    else:
        return []

def get_dialog_context(user: str, id: int):
    try:
        query = Dialog.get(Dialog.username == user, Dialog.id == id).context
        return query
    except DoesNotExist:
        return []


def message_query(sql: str, params=None):
    return json.dumps(db.execute_sql(sql, params).fetchall())





