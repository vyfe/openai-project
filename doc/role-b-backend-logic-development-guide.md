# 角色B开发手册：后端逻辑开发与接口模块化（Python/Flask）

## 1. 角色目标
- 在保持旧接口可用的前提下，交付多模型并行会话 V2 接口。
- 将 `server.py` 中会话相关逻辑按功能拆分，建立 service + route 分层。
- 支持并发 fan-out、流式回写、单元级重试、动态增删模型。

## 2. 模块化目标结构（建议）
```text
cyf/project/server/
  app.py                        # Flask app factory
  routes/
    __init__.py
    legacy_chat_routes.py       # 旧 split/split_stream/split_his*
    conversation_v2_routes.py   # 新主子会话API
  services/
    conversation_service.py     # 主流程编排
    round_execution_service.py  # round fan-out 执行
    retry_service.py            # cell重试
    stream_runtime_service.py   # request_id/abort管理
    legacy_bridge_service.py    # 旧Dialog兼容桥接
  dto/
    conversation_dto.py         # 入参/出参结构校验
  repositories/
    ...（由角色A提供）
```

## 3. 路由拆分规则
- `legacy_chat_routes.py`：保持当前能力，不做行为变化。
- `conversation_v2_routes.py`：仅放 V2 的 7 个接口。
- 路由层只做：认证、参数校验、service 调用、统一响应包装。
- 业务策略不写在 route，统一放 service。

## 4. V2 接口行为定义

### 4.1 `POST /conversation/master/create`
- 输入：`title`, `session_type`, `active_models[]`
- 输出：`master_id`, `children[]`
- 行为：创建主会话 + 为每个模型创建 child。

### 4.2 `POST /conversation/master/list`
- 输入：分页参数
- 输出：主会话摘要列表（不返回子会话）

### 4.3 `POST /conversation/master/detail`
- 输入：`master_id`
- 输出：`master + children + rounds + cells`

### 4.4 `POST /conversation/master/add_model`
- 输入：`master_id`, `model_id`
- 行为：新增 child，并为历史 round 补 `skipped` cell。

### 4.5 `POST /conversation/master/remove_model`
- 输入：`master_id`, `model_id`
- 行为：child 置 `removed`，保留历史 cell。

### 4.6 `POST /conversation/round/send`
- 输入：`master_id`, `user_prompt`, `attachments`
- 行为：
  - 创建新 round。
  - 对 active child 并发执行模型请求（复用现有调用能力）。
  - 写入/更新各 child 的 round_cell。
  - 支持 streaming 模式下增量写入。

### 4.7 `POST /conversation/cell/retry`
- 输入：`round_id`, `child_id`
- 行为：仅重试该单元，不触发其他单元。

## 5. 并行执行与容错
- 并发执行建议：`ThreadPoolExecutor` 或 async worker（按当前栈选择一种）。
- 每个 cell 维护独立状态：`idle -> streaming -> success|failed`。
- 错误隔离：单 child 失败只更新对应 cell，不影响 round 其余 child。
- 停止流：沿用 `request_id` 机制，但作用域细化到 `round_id + child_id`。

## 6. 与旧系统兼容
- 旧接口 `/split`、`/split_stream`、`/split_his*` 保持不变。
- `legacy_bridge_service`：
  - 可将旧 `Dialog` 映射为 `single` 主会话视图（读时桥接）。
  - 首次写 V2 时不强制迁移旧数据。

## 7. 交付物
- 新路由文件、新 service 文件、新 dto 文件。
- 接口文档（请求/响应 JSON 示例 + 错误码）。
- 集成测试：create/list/detail/add/remove/send/retry 全链路。

## 8. 验收标准
- 7个V2接口可稳定运行。
- 3~5 模型并发时互不污染，失败可单元级重试。
- 删除模型为软删除，历史数据可追溯。
- 旧接口能力不回归。
