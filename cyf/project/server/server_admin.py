# Admin CRUD 接口服务
from flask import Flask, request, jsonify
from flask_cors import CORS
from functools import wraps
from datetime import datetime
from peewee import DoesNotExist, IntegrityError
import sqlitelog
from sqlitelog import ModelMeta, SystemPrompt, TestLimit, User, Notification

app = Flask(__name__, static_folder=None)
CORS(app, supports_credentials=True, origins=["*"])

def success_response(data=None, msg=None):
    """成功响应"""
    return jsonify({
        "success": True,
        "data": data,
        "msg": msg or "操作成功"
    })

def error_response(msg):
    """错误响应"""
    return jsonify({
        "success": False,
        "msg": msg
    })

def test_limit_to_dict(limit):
    """TestLimit 转字典"""
    return {
        'id': limit.id,
        'user_ip': limit.user_ip,
        'user_count': limit.user_count,
        'limit': limit.limit
    }

def user_to_dict(user):
    """User 转字典（排除敏感字段）"""
    return {
        'id': user.id,
        'username': user.username,
        'api_key': user.api_key,
        'role': user.role,
        'is_active': user.is_active,
        'created_at': user.created_at.strftime('%Y-%m-%d %H:%M:%S') if user.created_at else None,
        'updated_at': user.updated_at.strftime('%Y-%m-%d %H:%M:%S') if user.updated_at else None
    }

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
            return json_data
        else:
            # 如果JSON数据无效，回退到request.values
            return request.values
    else:
        # 否则是表单数据或URL参数
        return request.values

def require_admin_auth(f):
    """管理员认证装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        data = get_request_data()
        user = data.get('user', '').strip()
        password = data.get('password', '').strip()
        # 只允许管理员角色登录
        success, error_msg, _ = sqlitelog.verify_user_password(user, password, "admin")
        if not success:
            return jsonify({"success": False, "msg": error_msg or "认证失败"})
        return f(*args, **kwargs)
    return decorated_function

# ==================== ModelMeta 接口 ====================
@app.route('/model_meta/list', methods=['GET'])
@require_admin_auth
def model_meta_list():
    """获取模型元数据列表"""
    try:
        # 获取过滤参数
        recommend = request.args.get('recommend')
        status_valid = request.args.get('status_valid')
        
        # 转换布尔值
        if recommend is not None:
            recommend = recommend.lower() in ('true', '1', 'yes')
        if status_valid is not None:
            status_valid = status_valid.lower() in ('true', '1', 'yes')
        
        # 查询数据
        models = sqlitelog.get_model_meta_list(recommend=recommend, status_valid=status_valid)
        return success_response(data=models)
    except Exception as e:
        return error_response(f"获取模型列表失败: {str(e)}")

@app.route('/model_meta/get/<int:model_id>', methods=['GET'])
@require_admin_auth
def model_meta_get(model_id):
    """获取单个模型元数据"""
    try:
        model = ModelMeta.get_by_id(model_id)
        return success_response(data=model.to_dict())
    except DoesNotExist:
        return error_response("模型不存在")
    except Exception as e:
        return error_response(f"获取模型失败: {str(e)}")

@app.route('/model_meta/create', methods=['POST'])
@require_admin_auth
def model_meta_create():
    """创建模型元数据"""
    try:
        data = get_request_data()
        model_name = data.get('model_name', '').strip()
        # 1-文本 2-图像
        model_type = int(data.get('model_type', '').strip())
        if not model_name:
            return error_response("模型名称不能为空")

        # 转换布尔值
        recommend = data.get('recommend', 'false').lower() in ('true', '1', 'yes')
        status_valid = data.get('status_valid', 'true').lower() in ('true', '1', 'yes')

        model = ModelMeta.create(
            model_name=model_name,
            model_desc=data.get('model_desc', ''),
            model_type=model_type,
            recommend=recommend,
            status_valid=status_valid
        )
        return success_response(data=model.to_dict(), msg="模型创建成功")
    except IntegrityError:
        return error_response("模型名称已存在")
    except Exception as e:
        return error_response(f"创建模型失败: {str(e)}")

@app.route('/model_meta/update', methods=['POST'])
@require_admin_auth
def model_meta_update():
    """更新模型元数据"""
    try:
        data = get_request_data()
        model_id = data.get('id')
        if not model_id:
            return error_response("模型ID不能为空")

        model = ModelMeta.get_by_id(int(model_id))

        # 更新字段
        if 'model_name' in data:
            model.model_name = data['model_name'].strip()
        if 'model_desc' in data:
            model.model_desc = data['model_desc']
        if 'recommend' in data:
            model.recommend = data['recommend'].lower() in ('true', '1', 'yes')
        if 'status_valid' in data:
            model.status_valid = data['status_valid'].lower() in ('true', '1', 'yes')

        model.save()
        return success_response(data=model.to_dict(), msg="模型更新成功")
    except DoesNotExist:
        return error_response("模型不存在")
    except IntegrityError:
        return error_response("模型名称已存在")
    except Exception as e:
        return error_response(f"更新模型失败: {str(e)}")

@app.route('/model_meta/delete', methods=['POST'])
@require_admin_auth
def model_meta_delete():
    """删除模型元数据"""
    try:
        data = get_request_data()
        model_id = data.get('id')
        if not model_id:
            return error_response("模型ID不能为空")

        model = ModelMeta.get_by_id(int(model_id))
        model.delete_instance()
        return success_response(msg="模型删除成功")
    except DoesNotExist:
        return error_response("模型不存在")
    except Exception as e:
        return error_response(f"删除模型失败: {str(e)}")

# ==================== SystemPrompt 接口 ====================
@app.route('/system_prompt/list', methods=['GET'])
@require_admin_auth
def system_prompt_list():
    """获取系统提示词列表"""
    try:
        # 获取过滤参数
        role_group = request.args.get('role_group')
        status_valid = request.args.get('status_valid')
        
        # 转换布尔值
        if status_valid is not None:
            status_valid = status_valid.lower() in ('true', '1', 'yes')
        
        # 构建查询
        query = SystemPrompt.select()
        if role_group:
            query = query.where(SystemPrompt.role_group == role_group)
        if status_valid is not None:
            query = query.where(SystemPrompt.status_valid == status_valid)
        
        # 返回字典格式的结果列表
        prompts = [prompt.to_dict() for prompt in query.dicts().iterator()]
        return success_response(data=prompts)
    except Exception as e:
        return error_response(f"获取系统提示词列表失败: {str(e)}")

@app.route('/system_prompt/get/<int:prompt_id>', methods=['GET'])
@require_admin_auth
def system_prompt_get(prompt_id):
    """获取单个系统提示词"""
    try:
        prompt = SystemPrompt.get_by_id(prompt_id)
        return success_response(data=prompt.to_dict())
    except DoesNotExist:
        return error_response("系统提示词不存在")
    except Exception as e:
        return error_response(f"获取系统提示词失败: {str(e)}")

@app.route('/system_prompt/create', methods=['POST'])
@require_admin_auth
def system_prompt_create():
    """创建系统提示词"""
    try:
        data = request.form
        role_name = data.get('role_name', '').strip()
        role_group = data.get('role_group', '').strip()
        
        if not role_name or not role_group:
            return error_response("角色名称和角色分组不能为空")
        
        # 转换布尔值
        status_valid = data.get('status_valid', 'true').lower() in ('true', '1', 'yes')
        
        prompt = SystemPrompt.create(
            role_name=role_name,
            role_group=role_group,
            role_desc=data.get('role_desc', ''),
            role_content=data.get('role_content', ''),
            status_valid=status_valid
        )
        return success_response(data=prompt.to_dict(), msg="系统提示词创建成功")
    except IntegrityError:
        return error_response("该角色名称和分组组合已存在")
    except Exception as e:
        return error_response(f"创建系统提示词失败: {str(e)}")

@app.route('/system_prompt/update', methods=['POST'])
@require_admin_auth
def system_prompt_update():
    """更新系统提示词"""
    try:
        data = get_request_data()
        prompt_id = data.get('id')
        if not prompt_id:
            return error_response("系统提示词ID不能为空")

        prompt = SystemPrompt.get_by_id(int(prompt_id))

        # 更新字段
        if 'role_name' in data:
            prompt.role_name = data['role_name'].strip()
        if 'role_group' in data:
            prompt.role_group = data['role_group'].strip()
        if 'role_desc' in data:
            prompt.role_desc = data['role_desc']
        if 'role_content' in data:
            prompt.role_content = data['role_content']
        if 'status_valid' in data:
            prompt.status_valid = data['status_valid'].lower() in ('true', '1', 'yes')

        prompt.save()
        return success_response(data=prompt.to_dict(), msg="系统提示词更新成功")
    except DoesNotExist:
        return error_response("系统提示词不存在")
    except IntegrityError:
        return error_response("该角色名称和分组组合已存在")
    except Exception as e:
        return error_response(f"更新系统提示词失败: {str(e)}")

@app.route('/system_prompt/delete', methods=['POST'])
@require_admin_auth
def system_prompt_delete():
    """删除系统提示词"""
    try:
        data = get_request_data()
        prompt_id = data.get('id')
        if not prompt_id:
            return error_response("系统提示词ID不能为空")

        prompt = SystemPrompt.get_by_id(int(prompt_id))
        prompt.delete_instance()
        return success_response(msg="系统提示词删除成功")
    except DoesNotExist:
        return error_response("系统提示词不存在")
    except Exception as e:
        return error_response(f"删除系统提示词失败: {str(e)}")

# ==================== TestLimit 接口 ====================
@app.route('/test_limit/list', methods=['GET'])
@require_admin_auth
def test_limit_list():
    """获取测试限制列表"""
    try:
        query = TestLimit.select().order_by(TestLimit.id.desc())
        limits = [test_limit_to_dict(limit) for limit in query.iterator()]
        return success_response(data=limits)
    except Exception as e:
        return error_response(f"获取测试限制列表失败: {str(e)}")

@app.route('/test_limit/get/<int:limit_id>', methods=['GET'])
@require_admin_auth
def test_limit_get(limit_id):
    """获取单个测试限制"""
    try:
        limit = TestLimit.get_by_id(limit_id)
        return success_response(data=test_limit_to_dict(limit))
    except DoesNotExist:
        return error_response("测试限制不存在")
    except Exception as e:
        return error_response(f"获取测试限制失败: {str(e)}")

@app.route('/test_limit/create', methods=['POST'])
@require_admin_auth
def test_limit_create():
    """创建测试限制"""
    try:
        data = get_request_data()
        user_ip = data.get('user_ip', '').strip()
        if not user_ip:
            return error_response("用户IP不能为空")
        
        try:
            user_count = int(data.get('user_count', 0))
            limit = int(data.get('limit', 20))
        except ValueError:
            return error_response("使用次数和限制值必须是数字")
        
        test_limit = TestLimit.create(
            user_ip=user_ip,
            user_count=user_count,
            limit=limit
        )
        return success_response(data=test_limit_to_dict(test_limit), msg="测试限制创建成功")
    except IntegrityError:
        return error_response("该IP已存在限制记录")
    except Exception as e:
        return error_response(f"创建测试限制失败: {str(e)}")

@app.route('/test_limit/update', methods=['POST'])
@require_admin_auth
def test_limit_update():
    """更新测试限制"""
    try:
        data = get_request_data()
        limit_id = data.get('id')
        if not limit_id:
            return error_response("限制ID不能为空")
        
        test_limit = TestLimit.get_by_id(int(limit_id))
        
        # 更新字段
        if 'user_ip' in data:
            test_limit.user_ip = data['user_ip'].strip()
        if 'user_count' in data:
            try:
                test_limit.user_count = int(data['user_count'])
            except ValueError:
                return error_response("使用次数必须是数字")
        if 'limit' in data:
            try:
                test_limit.limit = int(data['limit'])
            except ValueError:
                return error_response("限制值必须是数字")
        
        test_limit.save()
        return success_response(data=test_limit_to_dict(test_limit), msg="测试限制更新成功")
    except DoesNotExist:
        return error_response("测试限制不存在")
    except IntegrityError:
        return error_response("该IP已存在限制记录")
    except Exception as e:
        return error_response(f"更新测试限制失败: {str(e)}")

@app.route('/test_limit/delete', methods=['POST'])
@require_admin_auth
def test_limit_delete():
    """删除测试限制"""
    try:
        data = get_request_data()
        limit_id = data.get('id')
        if not limit_id:
            return error_response("限制ID不能为空")
        
        test_limit = TestLimit.get_by_id(int(limit_id))
        test_limit.delete_instance()
        return success_response(msg="测试限制删除成功")
    except DoesNotExist:
        return error_response("测试限制不存在")
    except Exception as e:
        return error_response(f"删除测试限制失败: {str(e)}")

@app.route('/test_limit/reset', methods=['POST'])
@require_admin_auth
def test_limit_reset():
    """重置测试限制"""
    try:
        data = get_request_data()
        limit_id = data.get('id')
        user_ip = data.get('user_ip')
        reset_all = data.get('reset_all', 'false').lower() in ('true', '1', 'yes')
        
        if reset_all:
            # 重置所有记录
            updated_count = TestLimit.update(user_count=0).execute()
            return success_response(msg=f"成功重置 {updated_count} 条测试限制记录")
        elif limit_id:
            # 重置指定ID
            test_limit = TestLimit.get_by_id(int(limit_id))
            test_limit.user_count = 0
            test_limit.save()
            return success_response(data=test_limit_to_dict(test_limit), msg="测试限制重置成功")
        elif user_ip:
            # 重置指定IP
            updated_count = TestLimit.update(user_count=0).where(TestLimit.user_ip == user_ip).execute()
            if updated_count > 0:
                return success_response(msg=f"成功重置IP {user_ip} 的测试限制")
            else:
                return error_response("未找到该IP的测试限制记录")
        else:
            return error_response("请提供ID、IP或设置reset_all=true")
    except DoesNotExist:
        return error_response("测试限制不存在")
    except Exception as e:
        return error_response(f"重置测试限制失败: {str(e)}")

# ==================== User 接口 ====================
@app.route('/user/list', methods=['GET'])
@require_admin_auth
def user_list():
    """获取用户列表"""
    try:
        query = User.select().order_by(User.id.desc())
        users = [user_to_dict(user) for user in query.iterator()]
        return success_response(data=users)
    except Exception as e:
        return error_response(f"获取用户列表失败: {str(e)}")

@app.route('/user/get/<int:user_id>', methods=['GET'])
@require_admin_auth
def user_get(user_id):
    """获取单个用户信息"""
    try:
        user = User.get_by_id(user_id)
        return success_response(data=user_to_dict(user))
    except DoesNotExist:
        return error_response("用户不存在")
    except Exception as e:
        return error_response(f"获取用户信息失败: {str(e)}")

@app.route('/user/create', methods=['POST'])
@require_admin_auth
def user_create():
    """创建用户"""
    try:
        data = get_request_data()
        username = data.get('username', '').strip()
        new_password = data.get('new_password', '').strip()
        
        if not username or not new_password:
            return error_response("用户名和新密码不能为空")
        
        # 检查用户名是否已存在
        if User.select().where(User.username == username).exists():
            return error_response("用户名已存在")
        
        # 生成API密钥（可选）
        api_key = data.get('api_key', '').strip() or None
        
        # 创建用户
        user = sqlitelog.create_user(username, new_password, api_key)
        
        # 更新其他字段
        if 'role' in data:
            user.role = data['role']
        if 'is_active' in data:
            user.is_active = data['is_active'].lower() in ('true', '1', 'yes')
        
        user.save()
        return success_response(data=user_to_dict(user), msg="用户创建成功")
    except Exception as e:
        return error_response(f"创建用户失败: {str(e)}")

@app.route('/user/update', methods=['POST'])
@require_admin_auth
def user_update():
    """更新用户信息"""
    try:
        data = get_request_data()
        user_id = data.get('id')
        if not user_id:
            return error_response("用户ID不能为空")
        
        user = User.get_by_id(int(user_id))
        
        # 更新字段
        if 'username' in data:
            new_username = data['username'].strip()
            if new_username != user.username:
                if User.select().where(User.username == new_username).exists():
                    return error_response("用户名已存在")
                user.username = new_username
        
        if 'role' in data:
            user.role = data['role']
        
        if 'is_active' in data:
            user.is_active = data['is_active'].lower() in ('true', '1', 'yes')
        
        if 'api_key' in data:
            user.api_key = data['api_key'].strip() or None
        
        # 如果提供了新密码，重新哈希
        if 'new_password' in data and data['new_password'].strip():
            new_password = data['new_password'].strip()
            password_hash, salt = User.hash_password(new_password)
            user.password_hash = password_hash
            user.salt = salt
        
        user.updated_at = datetime.now()
        user.save()
        return success_response(data=user_to_dict(user), msg="用户信息更新成功")
    except DoesNotExist:
        return error_response("用户不存在")
    except Exception as e:
        return error_response(f"更新用户信息失败: {str(e)}")

@app.route('/user/delete', methods=['POST'])
@require_admin_auth
def user_delete():
    """删除用户（默认软删除）"""
    try:
        data = get_request_data()
        user_id = data.get('id')
        if not user_id:
            return error_response("用户ID不能为空")
        
        hard_delete = data.get('hard_delete', 'false').lower() in ('true', '1', 'yes')
        
        if hard_delete:
            # 硬删除
            user = User.get_by_id(int(user_id))
            user.delete_instance()
            return success_response(msg="用户永久删除成功")
        else:
            # 软删除（标记为未激活）
            user = User.get_by_id(int(user_id))
            user.is_active = False
            user.updated_at = datetime.now()
            user.save()
            return success_response(msg="用户已标记为未激活")
    except DoesNotExist:
        return error_response("用户不存在")
    except Exception as e:
        return error_response(f"删除用户失败: {str(e)}")


# ==================== Notification 接口 ====================
def notification_to_dict(notification):
    """Notification 转字典"""
    return {
        'id': notification.id,
        'title': notification.title,
        'content': notification.content,
        'publish_time': notification.publish_time.strftime('%Y-%m-%d %H:%M:%S') if notification.publish_time else None,
        'status': notification.status,
        'priority': notification.priority,
        'created_at': notification.created_at.strftime('%Y-%m-%d %H:%M:%S') if notification.created_at else None,
        'updated_at': notification.updated_at.strftime('%Y-%m-%d %H:%M:%S') if notification.updated_at else None
    }

@app.route('/notification/list', methods=['GET'])
@require_admin_auth
def notification_list():
    """获取通知公告列表"""
    try:
        # 获取过滤参数
        status = request.args.get('status')
        limit = request.args.get('limit', type=int)
        offset = request.args.get('offset', type=int)
        
        # 查询数据
        notifications = sqlitelog.get_notification_list(status=status, limit=limit, offset=offset)
        return success_response(data=notifications)
    except Exception as e:
        return error_response(f"获取通知列表失败: {str(e)}")

@app.route('/notification/active_list', methods=['GET'])
def notification_active_list():
    """获取有效的通知公告列表（无需认证）"""
    try:
        limit = request.args.get('limit', 10, type=int)
        notifications = sqlitelog.get_active_notifications(limit=limit)
        return success_response(data=notifications)
    except Exception as e:
        return error_response(f"获取有效通知列表失败: {str(e)}")

@app.route('/notification/get/<int:notification_id>', methods=['GET'])
@require_admin_auth
def notification_get(notification_id):
    """获取单个通知公告"""
    try:
        notification = Notification.get_by_id(notification_id)
        return success_response(data=notification_to_dict(notification))
    except DoesNotExist:
        return error_response("通知不存在")
    except Exception as e:
        return error_response(f"获取通知失败: {str(e)}")

@app.route('/notification/create', methods=['POST'])
@require_admin_auth
def notification_create():
    """创建通知公告"""
    try:
        data = get_request_data()
        title = data.get('title', '').strip()
        content = data.get('content', '').strip()
        
        if not title or not content:
            return error_response("通知标题和内容不能为空")
        
        # 转换优先级
        try:
            priority = int(data.get('priority', 0))
        except ValueError:
            priority = 0
        
        # 状态默认为active
        status = data.get('status', 'active').strip()
        if status not in ['active', 'inactive']:
            status = 'active'
        
        notification = sqlitelog.create_notification(
            title=title,
            content=content,
            priority=priority,
            status=status
        )
        return success_response(data=notification_to_dict(notification), msg="通知创建成功")
    except Exception as e:
        return error_response(f"创建通知失败: {str(e)}")

@app.route('/notification/update', methods=['POST'])
@require_admin_auth
def notification_update():
    """更新通知公告"""
    try:
        data = get_request_data()
        notification_id = data.get('id')
        if not notification_id:
            return error_response("通知ID不能为空")
        
        # 构建更新字段
        update_fields = {}
        
        if 'title' in data:
            update_fields['title'] = data['title'].strip()
        if 'content' in data:
            update_fields['content'] = data['content'].strip()
        if 'priority' in data:
            try:
                update_fields['priority'] = int(data['priority'])
            except ValueError:
                return error_response("优先级必须是数字")
        if 'status' in data:
            status = data['status'].strip()
            if status in ['active', 'inactive']:
                update_fields['status'] = status
            else:
                return error_response("状态必须是active或inactive")
        
        if not update_fields:
            return error_response("没有要更新的字段")
        
        success = sqlitelog.update_notification(int(notification_id), **update_fields)
        if success:
            notification = Notification.get_by_id(int(notification_id))
            return success_response(data=notification_to_dict(notification), msg="通知更新成功")
        else:
            return error_response("通知不存在")
    except Exception as e:
        return error_response(f"更新通知失败: {str(e)}")

@app.route('/notification/delete', methods=['POST'])
@require_admin_auth
def notification_delete():
    """删除通知公告"""
    try:
        data = get_request_data()
        notification_id = data.get('id')
        if not notification_id:
            return error_response("通知ID不能为空")
        
        success = sqlitelog.delete_notification(int(notification_id))
        if success:
            return success_response(msg="通知删除成功")
        else:
            return error_response("通知不存在")
    except Exception as e:
        return error_response(f"删除通知失败: {str(e)}")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=39998, debug=True)