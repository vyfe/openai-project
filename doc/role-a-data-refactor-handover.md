# A阶段收尾交接：数据重构字段字典与Repository清单

## 1. 变更范围概述
- 已完成 `server/db`、`server/models`、`server/repositories` 三层结构初始化。
- 已在兼容层 `sqlitelog.py` 保持旧函数签名可用，并新增 V2 会话数据操作入口。
- 当前后端可在不修改旧调用方的前提下继续运行。

## 2. 新增数据表字段字典

### 2.1 `masterconversation`
- `id` INTEGER PK
- `owner` TEXT NOT NULL
- `title` TEXT NOT NULL
- `session_type` TEXT NOT NULL，默认 `single`，约束目标值：`single|multi_compare`
- `active_models_json` TEXT NOT NULL，JSON数组字符串
- `created_at` DATETIME NOT NULL
- `updated_at` DATETIME NOT NULL
- 索引：`(owner, updated_at)`

### 2.2 `childconversation`
- `id` INTEGER PK
- `master_id` INTEGER FK -> `masterconversation.id`
- `model_id` TEXT NOT NULL
- `status` TEXT NOT NULL，默认 `active`，约束目标值：`active|removed|failed`
- `backend_dialog_id` INTEGER NULL（旧Dialog映射ID）
- `created_round_index` INTEGER NOT NULL，默认 `0`
- `created_at` DATETIME NOT NULL
- `updated_at` DATETIME NOT NULL
- 唯一索引：`(master_id, model_id)`

### 2.3 `conversationround`
- `id` INTEGER PK
- `master_id` INTEGER FK -> `masterconversation.id`
- `round_index` INTEGER NOT NULL
- `user_prompt` TEXT NOT NULL
- `attachments_json` TEXT NULL（JSON数组字符串）
- `created_at` DATETIME NOT NULL
- 唯一索引：`(master_id, round_index)`

### 2.4 `roundcell`
- `id` INTEGER PK
- `round_id` INTEGER FK -> `conversationround.id`
- `child_id` INTEGER FK -> `childconversation.id`
- `assistant_output` TEXT NULL
- `cell_status` TEXT NOT NULL，默认 `idle`，约束目标值：`idle|streaming|success|failed|skipped`
- `error_json` TEXT NULL
- `latency_ms` INTEGER NULL
- `request_id` TEXT NULL
- `updated_at` DATETIME NOT NULL
- 唯一索引：`(round_id, child_id)`

## 3. Repository清单（供角色B服务层直接调用）

### 3.1 `MasterConversationRepo`
文件：`cyf/project/server/repositories/master_conversation_repo.py`
- `create(owner, title, session_type='single', active_models=None)`
- `get(master_id, owner=None)`
- `list_by_owner(owner, limit=20, offset=0)`
- `update_active_models(master_id, active_models)`
- `touch(master_id)`
- `to_dict(master)`

### 3.2 `ChildConversationRepo`
文件：`cyf/project/server/repositories/child_conversation_repo.py`
- `create(master_id, model_id, status='active', backend_dialog_id=None, created_round_index=0)`
- `list_by_master(master_id, include_removed=True)`
- `get_by_master_model(master_id, model_id)`
- `update_status(child_id, status)`
- `update_backend_dialog_id(child_id, backend_dialog_id)`

### 3.3 `RoundRepo`
文件：`cyf/project/server/repositories/round_repo.py`
- `create(master_id, round_index, user_prompt, attachments=None)`
- `list_by_master(master_id)`
- `get_latest_round_index(master_id)`

### 3.4 `RoundCellRepo`
文件：`cyf/project/server/repositories/round_cell_repo.py`
- `create(round_id, child_id, cell_status='idle', assistant_output=None, error_json=None, latency_ms=None, request_id=None)`
- `list_by_round(round_id)`
- `get(round_id, child_id)`
- `upsert(round_id, child_id, **kwargs)`

### 3.5 `LegacyDialogRepo`
文件：`cyf/project/server/repositories/legacy_dialog_repo.py`
- `set_dialog(user, model, chattype, dialog_name, context, dialog_id=None)`

## 4. 兼容层导出与新入口
文件：`cyf/project/server/sqlitelog.py`

### 4.1 旧能力保持
- 旧模型导出：`Log/Dialog/ModelMeta/SystemPrompt/TestLimit/User/Notification`
- 旧函数保持：`set_dialog/get_dialog_list/get_dialog_context/...`

### 4.2 新会话入口（V2数据层）
- `create_master_conversation(...)`
- `create_child_conversation(...)`
- `create_conversation_round(...)`
- `upsert_round_cell(...)`

## 5. 模块化边界约定
- Model 文件仅定义结构，不写业务流程。
- Repository 仅执行数据读写，不写编排逻辑。
- 业务策略（加模型补`skipped`、单元重试流程、并发写回）由角色B service层实现。

## 6. 当前已验证项
- `.venv` 环境下 `sqlitelog/server_admin/init_model_meta` 导入通过。
- `sqlitelog.init_db()` 可创建新旧全部表。
- Repository 冒烟：`master -> child -> round -> cell` 写入链路通过。

## 7. 给角色B的接入建议
- 优先直接调用 `repositories/*Repo`，避免在 route 中写 SQL。
- 在 service 层约束枚举合法性（`session_type/status/cell_status`）。
- `round/send` 使用 `RoundCellRepo.upsert` 处理流式增量与终态写回。
