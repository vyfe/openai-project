import configparser
import json
import logging
import os.path
import random
import sys
import time
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler

import requests
from flask import Flask, request
from openai import OpenAI
from openai.types.chat import ChatCompletionUserMessageParam

import sqlitelog

app = Flask(__name__)
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'ppt', 'pptx'}
conf = configparser.ConfigParser()
conf.read('conf/conf.ini', encoding="UTF-8")
url_list = conf['api']['api_host'].split(',')
user_list = {li for li in conf['common']['users'].split(',')}
model_list = {model_name: conf['model'][model_name] for model_name in conf['model']}
url = url_list[random.randint(0, len(url_list) - 1)]

# 配置日志
logging.basicConfig(
    level=logging.INFO,  # 设置日志级别
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',  # 设置日志格式
    datefmt='%Y-%m-%d %H:%M:%S',  # 设置时间格式
    filemode='a'  # 设置写入模式为覆盖
)

_debug=False
if _debug:
    handler = logging.StreamHandler(stream=sys.stdout)
else:
    handler = RotatingFileHandler('app.log', maxBytes=10 * 1024 * 1024, backupCount=5, encoding="UTF-8")
    handler.setLevel(logging.INFO)
app.logger.addHandler(handler)

clients=[OpenAI(api_key=conf['api']['api_key'], base_url=url) for url in  url_list]

def random_client() -> OpenAI:
    return clients[random.randint(0, len(url_list) - 1)]

# 检查文件扩展名是否允许
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/never_guess_my_usage/test', )
def health_check():
    app.logger.info(request.values)
    try:
        return json.dumps(request.values.to_dict()), 200
    except json.JSONDecodeError:
        return {"msg": "json no ok"}, 200

@app.route('/never_guess_my_usage/set_info', )
def data_check():
    app.logger.info(request.values)
    try:
        if request.values.get('param'):
            param = request.values.get('param').split(",")
            return sqlitelog.message_query(request.values.get('info'), param), 200
        else:
            return sqlitelog.message_query(request.values.get('info')), 200
    except json.JSONDecodeError:
        return {"msg": "json no ok"}, 200


@app.route('/never_guess_my_usage/download',  methods=['POST'])
def upload():
    # 检查请求中是否包含文件部分
    if 'file' not in request.files:
        return {"msg": "no file"}, 200
    file = request.files['file']
    if file.filename == '':
        return {"msg": "no filename"}, 200
    if file.content_length > 20 * 1024 * 1024:
        return {"msg": "more than 20M"}, 200
    # 检查文件是否符合条件
    if file and allowed_file(file.filename):
        filename = str(time.time()) + "-" + file.filename
        file_fullname = os.path.join(conf["common"]["upload_dir"], filename)
        file.save(file_fullname)
        os.chmod(file_fullname, 0o755)
        # file.save(filename)
        # 加密混淆或定期清理？
        return {"content": f':4567/download/{filename}'}, 200
    else:
        # 上传文件并返回url的接口
        return {"msg": "文件格式问题"}, 200

@app.route('/never_guess_my_usage/split', methods=['POST', 'GET'])
def dialog():
    # 对话接口
    app.logger.info(request.values)
    try:
        # TODO 1 本地私钥解密
        # 2 用户名 + 上下文解析
        user = request.values.get('user')
        model = request.values.get('model')
        # 用户白名单、model名根据配置检查
        logging.info(f"user:{user}， model: {model}")
        if user not in user_list or model not in model_list:
            return {"msg": "not supported user or model"}, 200
        dialogs = request.values.get('dialog')
        # 对话模式 single=单条 multi=上下文
        dialog_mode = request.values.get('dialog_mode', 'single')
        if dialog_mode == 'single':
            dialogvo = [ChatCompletionUserMessageParam(role="user", content=dialogs)]
            title=dialogs
        elif dialog_mode == 'multi':
            dialogvo = json.loads(dialogs)
            title=dialogvo[0]["content"]
        else:
            return {"msg": "not supported dialog_mode"}, 200
        result = random_client().chat.completions.create(
            model=model_list[model],
            messages=dialogvo,
            max_tokens=8192
        )
        # 4 sqlite3数据库写日志：用户名+token数+raw msg
        tokens = result.usage.total_tokens
        app.logger.info(result)
        sqlitelog.set_log(user, tokens, model_list[model], json.dumps(result.to_dict()))
        # 5 dialog组装：上下文+本次问题，返回答案
        sqlitelog.set_dialog(user, model_list[model], "chat",  title,
                             json.dumps(dialogvo + [result.choices[0].message.to_dict()]))
        # 仅返回role和content
        return {"role": result.choices[0].message.role, "content": result.choices[0].message.content}, 200
    except json.JSONDecodeError:
        return {"msg": "api return json not ok"}, 200

@app.route('/never_guess_my_usage/split_pic', methods=['POST'])
def dialog_pic():
    # 图片对话接口
    app.logger.info(request.values)
    try:
        # TODO 1 本地私钥解密
        # 2 用户名 + 上下文解析
        user = request.values.get('user')
        model = request.values.get('model')
        # 用户白名单、model名根据配置检查
        logging.info(f"user:{user}， model: {model}")
        if user not in user_list or model not in model_list:
            return {"msg": "not supported user or model"}, 200
        # 对话模式 single=单条 multi=上下文/编辑
        dialogs = request.values.get('dialog')
        dialog_mode = request.values.get('dialog_mode', 'single')
        if dialog_mode == 'single':
            dialogvo = {"role": "user", "desc": dialogs}
            title=dialogs
            result = random_client().images.generate(
                model=model_list[model],
                prompt=dialogs,
                n=1,
                response_format="url",
                size="1024x1024",
                timeout=60
            )
        elif dialog_mode == 'multi':
            dialogvo = json.loads(dialogs)
            title = dialogvo[0]["desc"]
            # 将连接图片转为本地的file对象
            local_file = str(dialogvo[-2]["url"]).replace(":4567/download", "/home/www/downloads")
            with open(local_file, "rb") as image_file:
                result = random_client().images.edit(
                    model=model_list[model],
                    image=image_file,
                    prompt=dialogvo[-1]["desc"],
                    n=1,
                    response_format="url",
                    size="1024x1024"
                )
        else:
            return {"msg": "not supported dialog_mode"}, 200

        app.logger.info(result)
        # 返回的图片url需要转储到本地的downloads/image中，再生成新的链接/日志/对话记录，同时在客户端展示图片和文件url
        # 暂时支持生成1张
        desc = result.data[0].revised_prompt
        # 保存到本地后使用本地的下载url
        response = requests.get(result.data[0].url)
        if response.status_code == 200:
            filename = (model_list[model] + "-" + str(time.time()) + "-"
                        + os.path.basename(result.data[0].url).split("?")[0])
            save_path = os.path.join(conf["common"]["upload_dir"], "images/" + filename)
            with open(save_path, "wb") as pic:
                pic.write(response.content)
            os.chmod(save_path, 0o755)
            logging.info(f"pic saving:{save_path}")
        else:
            return {"msg": "error requesting pic server"}, 501
        result_save = {"role": "assistant", "desc": desc, "url": f':4567/download/images/{filename}'}
        # 日志和对话单独记录，dialog中新增model-name字段？
        # 图片按条数统计
        sqlitelog.set_log(user, 1, model_list[model], json.dumps(result.to_dict()))
        # 5 dialog组装：上下文+本次问题回答
        if not isinstance(dialogvo, list):
            dialogvo = [dialogvo]
        dialogvo.append(result_save)
        sqlitelog.set_dialog(user, model_list[model],"pic", title, json.dumps(dialogvo))
        return result_save, 200
    except json.JSONDecodeError:
        return {"msg": "api return json not ok"}, 200

@app.route('/never_guess_my_usage/split_his', methods=['POST'])
def dialog_his():
    # 根据用户名获取3日内历史纪录，[{日期+标题、类型}], 按id倒排
    user = request.values.get('user')
    app.logger.info(user)
    if user not in user_list:
        return {"msg": "not supported user or model"}, 200
    min_time_str = (datetime.now() - timedelta(days=3)).date()
    dialog_list = sqlitelog.get_dialog_list(user, min_time_str)
    dialog_list = [ {**item, "start_date": item["start_date"].strftime("%Y-%m-%d")} for item in dialog_list]
    return {"content": dialog_list}, 200

@app.route('/never_guess_my_usage/split_his_content', methods=['POST'])
def dialog_content():
    try:
        # 根据用户名+id获取历史纪录详情context
        user = request.values.get('user')
        if user not in user_list:
            return {"msg": "not supported user or model"}, 200
        id = request.values.get('dialogId')
        app.logger.info(user + "," + id)
        # 理想状态下是列表
        result = sqlitelog.get_dialog_context(user, int(id))
        context = json.loads(result.context)
        return {"content": {"chattype": result.chattype, "context": context}}
    except json.JSONDecodeError:
        return {"msg": "api return content not ok"}, 200

if __name__ == '__main__':
    # 若不存在sqlite3 db，初始化
    sqlitelog.init_db()
    # 上传文件夹初始化
    # if not os.path.exists(conf["common"]["upload_dir"]):
    #     os.makedirs(conf["common"]["upload_dir"])
    app.run(host='0.0.0.0', port=39997)