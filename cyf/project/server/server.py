import configparser
import json
import os.path
import random
import sqlitelog

from flask import Flask, request
from openai import OpenAI
from openai.types.chat import ChatCompletionUserMessageParam
from werkzeug.utils import secure_filename

from cyf.project.server.sqlitelog import set_log

app = Flask(__name__)
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}
conf = configparser.ConfigParser()
conf.read('conf/conf.ini')
url_list = conf['api']['api_host'].split(',')
url = url_list[random.randint(0, len(url_list) - 1)]
client=OpenAI(
    api_key=conf['api']['api_key'],
    base_url=url
)

# 检查文件扩展名是否允许
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/test', )
def health_check():
    print(request.values)
    try:
        data = request.get_json()
        return json.dumps(data), 200
    except json.JSONDecodeError:
        return 'Not OK', 500

@app.route('/never_guess_my_usage/set_info', )
def data_check():
    print(request.values)
    try:
        if request.values.get('param'):
            param = request.values.get('param').split(",")
            return sqlitelog.message_query(request.values.get('info'), param), 200
        else:
            return sqlitelog.message_query(request.values.get('info')), 200
    except json.JSONDecodeError:
        return 'Not OK', 500


@app.route('/never_guess_my_usage/download',  methods=['POST'])
def upload():
    # 检查请求中是否包含文件部分
    if 'file' not in request.files:
        return "", 200
    file = request.files['file']
    if file.filename == '':
        return "", 200
    if file.content_length > 20 * 1024 * 1024:
        return "文件超过20M", 500
    # 检查文件是否符合条件
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file.save(os.path.join(conf["common"]["upload_dir"], filename))
        # 加密混淆或定期清理？
        return f'文件服务器地址/{filename}', 200
    else:
        # 上传文件并返回url的接口
        return "文件格式问题", 500

@app.route('/never_guess_my_usage/split', methods=['POST', 'GET'])
def dialog():
    # 对话接口
    print(request.values)
    try:
        # TODO 1 本地私钥解密
        # 2 用户名 + 上下文解析
        user = request.values.get('user')
        # 用户白名单先入配置
        print(f"user:c{user}")
        # TODO 需要客户端支持多轮对话
        dialogs = request.values.get('dialog')
        dialogvo=[ChatCompletionUserMessageParam(role="user", content=dialogs)]
        # 功能测试
        result = client.chat.completions.create(
            model='gpt-3.5-turbo',
            messages=dialogvo,
            max_completion_tokens=1000
        )
        # TODO 省资源，需要截断会话?
        # 4 sqlite3数据库写日志：用户名+token数+raw msg
        tokens = result.usage.total_tokens
        sqlitelog.set_log(user, tokens, json.dumps(result.to_dict()))
        # 5 dialog组装：问题+答案
        sqlitelog.set_dialog(user, dialogs,
                             json.dumps(dialogvo + [result.choices[0].message.to_dict()]))
        return result.choices[0].message.content, 200
    except json.JSONDecodeError:
        return 'Not OK', 500

if __name__ == '__main__':
    # 若不存在sqlite3 db，初始化
    sqlitelog.init_db()
    # 上传文件夹初始化
    # if not os.path.exists(conf["common"]["upload_dir"]):
    #     os.makedirs(conf["common"]["upload_dir"])
    app.run(host='0.0.0.0', port=80)