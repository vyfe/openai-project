# 角色A开发手册：数据架构升级与模型模块化（Python）

## 1. 角色目标
- 设计并落地主会话/子会话/回合单元的数据结构。
- 将当前 `sqlitelog.py` 内部数据模型拆分为单文件模块。
- 提供可回滚的 SQLite 迁移方案，并保证旧 `Dialog` 兼容可读。

## 2. 现状问题
- `cyf/project/server/sqlitelog.py` 同时承担：
  - Model 定义
  - 查询函数
  - 迁移逻辑
  - 业务型 helper
- `Dialog` 为单模型单会话，无法表达主子关系和回合矩阵。

## 3. 目标目录结构（建议）
```text
cyf/project/server/
  db/
    database.py                # db初始化与连接
    migrator.py                # 统一迁移入口
  models/
    __init__.py
    log.py
    dialog_legacy.py
    master_conversation.py
    child_conversation.py
    round.py
    round_cell.py
    user.py
    model_meta.py
    system_prompt.py
    notification.py
  repositories/
    master_conversation_repo.py
    child_conversation_repo.py
    round_repo.py
    round_cell_repo.py
    legacy_dialog_repo.py
```

## 4. 新数据结构定义

### 4.1 `master_conversation`
- `id` INTEGER PK
- `owner` TEXT NOT NULL
- `title` TEXT NOT NULL
- `session_type` TEXT NOT NULL (`single|multi_compare`)
- `active_models_json` TEXT NOT NULL（JSON 数组）
- `created_at` DATETIME NOT NULL
- `updated_at` DATETIME NOT NULL
- 索引：`(owner, updated_at DESC)`

### 4.2 `child_conversation`
- `id` INTEGER PK
- `master_id` INTEGER NOT NULL FK
- `model_id` TEXT NOT NULL
- `status` TEXT NOT NULL (`active|removed|failed`)
- `backend_dialog_id` INTEGER NULL（映射旧对话ID）
- `created_round_index` INTEGER NOT NULL
- `created_at` DATETIME NOT NULL
- `updated_at` DATETIME NOT NULL
- 唯一索引：`(master_id, model_id)`

### 4.3 `conversation_round`
- `id` INTEGER PK
- `master_id` INTEGER NOT NULL FK
- `round_index` INTEGER NOT NULL
- `user_prompt` TEXT NOT NULL
- `attachments_json` TEXT NULL
- `created_at` DATETIME NOT NULL
- 唯一索引：`(master_id, round_index)`

### 4.4 `round_cell`
- `id` INTEGER PK
- `round_id` INTEGER NOT NULL FK
- `child_id` INTEGER NOT NULL FK
- `assistant_output` TEXT NULL
- `cell_status` TEXT NOT NULL (`idle|streaming|success|failed|skipped`)
- `error_json` TEXT NULL
- `latency_ms` INTEGER NULL
- `request_id` TEXT NULL
- `updated_at` DATETIME NOT NULL
- 唯一索引：`(round_id, child_id)`

## 5. 迁移策略
- 保留旧表 `Dialog`，不做破坏性修改。
- 新增四张表，不触碰旧接口使用字段。
- `migrator.py` 中按步骤执行：
  - `ensure_master_conversation_table()`
  - `ensure_child_conversation_table()`
  - `ensure_conversation_round_table()`
  - `ensure_round_cell_table()`
- 迁移支持幂等，重复执行不报错。

## 6. 数据模块化规范
- 每个 Model 一个文件，禁止继续在 `sqlitelog.py` 定义新模型。
- repository 只做数据访问，不写业务流程。
- 业务语义（如 add_model 时补 `skipped`）放 service 层（由角色B负责）。

## 7. 交付物
- 新模型文件与 repository 文件。
- 迁移脚本与启动自检日志。
- 数据字典文档（字段、枚举、索引、约束）。
- 与角色B对齐的 query 接口（Python函数签名）。

## 8. 验收标准
- 本地初始化后四张新表存在且索引正确。
- 旧 `Dialog` 读写路径不受影响。
- repository 单测覆盖：增删模型、回合创建、单元写入、软删除与查询。
