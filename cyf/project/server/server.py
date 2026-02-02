import configparser
import json
import logging
import os.path
import random
import sys
import time
import re
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler
from urllib.parse import urlparse

import requests
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from openai import OpenAI, APIError, AuthenticationError, RateLimitError
from openai.types.chat import ChatCompletionUserMessageParam

import sqlitelog

# 添加数据库认证相关的导入
from sqlitelog import user_exists_in_db, verify_user_password, get_user_api_key, get_all_active_users

# 导入 admin 接口（如果存在）
try:
    import server_admin
    admin_app = server_admin.app
except ImportError:
    admin_app = None
    print("警告: server_admin.py 不存在或导入失败，跳过 admin 接口注册")

# 文件URL正则表达式
FILE_URL_PATTERN = re.compile(r'\[FILE_URL:(https?://[^\]]+)\]')

USE_DB_AUTH = True

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 52428800
# 启用CORS支持，允许来自所有源的请求（在生产环境中应更具体地指定源）
CORS(app, supports_credentials=True, origins=["*"],
     allow_headers=["Content-Type", "Authorization", "X-Requested-With", "User-Agent", "Cache-Control"],
     methods=["GET", "PUT", "POST", "DELETE", "OPTIONS"])

# 为所有响应添加CORS头的函数
@app.after_request
def after_request(response):
    # 为所有响应添加CORS头
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization,X-Requested-With,User-Agent,Cache-Control')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    response.headers.add('Access-Control-Allow-Credentials', 'true')
    return response
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'ppt', 'pptx', 'md'}
conf = configparser.ConfigParser()
conf.read('conf/conf.ini', encoding="UTF-8")
url_list = conf['api']['api_host'].split(',')
web_host = conf['common']['host']
# 解析用户凭据，支持格式：用户名:密码:api_key（api_key可选）
user_credentials = {}
user_api_keys = {}  # 存储用户的专属API key

# 模型缓存相关配置
MODEL_CACHE = {}
CACHE_EXPIRY_TIME = {}

# 测试用户限制配置
test_user_name = conf.get('common', 'test_user', fallback='')
test_ip_default_limit = int(conf.get('common', 'test_ip_default_limit', fallback='20'))
test_exceed_msg = conf.get('common', 'test_exceed_msg', fallback='请求次数已达上限')

url = url_list[random.randint(0, len(url_list) - 1)]


def is_gemini_model(model_name: str) -> bool:
    """判断是否为 Gemini 类型模型"""
    return 'gemini' in model_name.lower()


def convert_message_for_gemini(message: dict) -> dict:
    """
    将消息转换为 Gemini 格式
    输入: {"role": "user", "content": "文本[FILE_URL:http://xxx]"}
    输出: {"role": "user", "content": [{"type": "text", "text": "文本"}, {"type": "file_url", "file_url": "http://xxx"}]}
    """
    content = message.get('content', '')
    if isinstance(content, list):
        return message  # 已是数组格式

    # 提取文件 URL
    file_urls = FILE_URL_PATTERN.findall(content)

    if not file_urls:
        return message  # 无文件URL，保持原格式

    # 获取纯文本（移除标记）
    text_content = FILE_URL_PATTERN.sub('', content).strip()

    # 构建 content 数组
    content_array = []
    if text_content:
        content_array.append({"type": "text", "text": text_content})
    for url in file_urls:
        content_array.append({"type": "file_url", "file_url": url})

    return {"role": message.get('role'), "content": content_array}


def convert_dialog_for_model(dialogvo: list, model: str) -> list:
    """根据模型类型转换对话格式"""
    if is_gemini_model(model):
        return [convert_message_for_gemini(msg) for msg in dialogvo]
    return dialogvo  # 非Gemini模型保持原格式


def url_to_file(url: str) -> bytes:
    """
    将URL转换为文件字节数据
    """
    try:
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            return response.content
        else:
            raise Exception(f"无法下载文件，状态码: {response.status_code}")
    except Exception as e:
        app.logger.error(f"URL转文件失败: {str(e)}")
        raise


def process_pic_dialog_with_urls(dialogs: str, dialog_mode: str) -> dict:
    """
    处理图片对话中的URL，将FILE_URL_PATTERN匹配到的URL转换为文件
    返回处理后的对话数据和文件列表
    """
    result = {
        'processed_dialogs': dialogs,
        'files': [],
        'text_content': dialogs,
        'original_content': dialogs  # 保留原始内容用于历史记录
    }
    
    if dialog_mode == 'single':
        # 检查是否包含文件URL
        file_urls = FILE_URL_PATTERN.findall(dialogs)
        if file_urls:
            # 提取纯文本内容（用于API调用）
            text_content = FILE_URL_PATTERN.sub('', dialogs).strip()
            result['text_content'] = text_content
            
            # 下载文件
            for url in file_urls:
                try:
                    file_data = url_to_file(url)
                    filename = os.path.basename(urlparse(url).path) or 'file'
                    # 创建文件元组 (filename, bytes, content_type)
                    content_type = get_content_type(filename)
                    result['files'].append({
                        'url': url,
                        'data': (filename, file_data, content_type),
                        'filename': filename
                    })
                except Exception as e:
                    app.logger.error(f"处理文件URL失败 {url}: {str(e)}")
                    
        result['processed_dialogs'] = result['text_content']
    
    return result


def get_content_type(filename: str) -> str:
    """
    根据文件扩展名获取content type
    """
    ext = os.path.splitext(filename)[1].lower()
    content_types = {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.webp': 'image/webp',
        '.bmp': 'image/bmp',
        '.tiff': 'image/tiff'
    }
    return content_types.get(ext, 'application/octet-stream')


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


def generate_sse_error(error_msg, error_type="GENERAL_ERROR"):
    """
    生成SSE错误响应的通用函数
    """
    error_response = {
        "success": False,
        "msg": error_msg,
        "done": True,
        "error": {
            "success": False,
            "msg": error_msg,
            "error_type": error_type
        }
    }
    yield f"data: {json.dumps(error_response)}\n\n"

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
    if USE_DB_AUTH:
        success, error_msg, _ = sqlitelog.verify_user_password(user, password)
        return success, error_msg
    else:
        if not user or user not in user_credentials:
            return False, "用户不存在或未授权"
        if user_credentials[user] != password:
            return False, "密码错误"
        return True, None

def get_request_data():
    """
    通用请求数据获取函数，兼容JSON和form格式
    返回一个类似dict的对象，可以使用.get()方法获取数据
    """
    content_type = request.content_type

    if content_type and 'application/json' in content_type:
        # 如果是JSON请求，从JSON数据中获取参数
        json_data = request.get_json(silent=True)
        if json_data:
            # 使用字典推导式将第一层元素转换为文本格式
            text_data = {key: str(value) for key, value in json_data.items()}
            return text_data
        else:
            # 如果JSON数据无效，回退到request.values
            return request.values
    else:
        # 否则是表单数据或URL参数
        return request.values


def require_auth(f):
    """用户认证装饰器，用于验证用户凭据"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 首先检查Content-Type头以确定请求数据格式
        content_type = request.content_type

        if content_type and 'application/json' in content_type:
            # 如果是JSON请求，从JSON数据中获取参数
            json_data = request.get_json(silent=True)
            if json_data:
                user = json_data.get('user', '').strip()
                password = json_data.get('password', '').strip()
            else:
                # 如果JSON数据无效，尝试从其他来源获取
                user = request.values.get('user', '').strip()
                password = request.values.get('password', '').strip()
        else:
            # 否则是表单数据或URL参数
            user = request.values.get('user', '').strip()
            password = request.values.get('password', '').strip()

        # 验证用户凭据
        is_valid, error_msg = verify_credentials(user, password)
        if not is_valid:
            return {"msg": error_msg}, 200

        # 将用户信息注入到函数参数中
        kwargs['user'] = user
        kwargs['password'] = password

        return f(*args, **kwargs)
    return decorated_function

def random_client() -> OpenAI:
    return clients[random.randint(0, len(url_list) - 1)]


def get_client_for_user(username: str) -> OpenAI:
    """根据用户名获取对应的API客户端"""
    if USE_DB_AUTH:
        api_key = sqlitelog.get_user_api_key(username)
    else:
        api_key = user_api_keys.get(username)

    if api_key:
        # 为用户创建具有其专属API key的客户端
        url = url_list[random.randint(0, len(url_list) - 1)]
        return OpenAI(api_key=api_key, base_url=url)
    else:
        # 返回默认客户端
        return random_client()


def get_client_ip() -> str:
    """获取客户端真实 IP（支持反向代理）"""
    # 优先从 X-Forwarded-For 获取（通过代理时）
    forwarded = request.headers.get('X-Forwarded-For')
    if forwarded:
        # 取第一个 IP（最原始的客户端 IP）
        return forwarded.split(',')[0].strip()
    return request.remote_addr or '127.0.0.1'


def check_test_user_limit(user: str) -> dict:
    """
    检查测试用户是否超过请求限制
    返回 None 表示未超限或非测试用户，否则返回错误响应
    """
    if not test_user_name or user != test_user_name:
        return {"success": True,}

    client_ip = get_client_ip()

    # 先检查是否已超限
    if sqlitelog.check_test_limit_exceeded(client_ip, test_ip_default_limit):
        return {
            "success": False,
            "msg": test_exceed_msg,
            "error_type": "TEST_LIMIT_EXCEEDED"
        }

    # 增加计数
    sqlitelog.increment_test_limit(client_ip, test_ip_default_limit)
    return {"success": True,}


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
            # 构建基本模型对象
            filtered_model = {
                'id': model_id.lower(),
                'label': model_id.lower()
            }
            # 保留原模型中的其他字段（如 recommend, model_desc 等）
            for key, value in model.items():
                if key not in ['id', 'label']:  # 只有当这些字段不存在于基本对象中时才添加
                    if key not in filtered_model:
                        filtered_model[key] = value
            filtered_models.append(filtered_model)

    return filtered_models


def get_cached_models():
    """获取缓存的模型列表，如果过期则重新获取"""
    import time

    cache_ttl = int(conf.get('model_filter', 'cache_ttl', fallback='3600'))
    current_time = time.time()

    # 检查缓存是否过期
    if 'models' in CACHE_EXPIRY_TIME and current_time < CACHE_EXPIRY_TIME['models']:
        return MODEL_CACHE.get('models', [])

    try:
        client = random_client()
        models_response = client.models.list()

        # 解析包含和排除规则
        include_prefixes_str = conf.get('model_filter', 'include_prefixes', fallback='gpt,gemini')
        exclude_keywords_str = conf.get('model_filter', 'exclude_keywords', fallback='instruct,realtime,audio')

        include_prefixes = [prefix.strip() for prefix in include_prefixes_str.split(',')]
        exclude_keywords = [keyword.strip() for keyword in exclude_keywords_str.split(',')]

        # 过滤模型
        filtered_models = filter_models([model.model_dump() for model in models_response.data], include_prefixes, exclude_keywords)

        # ========== 新增：集成 ModelMeta 元数据 ==========
        # 获取所有模型的元数据
        model_ids = [m['id'] for m in filtered_models]
        model_meta_list = sqlitelog.get_model_meta_list(model_names=model_ids)

        # 构建元数据映射 (model_name -> meta)
        meta_map = {meta['model_name'].lower(): meta for meta in model_meta_list}

        # 增强模型列表：添加元数据字段，过滤无效模型
        enhanced_models = []
        for model in filtered_models:
            model_id = model['id'].lower()
            meta = meta_map.get(model_id)

            # 如果有元数据且 status_valid 为 False，跳过该模型
            if meta and not meta.get('status_valid', True):
                continue

            # 添加元数据字段
            model['recommend'] = meta.get('recommend', False) if meta else False
            model['model_desc'] = meta.get('model_desc', '') if meta else ''
            # 1-文本 2-图像
            model['model_type'] = meta.get('model_type', '') if meta else 1
            enhanced_models.append(model)
        # ========== 新增结束 ==========

        # 更新缓存
        MODEL_CACHE['models'] = enhanced_models
        CACHE_EXPIRY_TIME['models'] = current_time + cache_ttl

        return enhanced_models
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
        models_response = get_cached_models()

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
                for model in models_response:
                    model_id = model['id'].lower()
                    if prefix.lower() in model_id:
                        # 检查是否包含排除关键词
                        has_exclude_keyword = any(keyword.lower() in model_id for keyword in exclude_keywords)
                        if not has_exclude_keyword:
                            prefix_models.append(model)

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
    app.logger.info(get_request_data())
    try:
        return json.dumps(get_request_data().to_dict()), 200
    except json.JSONDecodeError:
        return {"msg": "json no ok"}, 200


@app.route('/never_guess_my_usage/login', methods=['POST'])
def login():
    content_type = request.content_type
    data = get_request_data()
    # 否则是表单数据
    user = data.get('user', '').strip()
    password = data.get('password', '').strip()

    if not user:
        return {"success": False, "msg": "用户名不能为空"}, 200

    # 使用统一的验证函数
    is_valid, error_msg = verify_credentials(user, password)
    if not is_valid:
        return {"success": False, "msg": error_msg}, 200

    return {"success": True, "msg": "登录成功", "user": user}, 200

@app.route('/never_guess_my_usage/set_info', )
def data_check():
    data = get_request_data()
    app.logger.info(data)
    try:
        if data.get('param'):
            param = data.get('param').split(",")
            return sqlitelog.message_query(data.get('info'), param), 200
        else:
            return sqlitelog.message_query(data.get('info')), 200
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


def parse_dialog_mode(dialogs, dialog_mode, dialog_title=None):
    """
    解析对话模式（single/multi）并返回相应的对话内容和标题
    """
    if dialog_mode == 'single':
        dialogvo = [ChatCompletionUserMessageParam(role="user", content=dialogs)]
        title = dialog_title or dialogs
    elif dialog_mode == 'multi':
        dialogvo = json.loads(dialogs)
        title = dialog_title or extract_title_from_dialog(dialogvo)
    else:
        return None, "not supported dialog_mode"

    return dialogvo, title


@app.route('/never_guess_my_usage/split', methods=['POST', 'GET'])
@require_auth
def dialog(user, password):
    # 对话接口
    data = get_request_data()
    app.logger.info(data)
    try:
        # TODO 1 本地私钥解密
        # 2 用户名 + 上下文解析
        model = data.get('model')
        # 获取前端传入的对话标题
        dialog_title = data.get('dialog_title')

        # 获取最大回复token参数
        max_response_tokens_raw = data.get('max_response_tokens')
        max_response_tokens = int(max_response_tokens_raw) if max_response_tokens_raw is not None else None

        # 检查测试用户限制
        limit_error = check_test_user_limit(user)
        if not limit_error["success"]:
            return limit_error, 200

        # 用户白名单、model名根据配置检查
        logging.info(f"user:{user}， model: {model}")
        if not is_valid_model(model):
            return {"msg": "not supported user or model"}, 200
        dialogs = data.get('dialog')
        # 对话模式 single=单条 multi=上下文
        dialog_mode = data.get('dialog_mode', 'single')

        dialogvo, title = parse_dialog_mode(dialogs, dialog_mode, dialog_title)
        if dialogvo is None:
            return {"msg": title}, 200

        # 构建API调用参数
        api_params = {
            "model": model,
            "messages": convert_dialog_for_model(dialogvo, model),  # 根据模型类型转换对话格式
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
            # 仅返回role、content和finish_reason
            return {
                "role": result.choices[0].message.role,
                "content": result.choices[0].message.content,
                "finish_reason": result.choices[0].finish_reason
            }, 200
        except Exception as api_e:
            return handle_api_exception(api_e, user=user, model=model, dialog_content=dialogs), 200
    except json.JSONDecodeError:
        return {"msg": "api return json not ok"}, 200


@app.route('/never_guess_my_usage/split_stream', methods=['POST', 'GET'])
@require_auth
def dialog_stream(user, password):
    # 对话接口 - 流式响应
    data = get_request_data()
    app.logger.info(data)
    try:
        model = data.get('model', '')
        app.logger.info(model)
        # 获取前端传入的对话标题
        dialog_title = data.get('dialog_title', '')
        app.logger.info(dialog_title)
        # 获取最大回复token参数
        max_response_tokens_raw = data.get('max_response_tokens')
        max_response_tokens = int(max_response_tokens_raw) if max_response_tokens_raw is not None else None

        # 检查测试用户限制
        limit_error = check_test_user_limit(user)
        if not limit_error["success"]:
            return Response(
                generate_sse_error(limit_error["msg"], "TEST_EXCEED"),
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
            return Response(
                generate_sse_error("not supported user or model", "MODEL_ERROR"),
                mimetype='text/event-stream',
                headers={
                    'Cache-Control': 'no-cache',
                    'X-Accel-Buffering': 'no',
                    'Connection': 'close'
                }
            )
        dialogs = data.get('dialog')
        # 对话模式 single=单条 multi=上下文
        dialog_mode = data.get('dialog_mode', 'single')

        dialogvo, title = parse_dialog_mode(dialogs, dialog_mode, dialog_title)
        if dialogvo is None:
            # 针对SSE请求，需要返回SSE格式的错误
            return Response(
                generate_sse_error(title, "DIALOG_MODE_ERROR"),
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
                    "messages": convert_dialog_for_model(dialogvo, model),  # 根据模型类型转换对话格式
                    "max_tokens": max_response_tokens or 102400,  # 使用传入的参数或默认值
                    "stream": True,
                    "timeout": 300  # 5分钟超时
                }

                stream = get_client_for_user(user).chat.completions.create(**api_params)

                finish_reason = None
                for chunk in stream:
                    if chunk.choices:
                        delta = chunk.choices[0].delta
                        if delta.content:
                            content_piece = delta.content
                            full_content += content_piece
                            yield f"data: {json.dumps({'content': content_piece, 'done': False})}\n\n"
                        if chunk.choices[0].finish_reason:
                            finish_reason = chunk.choices[0].finish_reason

                yield f"data: {json.dumps({'content': '', 'done': True, 'finish_reason': finish_reason})}\n\n"

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
                'Connection': 'close'  # 确保连接关闭
            }
        )
    except Exception as e:
        app.logger.error(f"流式对话异常: {str(e)}")

        # 针对SSE请求，需要返回SSE格式的错误
        return Response(
            generate_sse_error(f"流式对话异常: {str(e)}", "GENERAL_ERROR"),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'X-Accel-Buffering': 'no',
                'Connection': 'close',
            }
        )

@app.route('/never_guess_my_usage/split_pic', methods=['POST'])
@require_auth
def dialog_pic(user, password):
    # 图片对话接口
    data = get_request_data()
    app.logger.info(data)
    try:
        # TODO 1 本地私钥解密
        # 2 用户名 + 上下文解析
        model = data.get('model')
        # 获取前端传入的对话标题
        dialog_title = data.get('dialog_title')
        size = data.get('size', '1024x1024')

        # 用户白名单、model名根据配置检查
        logging.info(f"user:{user}， model: {model}")
        if not is_valid_model(model):
            return {"msg": "not supported user or model"}, 200
        # 对话模式 single=单条 multi=上下文/编辑
        dialogs = data.get('dialog')
        dialog_mode = data.get('dialog_mode', 'single')
        dialog_id = data.get('dialogId') or None
        # 处理FILE_URL_PATTERN匹配
        processed_data = process_pic_dialog_with_urls(dialogs, dialog_mode)
        
        if dialog_mode == 'single':
            dialogvo = []  # 使用原始内容保存历史记录
            title = dialog_title or processed_data['original_content']
        elif dialog_mode == 'multi':
            # 多轮对话优化：根据前端编辑后的历史记录来保存
            dialogvo = json.loads(dialogs)
            title = dialog_title or extract_title_from_dialog(dialogvo)

                
        try:
            # 如果有文件，使用图片编辑API；否则使用图片生成API
            if processed_data['files']:
                # 使用第一个文件进行图片编辑
                file_info = processed_data['files'][0]
                result = get_client_for_user(user).images.edit(
                    model=model,
                    image=file_info['data'],
                    prompt=processed_data['text_content'],
                    n=1,
                    response_format="url",
                    size=size,
                    timeout=120
                )
            else:
                # 无文件，直接生成图片
                result = get_client_for_user(user).images.generate(
                    model=model,
                    prompt=processed_data['text_content'],
                    n=1,
                    response_format="url",
                    size=size,
                    timeout=120
                )
        except Exception as api_e:
            return handle_api_exception(api_e, user=user, model=model, dialog_content=dialogs), 200

        app.logger.info(result)
        # 返回的图片url需要转储到本地的downloads/image中，再生成新的链接/日志/对话记录，同时在客户端展示图片和文件url
        # 暂时支持生成1张
        desc = result.data[0].revised_prompt or '图片已生成'
        # 保存到本地后使用本地的下载url
        # TODO 异常提示词是没有url的，需要区分code
        # response = requests.get(result.data[0].url)
        # if response.status_code == 200:
        #     filename = (model + "-" + str(time.time()) + "-")
        #     filename += [seg for seg in urlparse(result.data[0].url).path.split('/') if seg][-1]
        #     save_path = os.path.join(conf["common"]["upload_dir"], "images/" + filename)
        #     with open(save_path, "wb") as pic:
        #         pic.write(response.content)
        #     os.chmod(save_path, 0o755)
        #     logging.info(f"pic saving:{save_path}")
        # else:
        #     return {"msg": "error requesting pic server"}, 501
        # result_save = {"role": "assistant", "desc": desc, "url": f'{web_host}:4567/download/images/{filename}'}
        # TODO 直接保存oss url，后面有余力再考虑转存
        result_save = {"role": "assistant", "desc": desc, "url": f'{result.data[0].url}'}
        # 日志和对话单独记录，dialog中新增model-name字段？
        # 图片按条数统计
       
        sqlitelog.set_log(user, 1, model, json.dumps(result.to_dict()))
        # 5 dialog组装：上下文+本次问题回答
        try:
            # 根据对话模式处理新的对话项
            if dialog_mode == 'single':
                # 单轮对话模式，直接添加当前对话和结果
                new_entry = {"role": "user", "desc": processed_data['original_content']}
                dialogvo.append(new_entry)
                dialogvo.append(result_save)
            else:
                # 多轮对话模式，追加当前对话和结果
                if not isinstance(dialogvo, list):
                    dialogvo = [dialogvo]
                dialogvo.append(result_save)
            # 使用相同的标题，但保留原来的对话ID
            sqlitelog.set_dialog(user, model, "pic", title, json.dumps(dialogvo), dialog_id)
        except Exception as e:
            # 如果查询数据库出现错误，仍然按照原来逻辑处理
            app.logger.error(f"获取对话历史失败: {str(e)}")
            if not isinstance(dialogvo, list):
                dialogvo = [dialogvo]
            dialogvo.append(result_save)
            sqlitelog.set_dialog(user, model, "pic", title, json.dumps(dialogvo))
        return result_save, 200
    except json.JSONDecodeError:
        return {"msg": "api return json not ok"}, 200

@app.route('/never_guess_my_usage/split_his', methods=['POST'])
@require_auth
def dialog_his(user, password):
    # 根据用户名获取3日内历史纪录，[{日期+标题、类型}], 按id倒排
    app.logger.info(user)
    min_time_str = (datetime.now() - timedelta(days=5)).date()
    dialog_list = sqlitelog.get_dialog_list(user, min_time_str)
    dialog_list = [ {**item, "start_date": item["start_date"].strftime("%Y-%m-%d")} for item in dialog_list]
    return {"content": dialog_list}, 200

@app.route('/never_guess_my_usage/split_his_content', methods=['POST'])
@require_auth
def dialog_content(user, password):
    data = get_request_data()
    try:
        # 根据用户名+id获取历史纪录详情context
        id = data.get('dialogId')

        app.logger.info(user + "," + id)
        # 理想状态下是列表
        result = sqlitelog.get_dialog_context(user, int(id))
        context = json.loads(result.context)
        return {"content": {"chattype": result.chattype, "context": context}}
    except json.JSONDecodeError:
        return {"msg": "api return content not ok"}, 200


@app.route('/never_guess_my_usage/usage', methods=['GET', 'POST'])
@require_auth
def get_usage(user, password):
    """获取用户用量信息"""
    # 验证用户凭据在装饰器中已经完成

    api_key = sqlitelog.get_user_api_key(user)
    app.logger.info(api_key)
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
            today_usage = today_data.get('total_usage', 0)

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
@require_auth
def dialog_delete(user, password):
    data = get_request_data()
    """删除用户的历史会话（支持批量删除）"""
    dialog_ids_str = data.get('dialog_ids', '[]')

    # 解析并验证 dialog_ids
    dialog_ids = json.loads(dialog_ids_str)

    # 执行删除
    deleted_count = sqlitelog.delete_dialogs(user, dialog_ids)
    return {"success": True, "deleted_count": deleted_count}


@app.route('/never_guess_my_usage/update_dialog_title', methods=['POST'])
@require_auth
def update_dialog_title(user, password):
    """更新对话标题"""
    data = get_request_data()
    dialog_id_raw = data.get('dialog_id')
    dialog_id = int(dialog_id_raw) if dialog_id_raw is not None else None
    new_title = data.get('new_title', '').strip()

    # 验证参数
    if dialog_id is None or not new_title:
        return {"success": False, "msg": "dialog_id 和 new_title 参数不能为空"}, 200

    # 更新对话标题
    success = sqlitelog.update_dialog_title(user, dialog_id, new_title)

    if success:
        return {"success": True, "msg": "更新成功"}, 200
    else:
        return {"success": False, "msg": "更新失败，可能是对话不存在或不属于该用户"}, 200

@app.route('/never_guess_my_usage/system_prompt', methods=['GET'])
def system_prompt():
    return {"msg": "api return content not ok"}, 200


@app.route('/never_guess_my_usage/system_prompts_by_group', methods=['GET'])
def get_system_prompts_by_group():
    """按role_group分类获取系统提示词"""
    try:
        grouped_prompts = sqlitelog.get_system_prompts_by_group()
        return {"success": True, "groups": grouped_prompts}, 200
    except Exception as e:
        app.logger.error(f"获取按组分类的系统提示词失败: {str(e)}")
        return {"success": False, "msg": f"获取系统提示词失败: {str(e)}"}, 200


@app.route('/never_guess_my_usage/notifications', methods=['GET'])
def get_notifications():
    """获取通知公告列表，支持分页，按更新时间倒序排列"""
    try:
        # 获取分页参数
        page = request.args.get('page', 1, type=int)
        page_size = request.args.get('page_size', 10, type=int)
        status = request.args.get('status', 'active', type=str)  # 可选的状态过滤参数

        # 验证参数
        if page < 1:
            page = 1
        if page_size < 1 or page_size > 100:  # 限制每页最多100条
            page_size = 10

        # 计算偏移量
        offset = (page - 1) * page_size

        # 调用数据库函数获取通知列表
        notifications = sqlitelog.get_notification_list(
            status=status,
            limit=page_size,
            offset=offset
        )

        # 获取总数用于分页信息
        total_count = sqlitelog.get_notification_count(status=status)

        return {
            "success": True,
            "data": {
                "list": notifications,
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total": total_count,
                    "pages": (total_count + page_size - 1) // page_size if total_count > 0 else 1
                }
            }
        }, 200
    except Exception as e:
        app.logger.error(f"获取通知公告列表失败: {str(e)}")
        return {"success": False, "msg": f"获取通知公告列表失败: {str(e)}"}, 200

@app.route('/never_guess_my_usage/del_password', methods=['POST'])
@require_auth
def user_reset_password(user, password):
    """重置用户密码"""
    try:
        data = get_request_data()
        new_password = data.get('new_password', '').strip()
        if not new_password:
            return jsonify({"success": False, "msg": "新密码不能为空"})

        # 由于使用了require_auth装饰器，我们已经有了经过验证的用户信息
        # 只允许用户重置自己的密码
        current_user = user  # 从装饰器获得的用户名

        # 调用sqlitelog中的重置密码函数
        from sqlitelog import reset_user_password
        success, msg = reset_user_password(current_user, new_password)

        if success:
            return jsonify({"success": True, "msg": msg})
        else:
            return jsonify({"success": False, "msg": msg})

    except Exception as e:
        app.logger.error(f"重置密码失败: {str(e)}")
        return jsonify({"success": False, "msg": f"重置密码失败: {str(e)}"})

# 在应用启动时初始化数据库表
# 若不存在sqlite3 db，初始化
sqlitelog.init_db()

# 初始化模型元数据
try:
    from init.init_model_meta import init_model_meta_data
    init_model_meta_data()
except ImportError:
    print("警告: init_model_meta.py 文件不存在或导入失败，跳过模型元数据初始化")
except Exception as e:
    print(f"模型元数据初始化过程中发生错误: {e}")

# 注册 admin 路由（如果存在）
if admin_app:
    print("正在注册 admin 路由...")
    # 将 admin 路由复制到主应用
    rule_count = 0
    for rule in admin_app.url_map.iter_rules():
        try:
            # 获取视图函数
            view_func = admin_app.view_functions[rule.endpoint]
            # 注册到主应用，添加 /admin_api 前缀
            admin_rule = rule.rule
            if not admin_rule.startswith('/never_guess_my_usage'):
                admin_rule = '/never_guess_my_usage' + admin_rule
            # 使用新的 endpoint 名称避免冲突
            new_endpoint = f"admin_{rule.endpoint}"
            print(f"尝试注册路由: {admin_rule} -> {new_endpoint} (原endpoint: {rule.endpoint})")
            app.add_url_rule(admin_rule, endpoint=new_endpoint, view_func=view_func, methods=rule.methods)
            rule_count += 1
            print(f"成功注册路由: {admin_rule}")
        except Exception as e:
            print(f"跳过路由 {rule.rule}: {e}")
            import traceback
            traceback.print_exc()
    print(f"成功注册 {rule_count} 个 admin 路由")

if __name__ == '__main__':
    # 上传文件夹初始化
    # if not os.path.exists(conf["common"]["upload_dir"]):
    #     os.makedirs(conf["common"]["upload_dir"])
    app.run(host='0.0.0.0', port=39997)
