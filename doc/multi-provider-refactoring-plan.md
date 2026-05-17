# Multi-Provider Architecture Refactoring Plan

## Context

当前后端虽然支持多 API Host 切换+黑名单机制，但本质上是**同一服务商的多个节点**——所有 Host 共享同一个 API Key，模型列表也是从单一 Host 拉取后全局缓存。用户需要引入真正独立的 API 服务商（各自独立节点、Key、模型列表、用户授权），因此需要将"Provider"提升为一等实体。

## 核心设计决策

| 决策点 | 方案 |
|--------|------|
| 用户-Provider 关系 | 多对多（用户可被分配到一个或多个 Provider，有默认 Provider）|
| 模型-Provider 映射 | ModelMeta 表增加 `provider_id` 外键，模型缓存按 Provider 独立维护 |
| Provider 切换 | 前端增加 Provider 选择器，用户手动选择；也可由模型名自动路由 |
| 用量/计费 | 按 Provider 独立查询后聚合展示 |
| 向后兼容 | 完全兼容——无 `[provider.*]` 配置时自动从旧 `[api]` 段创建单 Provider |

## 改造范围总览（7 个层面 30+ 项变更）

### 1. 数据模型层（新增 2 个实体，修改 2 个实体）

**新增 `ApiProvider` 实体** (`model/entities.py`)
```python
class ApiProvider(BaseModel):
    provider_name = CharField(unique=True)   # 标识名，如 "gpt-ge", "vveai"
    provider_label = CharField()             # 显示名，如 "GPT.GE Japan"
    api_key = CharField()                    # Provider 级默认 API Key
    api_hosts = TextField()                  # JSON array 多节点 URL
    exclude_keywords = TextField(default="")  # 模型过滤关键词
    billing_mode = CharField(default="timestamp")
    usd_to_cny_rate = FloatField(default=7.25)
    is_active = BooleanField(default=True)
    priority = IntegerField(default=0)       # 自动选择优先级
    created_at / updated_at
```

**新增 `UserProviderMapping` 关联表** (`model/entities.py`)
```python
class UserProviderMapping(BaseModel):
    user_id = IntegerField()
    provider_id = IntegerField()
    # 联合唯一索引 (user_id, provider_id)
```

**修改 `User` 实体**：增加 `default_provider_id` 字段
**修改 `ModelMeta` 实体**：增加 `provider_id` 字段，联合唯一索引改为 `(model_name, provider_id)`

### 2. 配置层（Settings + Runtime）

**`conf/settings.py` 改造**：
- 新增 `_parse_providers()` 函数，解析 `[provider.xxx]` 配置段
- Settings dataclass 新增 `providers: list[dict]` 和 `default_provider_name: str`
- 向后兼容：无 provider 段时自动从 `[api]` 段构建单 provider

**`conf/conf.ini` 新格式**：
```ini
[api]
api_key=sk-...      # 保留，作为向后兼容
api_host=https://...

[provider.gpt-ge]
label=GPT.GE
api_key=sk-...
hosts=https://jp.gpt.ge/v1,https://api.gpt.ge/v1
exclude_keywords=instruct,realtime,audio
priority=10

[provider.vveai]
label=VVEAI
api_key=sk-...
hosts=https://api.vveai.com/v1
priority=5
```

**`conf/runtime.py` 改造**：
- 新增 `ProviderRuntime` dataclass（封装单个 Provider 的运行时状态：clients、host_blacklist、model_cache、blacklist_lock）
- `RuntimeState` 新增 `providers: dict[str, ProviderRuntime]`
- 新增 `build_providers()` 方法取代 `build_clients()`
- 保留旧的 `clients`、`api_host_blacklist`、`model_cache` 字段用于向后兼容

### 3. Provider 服务层（核心重构）

**新建 `service/provider_service.py`**——从 `host_service.py` 提取并增强：

| 函数 | 职责 |
|------|------|
| `get_user_providers(username)` | 查询用户可访问的 Provider 列表 |
| `get_client_for_user(username, model_name?)` | 返回 `(client, host_idx, provider_name)`，支持按模型名自动路由 |
| `pick_random_host(provider)` | 在 provider 内选随机非黑名单节点 |
| `is_host_blacklisted(provider, url_index)` | 检查 provider 内特定节点是否被黑 |
| `blacklist_host(provider_name, url_index)` | 黑名单 provider 的特定节点 |
| `resolve_model_to_provider(model_name, user_providers)` | 根据模型名找到对应 Provider |
| `get_user_default_provider(username)` | 获取用户默认 Provider |

**修改 `service/host_service.py`**：现有函数变为薄包装，内部委托给 `provider_service`，保持签名不变

### 4. 模型服务层

**`service/model_service.py` 重大改造**：

| 函数 | 变化 |
|------|------|
| `get_cached_models(provider_name)` | **改为按 Provider 拉取和缓存**，每个 Provider 独立 TTL |
| `get_cached_models_for_user(username)` | **新增**——聚合用户所有 Provider 的模型列表，去重，冲突时加前缀 |
| `is_valid_model(model_name, provider_name?)` | 支持按 Provider 检查或全局检查 |
| `get_grouped_models(username?)` | 支持按用户返回其可见的模型分组 |
| `invalidate_model_cache(provider_name?)` | 支持按 Provider 或全局失效 |

### 5. 业务服务层

**`service/chat_service.py`**：`get_client_for_user` 调用改为新签名，获取 `provider_name`，传递给错误处理

**`service/stream_service.py`**：同上

**`service/image_service.py`**：同上

**`service/common_service.py`**：`handle_api_exception` 签名增加 `provider_name` 参数，改为调用 `provider_service.blacklist_host(provider_name, url_index)`

**`service/usage_service.py`**：重构为按 Provider 独立查询用量，按用户所有 Provider 聚合返回，同时返回 `per_provider` 明细

**`service/bootstrap_service.py`**：`build_clients()` → `build_providers()`，初始化 Provider 黑名单清理线程

### 6. 路由层

**`routes/public_routes.py`**：
- `/models` 和 `/models/grouped`：支持按用户返回其 Provider 的模型
- 新增 `GET /providers`：返回用户可用的 Provider 列表（不含 Key）

**`routes/admin_routes.py`**：
- 新增 Provider CRUD：`/provider/list`、`/provider/create`、`/provider/update`、`/provider/delete`
- 新增 `/provider/refresh_models`：手动刷新 Provider 模型缓存
- 新增 `/user/<id>/providers` GET/POST：管理用户-Provider 关联
- 修改 User create/update：支持 `provider_ids` 和 `default_provider_id`
- 修改 `/runtime/overview`：展示每个 Provider 的节点状态、模型缓存状态

### 7. 前端改造

| 组件/文件 | 变更 |
|-----------|------|
| `services/adminApi.ts` | 新增 `providerAPI`、`userProviderAPI` |
| **新建** `components/admin/ProviderTable.vue` | Provider CRUD 管理表格 |
| `components/admin/UserTable.vue` | 用户编辑对话框增加 Provider 分配（多选+默认选择）|
| `components/admin/RuntimeOverview.vue` | 按 Provider 分组展示节点状态 |
| `components/admin/ModelMetaTable.vue` | 增加 `provider_id` 列筛选 |
| `views/Admin.vue` | 增加 "Providers" 标签页 |
| `components/chat/ChatSidebar.vue` | 增加 Provider 选择器下拉框（聊天时选择） |
| `stores/`、`services/api.ts` | 聊天请求时传递 `provider` 参数 |

## 向后兼容策略

1. **配置**：无 `[provider.*]` 段时，自动从 `[api]` 创建名为 "default" 的单 Provider
2. **数据库**：`ensure_schema()` 自动创建新表/新列；`ModelMeta.provider_id = NULL` 视为全局可用
3. **服务层**：旧 `host_service.py` 函数签名不变，内部委托；无 Provider 时回退到原逻辑
4. **API**：所有现有接口的 request/response 格式不变

## 实施顺序（6 个 Phase）

| Phase | 内容 | 文件数 |
|-------|------|--------|
| Phase 1 数据层 | 新增实体、修改 User/ModelMeta、增加 Repository | ~4 |
| Phase 2 配置+运行时 | Settings 解析、ProviderRuntime、build_providers | ~3 |
| Phase 3 服务层 | provider_service 新建、host_service/model_service 改造 | ~7 |
| Phase 4 路由层 | public/admin routes 新增和修改 | ~2 |
| Phase 5 前端 | 新组件、修改现有组件、i18n | ~8 |
| Phase 6 收尾 | 审查、测试向后兼容、清理死代码 | - |

## 验证方法

1. **向后兼容测试**：不修改 conf.ini，启动服务，验证所有现有接口正常工作
2. **新 Provider 测试**：添加 `[provider.xxx]` 段，重启服务，验证 `/models` 返回新 Provider 的模型
3. **黑名单测试**：模拟 Provider 节点故障，验证黑名单和恢复机制
4. **用户隔离测试**：Admin 设置用户只能访问 Provider A，验证该用户无法使用 Provider B 的模型
5. **前端测试**：Admin 面板 CRUD Provider、Runtime 概览展示、用户 Provider 分配
