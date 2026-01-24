import configparser
import json
import logging
import os.path
import random
import sys
import time
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler
from urllib.parse import urlparse

import requests
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from openai import OpenAI, APIError, AuthenticationError, RateLimitError
from openai.types.chat import ChatCompletionUserMessageParam

import sqlitelog

app = Flask(__name__)
# 启用CORS支持，允许来自所有源的请求（在生产环境中应更具体地指定源）
CORS(app, supports_credentials=True, origins=["*"],
     allow_headers=["Content-Type", "Authorization", "X-Requested-With", "User-Agent", "Cache-Control"],
     methods=["GET", "PUT", "POST", "DELETE", "OPTIONS"])
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'ppt', 'pptx'}
conf = configparser.ConfigParser()
conf.read('conf/conf.ini', encoding="UTF-8")
url_list = conf['api']['api_host'].split(',')
# 解析用户凭据，支持格式：用户名:密码:api_key（api_key可选）
user_credentials = {}
user_api_keys = {}  # 存储用户的专属API key

# 支持多行格式的用户配置，每行一个用户信息
users_config = conf['common']['users']
# 按行分割，并去除空白行和仅包含空白字符的行
user_lines = [line.strip() for line in users_config.split('\n') if line.strip()]

for line in user_lines:
    # 按逗号分割（兼容旧格式）
    user_entries = line.split(',') if ',' in line else [line]

    for item in user_entries:
        # 使用最大分割次数2，确保即使密码或API密钥中包含冒号也能正确处理
        parts = item.strip().split(':', 2)
        if len(parts) >= 2:
            username = parts[0].strip()
            password = parts[1].strip()
            user_credentials[username] = password

            # 如果有第三个参数，则为该用户的专属API key
            if len(parts) >= 3 and parts[2].strip():
                user_api_keys[username] = parts[2].strip()
            else:
                user_api_keys[username] = conf['api']['api_key']  # 使用默认API key
        elif item.strip():  # 如果不是空行
            username = item.strip()
            user_credentials[username] = ''
            user_api_keys[username] = conf['api']['api_key']  # 使用默认API key

user_list = set(user_credentials.keys())

# 模型缓存相关配置
MODEL_CACHE = {}
CACHE_EXPIRY_TIME = {}

url = url_list[random.randint(0, len(url_list) - 1)]


def handle_api_exception(e, user=None, model=None, dialog_content=None):
    """
    统一处理API异常，特别处理IP白名单限制等错误
    """
    app.logger.error(f"API请求异常: {str(e)}, 类型: {type(e).__name__}")

    # 记录错误到日志
    if user and model:
        error_msg = f"API Error: {str(e)}"
        sqlitelog.set_log(user, 0, model, json.dumps({"error": error_msg, "content": dialog_content or ""}))

    # 处理不同的异常类型
    if isinstance(e, AuthenticationError):
        # 认证错误，可能包括IP白名单限制
        error_details = getattr(e, 'body', {}) or {}
        error_message = error_details.get('message', str(e)) if isinstance(error_details, dict) else str(e)

        # 特别处理IP白名单限制错误
        if '网段' in error_message or 'ip' in error_message.lower() or 'whitelist' in error_message.lower():
            return {
                "success": False,
                "msg": "API密钥访问受限：当前IP不在白名单中，请联系管理员或更换API服务",
                "error_type": "IP_RESTRICTION"
            }
        else:
            return {
                "success": False,
                "msg": f"认证失败: {error_message}",
                "error_type": "AUTHENTICATION_ERROR"
            }
    elif isinstance(e, RateLimitError):
        return {
            "success": False,
            "msg": "请求频率超限，请稍后再试",
            "error_type": "RATE_LIMIT_ERROR"
        }
    elif isinstance(e, APIError):
        # 通用API错误
        error_details = getattr(e, 'body', {}) or {}
        error_message = error_details.get('message', str(e)) if isinstance(error_details, dict) else str(e)
        return {
            "success": False,
            "msg": f"API错误: {error_message}",
            "error_type": "API_ERROR"
        }
    else:
        # 其他类型的异常
        return {
            "success": False,
            "msg": f"请求失败: {str(e)}",
            "error_type": "GENERAL_ERROR"
        }

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


def verify_credentials(user, password):
    if not user or user not in user_credentials:
        return False, "用户不存在或未授权"
    if user_credentials[user] != password:
        return False, "密码错误"
    return True, None

def random_client() -> OpenAI:
    return clients[random.randint(0, len(url_list) - 1)]


def get_client_for_user(username: str) -> OpenAI:
    """根据用户名获取对应的API客户端"""
    if username in user_api_keys:
        # 为用户创建具有其专属API key的客户端
        api_key = user_api_keys[username]
        url = url_list[random.randint(0, len(url_list) - 1)]
        return OpenAI(api_key=api_key, base_url=url)
    else:
        # 返回默认客户端
        return random_client()


def filter_models(models_data, include_prefixes=None, exclude_keywords=None):
    """过滤模型列表"""
    if include_prefixes is None:
        include_prefixes = ['gpt', 'gemini']
    if exclude_keywords is None:
        exclude_keywords = ['instruct', 'realtime', 'audio']

    filtered_models = []
    for model in models_data:
        model_id = model.get('id', '')

        # 检查是否包含指定模型
        has_include_prefix = any(prefix.lower() in model_id.lower() for prefix in include_prefixes)

        # 检查是否包含排除关键词
        has_exclude_keyword = any(keyword.lower() in model_id.lower() for keyword in exclude_keywords)

        if has_include_prefix and not has_exclude_keyword:
            filtered_models.append({
                'id': model_id.lower(),
                'label': model_id.lower()
            })

    return filtered_models


def get_cached_models():
    """获取缓存的模型列表，如果过期则重新获取"""
    import time

    cache_ttl = int(conf.get('model_filter', 'cache_ttl', fallback='3600'))
    current_time = time.time()

    # 检查缓存是否过期
    if 'models' in CACHE_EXPIRY_TIME and current_time < CACHE_EXPIRY_TIME['models']:
        # 缓存有效，直接返回
        return MODEL_CACHE.get('models', [])

    # 缓存过期或不存在，重新获取模型
    try:
        # 使用默认客户端获取模型列表，因为这个API不需要用户特定的凭证
        client = random_client()
        models_response = client.models.list()

        # 解析包含和排除规则
        include_prefixes_str = conf.get('model_filter', 'include_prefixes', fallback='gpt,gemini')
        exclude_keywords_str = conf.get('model_filter', 'exclude_keywords', fallback='instruct,realtime,audio')

        include_prefixes = [prefix.strip() for prefix in include_prefixes_str.split(',')]
        exclude_keywords = [keyword.strip() for keyword in exclude_keywords_str.split(',')]

        # 过滤模型
        filtered_models = filter_models([model.model_dump() for model in models_response.data], include_prefixes, exclude_keywords)

        # 更新缓存
        MODEL_CACHE['models'] = filtered_models
        CACHE_EXPIRY_TIME['models'] = current_time + cache_ttl

        return filtered_models
    except Exception as e:
        app.logger.error(f"获取模型列表失败: {str(e)}")
        return []


def is_valid_model(model_name):
    """验证模型是否有效"""
    available_models = get_cached_models()
    available_model_ids = [model['id'] for model in available_models]
    return model_name in available_model_ids


def get_grouped_models():
    """获取按前缀分组的模型列表"""
    try:
        # 使用默认客户端获取模型列表
        client = random_client()
        models_response = client.models.list()

        # 解析包含和排除规则
        include_prefixes_str = conf.get('model_filter', 'include_prefixes', fallback='gpt,gemini')
        exclude_keywords_str = conf.get('model_filter', 'exclude_keywords', fallback='instruct,realtime,audio')

        include_prefixes = [prefix.strip() for prefix in include_prefixes_str.split(',')]
        exclude_keywords = [keyword.strip() for keyword in exclude_keywords_str.split(',')]

        # 按前缀对模型进行分组
        grouped_models = {}

        for prefix in include_prefixes:
            if prefix.strip():  # 确保前缀非空
                prefix_models = []
                for model in models_response.data:
                    model_id = model.id.lower()
                    if prefix.lower() in model_id:
                        # 检查是否包含排除关键词
                        has_exclude_keyword = any(keyword.lower() in model_id for keyword in exclude_keywords)
                        if not has_exclude_keyword:
                            prefix_models.append({
                                'id': model.id,
                                'label': model.id
                            })

                if prefix_models:  # 只有当该前缀有匹配的模型时才添加到结果中
                    grouped_models[prefix] = prefix_models

        return grouped_models
    except Exception as e:
        app.logger.error(f"获取分组模型列表失败: {str(e)}")
        return {}


@app.route('/never_guess_my_usage/models/grouped', methods=['GET', 'POST'])
def get_grouped_models_endpoint():
    """获取按前缀分组的模型列表"""
    try:
        grouped_models = get_grouped_models()
        return {"success": True, "grouped_models": grouped_models}, 200
    except Exception as e:
        app.logger.error(f"获取分组模型列表异常: {str(e)}")
        return {"success": False, "msg": f"获取分组模型列表失败: {str(e)}"}, 200


@app.route('/never_guess_my_usage/models', methods=['GET', 'POST'])
def get_models():
    """获取可用的模型列表"""
    try:
        models = get_cached_models()
        return {"success": True, "models": models}, 200
    except Exception as e:
        app.logger.error(f"获取模型列表异常: {str(e)}")
        return {"success": False, "msg": f"获取模型列表失败: {str(e)}"}, 200

# 检查文件扩展名是否允许
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS



@app.route('/', methods=['GET', 'POST', 'OPTIONS'])
def handle_options():
    """处理预检请求"""
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'OK'})
        return response
    return '', 200

@app.route('/never_guess_my_usage/test', )
def health_check():
    app.logger.info(request.values)
    try:
        return json.dumps(request.values.to_dict()), 200
    except json.JSONDecodeError:
        return {"msg": "json no ok"}, 200


@app.route('/never_guess_my_usage/login', methods=['POST'])
def login():
    user = request.values.get('user', '').strip()
    password = request.values.get('password', '').strip()

    if not user:
        return {"success": False, "msg": "用户名不能为空"}, 200
    if user not in user_credentials:
        return {"success": False, "msg": "用户名不存在"}, 200
    if user_credentials[user] != password:
        return {"success": False, "msg": "密码错误"}, 200

    return {"success": True, "msg": "登录成功", "user": user}, 200

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

def extract_title_from_dialog(dialogvo: list, max_length: int = 50) -> str:
    """从对话中提取标题，优先使用第一条 user 消息"""
    for msg in dialogvo:
        if msg.get('role') == 'user':
            content = msg.get('content', '')
            return content[:max_length] + '...' if len(content) > max_length else content
    return 'Untitled'


@app.route('/never_guess_my_usage/split', methods=['POST', 'GET'])
def dialog():
    # 对话接口
    app.logger.info(request.values)
    try:
        # TODO 1 本地私钥解密
        # 2 用户名 + 上下文解析
        user = request.values.get('user', '').strip()
        password = request.values.get('password', '').strip()
        model = request.values.get('model')
        # 获取前端传入的对话标题
        dialog_title = request.values.get('dialog_title')

        # 获取最大回复token参数
        max_response_tokens = request.values.get('max_response_tokens', type=int)

        # 验证用户凭据
        is_valid, error_msg = verify_credentials(user, password)
        if not is_valid:
            return {"msg": error_msg}, 200

        # 用户白名单、model名根据配置检查
        logging.info(f"user:{user}， model: {model}")
        if not is_valid_model(model):
            return {"msg": "not supported user or model"}, 200
        dialogs = request.values.get('dialog')
        # 对话模式 single=单条 multi=上下文
        dialog_mode = request.values.get('dialog_mode', 'single')
        if dialog_mode == 'single':
            dialogvo = [ChatCompletionUserMessageParam(role="user", content=dialogs)]
            title = dialog_title or dialogs
        elif dialog_mode == 'multi':
            dialogvo = json.loads(dialogs)
            title = dialog_title or extract_title_from_dialog(dialogvo)
        else:
            return {"msg": "not supported dialog_mode"}, 200

        # 构建API调用参数
        api_params = {
            "model": model,
            "messages": dialogvo,
            "max_tokens": max_response_tokens or 102400  # 使用传入的参数或默认值
        }

        # 添加API请求的异常处理
        try:
            result = get_client_for_user(user).chat.completions.create(**api_params)
            # 4 sqlite3数据库写日志：用户名+token数+raw msg
            tokens = result.usage.total_tokens
            app.logger.info(result)
            sqlitelog.set_log(user, tokens, model, json.dumps(result.to_dict()))
            # 5 dialog组装：上下文+本次问题，返回答案
            sqlitelog.set_dialog(user, model, "chat",  title,
                                 json.dumps(dialogvo + [result.choices[0].message.to_dict()]))
            # 仅返回role和content
            return {"role": result.choices[0].message.role, "content": result.choices[0].message.content}, 200
        except Exception as api_e:
            return handle_api_exception(api_e, user=user, model=model, dialog_content=dialogs), 200
    except json.JSONDecodeError:
        return {"msg": "api return json not ok"}, 200


@app.route('/never_guess_my_usage/split_stream', methods=['POST', 'GET'])
def dialog_stream():
    # 对话接口 - 流式响应
    app.logger.info(request.values)
    try:
        user = request.values.get('user', '').strip()
        password = request.values.get('password', '').strip()
        model = request.values.get('model')
        # 获取前端传入的对话标题
        dialog_title = request.values.get('dialog_title')

        # 获取最大回复token参数
        max_response_tokens = request.values.get('max_response_tokens', type=int)

        # 验证用户凭据
        is_valid, error_msg = verify_credentials(user, password)
        if not is_valid:
            # 针对SSE请求，需要返回SSE格式的错误
            def error_generator():
                error_response = {
                    "success": False,
                    "msg": error_msg,
                    "done": True,
                    "error": {
                        "success": False,
                        "msg": error_msg,
                        "error_type": "AUTHENTICATION_ERROR"
                    }
                }
                yield f"data: {json.dumps(error_response)}\n\n"

            return Response(
                error_generator(),
                mimetype='text/event-stream',
                headers={
                    'Cache-Control': 'no-cache',
                    'X-Accel-Buffering': 'no',
                    'Connection': 'close'
                }
            )

        # 用户白名单、model名根据配置检查
        logging.info(f"user:{user}， model: {model}")
        if not is_valid_model(model):
            # 针对SSE请求，需要返回SSE格式的错误
            def error_generator():
                error_response = {
                    "success": False,
                    "msg": "not supported user or model",
                    "done": True,
                    "error": {
                        "success": False,
                        "msg": "not supported user or model",
                        "error_type": "MODEL_ERROR"
                    }
                }
                yield f"data: {json.dumps(error_response)}\n\n"

            return Response(
                error_generator(),
                mimetype='text/event-stream',
                headers={
                    'Cache-Control': 'no-cache',
                    'X-Accel-Buffering': 'no',
                    'Connection': 'close'
                }
            )
        dialogs = request.values.get('dialog')
        # 对话模式 single=单条 multi=上下文
        dialog_mode = request.values.get('dialog_mode', 'single')
        if dialog_mode == 'single':
            dialogvo = [ChatCompletionUserMessageParam(role="user", content=dialogs)]
            title = dialog_title or dialogs
        elif dialog_mode == 'multi':
            dialogvo = json.loads(dialogs)
            title = dialog_title or extract_title_from_dialog(dialogvo)
        else:
            # 针对SSE请求，需要返回SSE格式的错误
            def error_generator():
                error_response = {
                    "success": False,
                    "msg": "not supported dialog_mode",
                    "done": True,
                    "error": {
                        "success": False,
                        "msg": "not supported dialog_mode",
                        "error_type": "DIALOG_MODE_ERROR"
                    }
                }
                yield f"data: {json.dumps(error_response)}\n\n"

            return Response(
                error_generator(),
                mimetype='text/event-stream',
                headers={
                    'Cache-Control': 'no-cache',
                    'X-Accel-Buffering': 'no',
                    'Connection': 'close'
                }
            )

        def generate():
            full_content = ""
            try:
                # 构建API调用参数
                api_params = {
                    "model": model,
                    "messages": dialogvo,
                    "max_tokens": max_response_tokens or 102400,  # 使用传入的参数或默认值
                    "stream": True,
                    "timeout": 300  # 5分钟超时
                }

                stream = get_client_for_user(user).chat.completions.create(**api_params)

                for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        content_piece = chunk.choices[0].delta.content
                        full_content += content_piece
                        yield f"data: {json.dumps({'content': content_piece, 'done': False})}\n\n"

                yield f"data: {json.dumps({'content': '', 'done': True})}\n\n"

                # 记录日志 - 获取实际使用的token数
                # 在流式响应中无法获取usage，所以使用估算的方式
                tokens_used = len(full_content.encode('utf-8')) // 4  # 粗略估算token数量
                sqlitelog.set_log(user, tokens_used, model, json.dumps({"content": full_content}))
                # 记录对话
                sqlitelog.set_dialog(user, model, "chat", title,
                                    json.dumps(dialogvo + [{"role": "assistant", "content": full_content}]))

            except Exception as api_e:
                error_response = handle_api_exception(api_e, user=user, model=model, dialog_content=dialogs)
                app.logger.error(f"流式API请求异常处理: {error_response}")
                # 发送错误信息，标记为已完成，带有错误详情
                yield f"data: {json.dumps({'content': error_response.get('msg', 'API请求失败'), 'done': True, 'error': error_response})}\n\n"

        return Response(
            generate(),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'X-Accel-Buffering': 'no',
                'Connection': 'close',  # 确保连接关闭
                'Access-Control-Allow-Origin': '*',  # 添加CORS头
                'Access-Control-Allow-Credentials': 'true',
                'Access-Control-Allow-Headers': 'Content-Type,Authorization,X-Requested-With,User-Agent,Cache-Control',
                'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'
            }
        )
    except Exception as e:
        app.logger.error(f"流式对话异常: {str(e)}")

        # 针对SSE请求，需要返回SSE格式的错误
        def error_generator():
            error_response = {
                "success": False,
                "msg": f"流式对话异常: {str(e)}",
                "done": True,
                "error": {
                    "success": False,
                    "msg": f"流式对话异常: {str(e)}",
                    "error_type": "GENERAL_ERROR"
                }
            }
            yield f"data: {json.dumps(error_response)}\n\n"

        return Response(
            error_generator(),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'X-Accel-Buffering': 'no',
                'Connection': 'close',
                'Access-Control-Allow-Origin': '*',  # 添加CORS头
                'Access-Control-Allow-Credentials': 'true',
                'Access-Control-Allow-Headers': 'Content-Type,Authorization,X-Requested-With,User-Agent,Cache-Control',
                'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'
            }
        )

@app.route('/never_guess_my_usage/split_pic', methods=['POST'])
def dialog_pic():
    # 图片对话接口
    app.logger.info(request.values)
    try:
        # TODO 1 本地私钥解密
        # 2 用户名 + 上下文解析
        user = request.values.get('user', '').strip()
        password = request.values.get('password', '').strip()
        model = request.values.get('model')
        # 获取前端传入的对话标题
        dialog_title = request.values.get('dialog_title')

        # 验证用户凭据
        is_valid, error_msg = verify_credentials(user, password)
        if not is_valid:
            return {"msg": error_msg}, 200

        # 用户白名单、model名根据配置检查
        logging.info(f"user:{user}， model: {model}")
        if not is_valid_model(model):
            return {"msg": "not supported user or model"}, 200
        # 对话模式 single=单条 multi=上下文/编辑
        dialogs = request.values.get('dialog')
        dialog_mode = request.values.get('dialog_mode', 'single')
        if dialog_mode == 'single':
            dialogvo = {"role": "user", "desc": dialogs}
            title = dialog_title or dialogs

            try:
                result = get_client_for_user(user).images.generate(
                    model=model,
                    prompt=dialogs,
                    n=1,
                    response_format="url",
                    size="1024x1024",
                    timeout=120
                )
            except Exception as api_e:
                return handle_api_exception(api_e, user=user, model=model, dialog_content=dialogs), 200
        elif dialog_mode == 'multi':
            dialogvo = json.loads(dialogs)
            title = dialog_title or extract_title_from_dialog(dialogvo)  # 修复：改为使用新的提取函数
            # 将连接图片转为本地的file对象
            local_file = str(dialogvo[-2]["url"]).replace(":4567/download", "/home/www/downloads")

            try:
                with open(local_file, "rb") as image_file:
                    result = get_client_for_user(user).images.edit(
                        model=model,
                        image=image_file,
                        prompt=dialogvo[-1]["desc"],
                        n=1,
                        response_format="url",
                        size="1024x1024"
                    )
            except Exception as api_e:
                return handle_api_exception(api_e, user=user, model=model, dialog_content=json.dumps(dialogs)), 200
        else:
            return {"msg": "not supported dialog_mode"}, 200

        app.logger.info(result)
        # 返回的图片url需要转储到本地的downloads/image中，再生成新的链接/日志/对话记录，同时在客户端展示图片和文件url
        # 暂时支持生成1张
        desc = result.data[0].revised_prompt
        # 保存到本地后使用本地的下载url
        # TODO 异常提示词是没有url的，需要区分code
        response = requests.get(result.data[0].url)
        if response.status_code == 200:
            filename = (model + "-" + str(time.time()) + "-")
            filename += [seg for seg in urlparse(result.data[0].url).path.split('/') if seg][-1]
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
        sqlitelog.set_log(user, 1, model, json.dumps(result.to_dict()))
        # 5 dialog组装：上下文+本次问题回答
        if not isinstance(dialogvo, list):
            dialogvo = [dialogvo]
        dialogvo.append(result_save)
        sqlitelog.set_dialog(user, model,"pic", title, json.dumps(dialogvo))
        return result_save, 200
    except json.JSONDecodeError:
        return {"msg": "api return json not ok"}, 200

@app.route('/never_guess_my_usage/split_his', methods=['POST'])
def dialog_his():
    # 根据用户名获取3日内历史纪录，[{日期+标题、类型}], 按id倒排
    user = request.values.get('user', '').strip()
    password = request.values.get('password', '').strip()

    # 验证用户凭据
    is_valid, error_msg = verify_credentials(user, password)
    if not is_valid:
        return {"msg": error_msg}, 200

    app.logger.info(user)
    min_time_str = (datetime.now() - timedelta(days=3)).date()
    dialog_list = sqlitelog.get_dialog_list(user, min_time_str)
    dialog_list = [ {**item, "start_date": item["start_date"].strftime("%Y-%m-%d")} for item in dialog_list]
    return {"content": dialog_list}, 200

@app.route('/never_guess_my_usage/split_his_content', methods=['POST'])
def dialog_content():
    try:
        # 根据用户名+id获取历史纪录详情context
        user = request.values.get('user', '').strip()
        password = request.values.get('password', '').strip()
        id = request.values.get('dialogId')

        # 验证用户凭据
        is_valid, error_msg = verify_credentials(user, password)
        if not is_valid:
            return {"msg": error_msg}, 200

        app.logger.info(user + "," + id)
        # 理想状态下是列表
        result = sqlitelog.get_dialog_context(user, int(id))
        context = json.loads(result.context)
        return {"content": {"chattype": result.chattype, "context": context}}
    except json.JSONDecodeError:
        return {"msg": "api return content not ok"}, 200


@app.route('/never_guess_my_usage/usage', methods=['GET'])
def get_usage():
    """获取用户用量信息"""
    user = request.values.get('user', '').strip()
    password = request.values.get('password', '').strip()

    # 验证用户凭据
    is_valid, error_msg = verify_credentials(user, password)
    if not is_valid:
        return {"success": False, "msg": error_msg}, 200

    # 检查用户是否有专属API Key
    if user not in user_api_keys or not user_api_keys[user]:
        return {"success": False, "msg": "用户没有配置API密钥"}, 200

    api_key = user_api_keys[user]
    api_host = url_list[random.randint(0, len(url_list) - 1)]

    # 获取汇率转换率，默认为2.5
    usd_to_cny_rate = float(conf.get('api', 'usd_to_cny_rate', fallback='2.5'))

    try:
        # 获取当前时间和时间范围
        now = datetime.now()

        # 从配置中获取API参数模式，默认为'default'
        api_param_mode = conf.get('api', 'api_param_mode', fallback='default')

        headers = {
            'Authorization': f'Bearer {api_key}',
        }

        if api_param_mode == 'timestamp':
            # 使用毫秒时间戳格式
            # 今日0点（毫秒时间戳）
            today_start = datetime.combine(now.date(), datetime.min.time())
            today_timestamp_ms = int(today_start.timestamp() * 1000)

            # 本周一0点（毫秒时间戳）
            week_start = datetime.combine((now - timedelta(days=now.weekday())).date(), datetime.min.time())
            week_timestamp_ms = int(week_start.timestamp() * 1000)

            # 当前时间（毫秒时间戳）
            now_timestamp_ms = int(now.timestamp() * 1000)

            # 获取今日用量（使用毫秒时间戳格式）
            today_response = requests.get(
                f"{api_host}/dashboard/billing/usage?start_date={today_timestamp_ms}&end_date={now_timestamp_ms}",
                headers=headers,
                timeout=30
            )
            today_response.raise_for_status()
            today_data = today_response.json()
            today_usage = today_data.get('total_usage', 0)

            # 获取本周用量（使用毫秒时间戳格式）
            week_response = requests.get(
                f"{api_host}/dashboard/billing/usage?start_date={week_timestamp_ms}&end_date={now_timestamp_ms}",
                headers=headers,
                timeout=30
            )
            week_response.raise_for_status()
            week_data = week_response.json()
            week_usage =  week_data.get('total_usage', 0)

            # 获取总用量（使用更长时间范围的数据）
            # 从一年前开始到现在，使用毫秒时间戳
            one_year_ago = datetime.now() - timedelta(days=365)
            one_year_ago_timestamp_ms = int(one_year_ago.timestamp() * 1000)

            total_response = requests.get(
                f"{api_host}/dashboard/billing/usage?start_date={one_year_ago_timestamp_ms}&end_date={now_timestamp_ms}",
                headers=headers,
                timeout=30
            )
            total_response.raise_for_status()
            total_data = total_response.json()
            total_usage = total_data.get('total_usage', 0)

        else:  # 默认使用日期字符串格式
            # 今日0点
            today_start = datetime.combine(now.date(), datetime.min.time())
            # 本周一0点
            week_start = datetime.combine((now - timedelta(days=now.weekday())).date(), datetime.min.time())

            # 格式化为API所需格式 (YYYY-MM-DD)
            today_str = today_start.strftime('%Y-%m-%d')
            week_str = week_start.strftime('%Y-%m-%d')
            now_str = now.strftime('%Y-%m-%d')

            # 获取今日用量
            today_response = requests.get(
                f"{api_host}/dashboard/billing/usage?start_date={today_str}&end_date={now_str}",
                headers=headers,
                timeout=30
            )
            today_response.raise_for_status()
            today_data = today_response.json()
            today_usage = week_data.get('total_usage', 0)

            # 获取本周用量
            week_response = requests.get(
                f"{api_host}/dashboard/billing/usage?start_date={week_str}&end_date={now_str}",
                headers=headers,
                timeout=30
            )
            week_response.raise_for_status()
            week_data = week_response.json()
            week_usage = week_data.get('total_usage', 0)

            # 获取总用量
            total_response = requests.get(
                f"{api_host}/dashboard/billing/usage?start_date={week_str}&end_date={now_str}",
                headers=headers,
                timeout=30
            )
            total_response.raise_for_status()
            total_data = total_response.json()
            total_usage = total_data.get('total_usage', 0)

        # 获取订阅限额
        subscription_response = requests.get(
            f"{api_host}/dashboard/billing/subscription",
            headers=headers,
            timeout=30
        )
        subscription_response.raise_for_status()
        subscription_data = subscription_response.json()
        quota = subscription_data.get('hard_limit_usd', 0)

        # 单位换算：美分转人民币元
        today_usage_cny = (today_usage / 100) * usd_to_cny_rate
        week_usage_cny = (week_usage / 100) * usd_to_cny_rate
        total_usage_cny = (total_usage / 100) * usd_to_cny_rate
        quota_cny = quota * usd_to_cny_rate
        remaining_cny = quota_cny - total_usage_cny

        result = {
            "success": True,
            "data": {
                "today_usage": round(today_usage_cny, 2),
                "week_usage": round(week_usage_cny, 2),
                "total_usage": round(total_usage_cny, 2),
                "quota": round(quota_cny, 2),
                "remaining": round(remaining_cny, 2),
                "currency": "CNY"
            }
        }

        return result, 200

    except requests.exceptions.RequestException as e:
        app.logger.error(f"获取用量API请求异常: {str(e)}")
        return {"success": False, "msg": f"API请求失败: {str(e)}"}, 200
    except Exception as e:
        app.logger.error(f"获取用量异常: {str(e)}")
        return {"success": False, "msg": f"获取用量失败: {str(e)}"}, 200


@app.route('/never_guess_my_usage/split_his_delete', methods=['POST'])
def dialog_delete():
    """删除用户的历史会话（支持批量删除）"""
    user = request.values.get('user', '').strip()
    password = request.values.get('password', '').strip()
    dialog_ids_str = request.values.get('dialog_ids', '[]')

    # 验证用户凭据
    is_valid, error_msg = verify_credentials(user, password)
    if not is_valid:
        return {"success": False, "msg": error_msg}

    # 解析并验证 dialog_ids
    dialog_ids = json.loads(dialog_ids_str)

    # 执行删除
    deleted_count = sqlitelog.delete_dialogs(user, dialog_ids)
    return {"success": True, "deleted_count": deleted_count}

# 在应用启动时初始化数据库表
# 若不存在sqlite3 db，初始化
sqlitelog.init_db()

if __name__ == '__main__':
    # 上传文件夹初始化
    # if not os.path.exists(conf["common"]["upload_dir"]):
    #     os.makedirs(conf["common"]["upload_dir"])
    app.run(host='0.0.0.0', port=39997)