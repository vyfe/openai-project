# 用户表迁移计划：从配置文件到数据库

## 概述

将用户认证数据从配置文件 (`conf/conf.ini`) 迁移到 SQLite 数据库，同时保持向后兼容性。

---

## 文件修改清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `cyf/project/server/sqlitelog.py` | 修改 | 添加 User 模型和 CRUD 函数 |
| `cyf/project/server/server.py` | 修改 | 更新认证逻辑为混合模式 |
| `cyf/project/server/init_user_data.py` | **新建** | 数据迁移脚本 |

---

## 阶段 1：创建 User 模型 (`sqlitelog.py`)

### 1.1 添加导入 (文件顶部)
```python
import hashlib
import secrets
```

### 1.2 在 `TestLimit` 模型之后添加 `User` 模型 (约第92行后)
```python
class User(Model):
    username = CharField(unique=True)      # 用户名
    password_hash = CharField()            # 密码哈希值
    salt = CharField()                     # 密码盐值
    api_key = CharField(null=True)         # 用户专属API密钥
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
```

### 1.3 修改 `init_db()` 函数 (约第96行)
```python
db.create_tables([Log, Dialog, ModelMeta, SystemPrompt, TestLimit, User], safe=True)
```

### 1.4 添加用户 CRUD 函数 (文件末尾)
```python
def get_user_by_username(username: str):
    try:
        return User.get(User.username == username, User.is_active == True)
    except DoesNotExist:
        return None

def verify_user_password(username: str, password: str) -> tuple:
    user = get_user_by_username(username)
    if not user:
        return False, "用户不存在或未授权", None
    if not user.verify_password(password):
        return False, "密码错误", None
    return True, None, user

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
```

---

## 阶段 2：创建迁移脚本 (`init_user_data.py`)

新建文件 `cyf/project/server/init_user_data.py`，参考 `init_model_meta.py` 模式：

- `parse_users_from_config()` - 从配置文件解析用户
- `migrate_users_to_db()` - 迁移用户到数据库（密码哈希处理）
- `print_current_users()` - 打印当前用户

---

## 阶段 3：修改认证逻辑 (`server.py`)

### 3.1 添加导入 (约第19行后)
```python
from sqlitelog import user_exists_in_db, verify_user_password, get_user_api_key, get_all_active_users
```

### 3.2 重构用户加载逻辑 (替换第45-75行)

添加混合认证模式：
```python
USE_DB_AUTH = False  # 全局标记

def load_users_from_config():
    # 原有的配置文件解析逻辑
    ...

def init_user_auth():
    global USE_DB_AUTH
    sqlitelog.init_db()
    if sqlitelog.user_exists_in_db():
        USE_DB_AUTH = True
    else:
        load_users_from_config()
        USE_DB_AUTH = False
```

### 3.3 修改 `verify_credentials()` (第202-207行)
```python
def verify_credentials(user, password):
    if USE_DB_AUTH:
        success, error_msg, _ = sqlitelog.verify_user_password(user, password)
        return success, error_msg
    else:
        # 原有逻辑
        ...
```

### 3.4 修改 `get_client_for_user()` (第213-222行)
```python
def get_client_for_user(username: str) -> OpenAI:
    if USE_DB_AUTH:
        api_key = sqlitelog.get_user_api_key(username)
    else:
        api_key = user_api_keys.get(username)
    # 后续逻辑不变
    ...
```

### 3.5 修改 `/login` 端点 (第437-449行)
使用统一的 `verify_credentials()` 函数替代直接字典访问。

---

## 验证方法

```bash
# 1. 启动服务
cd cyf/project/server && python server.py

# 2. 运行迁移脚本
python init_user_data.py

# 3. 测试登录
curl -X POST http://localhost:39997/never_guess_my_usage/login \
  -d "user=admin&password=admin123"

# 4. 测试错误密码
curl -X POST http://localhost:39997/never_guess_my_usage/login \
  -d "user=admin&password=wrongpassword"
```

---

## 回滚方案

如果出现问题：
1. 在 `server.py` 中手动设置 `USE_DB_AUTH = False`
2. 重启服务（将回退到配置文件认证）
