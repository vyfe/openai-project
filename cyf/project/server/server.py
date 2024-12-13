import configparser
import json
import logging
import os.path
import random
import time

import sqlitelog

from flask import Flask, request
from openai import OpenAI
from openai.types.chat import ChatCompletionUserMessageParam
from werkzeug.utils import secure_filename

app = Flask(__name__)
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}
conf = configparser.ConfigParser()
conf.read('conf/conf.ini')
url_list = conf['api']['api_host'].split(',')
user_list = {li for li in conf['common']['users'].split(',')}
model_list = {model_name for model_name in conf['model']}
url = url_list[random.randint(0, len(url_list) - 1)]

# 配置日志
logging.basicConfig(
    level=logging.INFO,  # 设置日志级别
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',  # 设置日志格式
    datefmt='%Y-%m-%d %H:%M:%S',  # 设置时间格式
    filename='app.log',  # 设置日志文件名
    filemode='w'  # 设置写入模式为覆盖
)

# 创建一个日志记录器
logger = logging.getLogger(__name__)

client=OpenAI(
    api_key=conf['api']['api_key'],
    base_url=url
)

# 检查文件扩展名是否允许
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/test', )
def health_check():
    logger.info(request.values)
    try:
        return json.dumps(request.values.to_dict()), 200
    except json.JSONDecodeError:
        return {"msg": "json no ok"}, 500

@app.route('/never_guess_my_usage/set_info', )
def data_check():
    logger.info(request.values)
    try:
        if request.values.get('param'):
            param = request.values.get('param').split(",")
            return sqlitelog.message_query(request.values.get('info'), param), 200
        else:
            return sqlitelog.message_query(request.values.get('info')), 200
    except json.JSONDecodeError:
        return {"msg": "json no ok"}, 500


@app.route('/never_guess_my_usage/download',  methods=['POST'])
def upload():
    # 检查请求中是否包含文件部分
    if 'file' not in request.files:
        return {"msg": "no file"}, 200
    file = request.files['file']
    if file.filename == '':
        return {"msg": "no filename"}, 200
    if file.content_length > 20 * 1024 * 1024:
        return {"msg": "more than 20M"}, 500
    # 检查文件是否符合条件
    if file and allowed_file(file.filename):
        filename = str(time.time()) + "-" + secure_filename(file.filename)
        file_fullname = os.path.join(conf["common"]["upload_dir"], filename)
        file.save(file_fullname)
        os.chmod(file_fullname, 0o755)
        # file.save(filename)
        # 加密混淆或定期清理？
        return {"content": f':4567/download/{filename}'}, 200
    else:
        # 上传文件并返回url的接口
        return {"msg": "文件格式问题"}, 500

@app.route('/never_guess_my_usage/split', methods=['POST', 'GET'])
def dialog():
    # 对话接口
    logger.info(request.values)
    try:
        # TODO 1 本地私钥解密
        # 2 用户名 + 上下文解析
        user = request.values.get('user')
        model = request.values.get('model')
        # 用户白名单、model名根据配置检查
        logging.info(f"user:{user}， model: {model}")
        if user not in user_list or model not in model_list:
            return {"msg": "not supported user or model"}, 500
        # TODO 客户端支持多轮对话
        dialogs = request.values.get('dialog')
        # 对话模式 single=单条 multi=上下文
        dialog_mode = request.values.get('dialog_mode', 'single')
        if dialog_mode == 'single':
            dialogvo = [ChatCompletionUserMessageParam(role="user", content=dialogs)]
        elif dialog_mode == 'multi':
            dialogvo = json.loads(dialogs)
        else:
            return {"msg": "not supported dialog_mode"}, 500
        # 功能测试
        result = client.chat.completions.create(
            model=model,
            messages=dialogvo,
            max_completion_tokens=8192
        )
        # TODO 需要统计token数（使用tiktoken），并截断的会话?
        # 4 sqlite3数据库写日志：用户名+token数+raw msg
        tokens = result.usage.total_tokens
        logger.info(result)
        sqlitelog.set_log(user, tokens, model, json.dumps(result.to_dict()))
        # 5 dialog组装：上下文+本次问题，返回答案
        sqlitelog.set_dialog(user, dialogs, model,
                             json.dumps(dialogvo + [result.choices[0].message.to_dict()]))
        # 仅返回role和content
        return {"role": result.choices[0].message.role, "content": result.choices[0].message.content}, 200
    except json.JSONDecodeError:
        return {"msg": "api return json not ok"}, 500

if __name__ == '__main__':
    # 若不存在sqlite3 db，初始化
    sqlitelog.init_db()
    # 上传文件夹初始化
    # if not os.path.exists(conf["common"]["upload_dir"]):
    #     os.makedirs(conf["common"]["upload_dir"])
    app.run(host='0.0.0.0', port=39997)