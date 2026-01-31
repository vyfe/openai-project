# 实现 server_admin.py - Admin CRUD 接口

## 任务概述
完成 `cyf/project/server/server_admin.py`，为 ModelMeta、SystemPrompt、TestLimit、User 四个数据库表实现 CRUD 后端接口，通过 server.py 引用。

## 关键文件
| 文件 | 说明 |
|------|------|
| `cyf/project/server/server_admin.py` | **主要修改** - 当前仅有注释，需完整实现 |
| `cyf/project/server/sqlitelog.py` | 数据库模型定义（第38-117行） |
| `cyf/project/server/server.py` | 路由注册逻辑（第25-30行、1097-1107行） |

## 数据库模型概览
| 模型 | 字段 | 特殊说明 |
|------|------|----------|
| ModelMeta | model_name(唯一), model_desc, recommend, status_valid | 已有 `to_dict()` |
| SystemPrompt | role_name, role_group, role_desc, role_content, status_valid | 已有 `to_dict()`，唯一索引(role_name, role_group) |
| TestLimit | user_ip(唯一), user_count, limit | **无 to_dict()，需实现辅助函数** |
| User | username(唯一), password_hash, salt, api_key, is_active, created_at, updated_at | 已有 `hash_password()`, `verify_password()` |

## 实现步骤

### 1. 基础架构搭建
```python
from flask import Flask, request, jsonify
from flask_cors import CORS
from functools import wraps
from datetime import datetime
from peewee import DoesNotExist, IntegrityError
import sqlitelog
from sqlitelog import ModelMeta, SystemPrompt, TestLimit, User

app = Flask(__name__)
CORS(app, supports_credentials=True, origins=["*"])
```

### 2. 辅助函数
- `success_response(data=None, msg=None)` - 成功响应
- `error_response(msg)` - 错误响应
- `test_limit_to_dict(limit)` - TestLimit 转字典
- `user_to_dict(user)` - User 转字典（排除敏感字段）

### 3. 认证装饰器
```python
def require_admin_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = request.values.get('user', '').strip()
        password = request.values.get('password', '').strip()
        success, error_msg, _ = sqlitelog.verify_user_password(user, password)
        if not success:
            return jsonify({"success": False, "msg": error_msg or "认证失败"})
        return f(*args, **kwargs)
    return decorated_function
```

### 4. API 接口汇总 (共22个)

#### ModelMeta (5个)
| 路由 | 方法 | 最终URL | 说明 |
|------|------|---------|------|
| `/model_meta/list` | GET | `/admin_api/model_meta/list` | 支持 recommend/status_valid 过滤 |
| `/model_meta/get/<id>` | GET | `/admin_api/model_meta/get/<id>` | |
| `/model_meta/create` | POST | `/admin_api/model_meta/create` | 必填: model_name |
| `/model_meta/update` | POST | `/admin_api/model_meta/update` | 必填: id |
| `/model_meta/delete` | POST | `/admin_api/model_meta/delete` | 必填: id |

#### SystemPrompt (5个)
| 路由 | 方法 | 最终URL | 说明 |
|------|------|---------|------|
| `/system_prompt/list` | GET | `/admin_api/system_prompt/list` | 支持 role_group/status_valid 过滤 |
| `/system_prompt/get/<id>` | GET | `/admin_api/system_prompt/get/<id>` | |
| `/system_prompt/create` | POST | `/admin_api/system_prompt/create` | 必填: role_name, role_group |
| `/system_prompt/update` | POST | `/admin_api/system_prompt/update` | 必填: id |
| `/system_prompt/delete` | POST | `/admin_api/system_prompt/delete` | 必填: id |

#### TestLimit (6个)
| 路由 | 方法 | 最终URL | 说明 |
|------|------|---------|------|
| `/test_limit/list` | GET | `/admin_api/test_limit/list` | |
| `/test_limit/get/<id>` | GET | `/admin_api/test_limit/get/<id>` | |
| `/test_limit/create` | POST | `/admin_api/test_limit/create` | 必填: user_ip |
| `/test_limit/update` | POST | `/admin_api/test_limit/update` | 必填: id |
| `/test_limit/delete` | POST | `/admin_api/test_limit/delete` | 必填: id |
| `/test_limit/reset` | POST | `/admin_api/test_limit/reset` | 支持 id/user_ip/reset_all |

#### User (6个，特殊处理)
| 路由 | 方法 | 最终URL | 说明 |
|------|------|---------|------|
| `/user/list` | GET | `/admin_api/user/list` | 不返回 password_hash/salt |
| `/user/get/<id>` | GET | `/admin_api/user/get/<id>` | 不返回 password_hash/salt |
| `/user/create` | POST | `/admin_api/user/create` | 必填: username, new_password；密码哈希处理 |
| `/user/update` | POST | `/admin_api/user/update` | 必填: id；密码更新时重新哈希 |
| `/user/delete` | POST | `/admin_api/user/delete` | 默认软删除，支持 hard_delete=true |
| `/user/reset_password` | POST | `/admin_api/user/reset_password` | 必填: new_password + (id 或 username) |

## 响应格式
```json
// 成功
{"success": true, "data": {...}, "msg": "操作成功"}

// 失败
{"success": false, "msg": "错误信息"}
```

## 验证方式
1. 启动后端服务:
   ```bash
   cd cyf/project/server && python server.py
   ```

2. 测试接口示例:
   ```bash
   # ModelMeta 列表
   curl "http://localhost:39997/admin_api/model_meta/list?user=xxx&password=xxx"

   # 创建用户
   curl -X POST "http://localhost:39997/admin_api/user/create" \
     -d "user=admin&password=adminpwd&username=newuser&new_password=newpwd"

   # 重置密码
   curl -X POST "http://localhost:39997/admin_api/user/reset_password" \
     -d "user=admin&password=adminpwd&username=target_user&new_password=newpwd123"
   ```

3. 验证所有 22 个接口正常响应
