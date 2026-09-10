# 数据归档系统（已废弃）

> ⚠️ **历史归档说明**。`archive_logs.py` / `restore_logs.py` 已被删除（v1 重构 C5 清理），相关 cron 配置不再维护。

## 背景

早期版本依赖 `archive_logs.py` 把 `logs.db` 中过期 dialog / log 复制到 `backup/` 子库。
此机制已停用——`logs.db` 现在由 `runtime_logging.build_runtime_log_path()` 滚动归档（`runtime_log.{plain,archive}_retention_days` 配置）。

## 备份现状

- 平台日志：`runtime_log.root_dir` 下按日滚动 + 30 天压缩保留
- 量化日志：`runtime_log.root_dir/quant/...`，与平台独立
- SQLite 备份：仅 `cyf/project/server/backup/` 中历史归档残留文件，不再产生新归档

## 数据恢复

若需要从旧归档恢复，可使用 `sqlite3` 的 ATTACH 机制把 `backup/logs-YYYYMMDD.db` 挂到主库后写入。

### 1. 干跑预检

**必须同时查 PK 冲突和唯一索引冲突**——两个维度都要为 0 才是真正"零恢复"；只有一维度为 0 但另一维度不为 0 时，实际可恢复数取两者交集（受 INSERT OR IGNORE 行为影响）。

```bash
sqlite3 logs.db "ATTACH './backup/logs-20260830.db' AS bak; \
  SELECT 'log 待恢复(PK):', COUNT(*) FROM bak.log WHERE id NOT IN (SELECT id FROM main.log); \
  SELECT 'dialog 待恢复(PK):', COUNT(*) FROM bak.dialog WHERE id NOT IN (SELECT id FROM main.dialog); \
  SELECT 'dialog 待恢复(唯一索引):', COUNT(*) FROM bak.dialog \
    WHERE (username,chattype,dialog_name) NOT IN (SELECT username,chattype,dialog_name FROM main.dialog); \
  DETACH bak;"
```

> **为什么 log 表用 `id NOT IN`、dialog 表还要额外看唯一索引？**
>
> - `log.id` 没有业务唯一键（log 是纯追加流水），跨库合并只能靠 PK 去重，所以 PK 视角就是 log 的全集。
> - `dialog.id` 是 PK，但业务上同一对话（同一 `username+chattype+dialog_name`）在不同时刻会有多条不同 `start_date` 的快照，PK 不同但业务上重复——所以还要看唯一索引视角。

### 2. 实际恢复

**INSERT 时显式跳过 `id` 列**，让主库自增分配。直接 `INSERT OR IGNORE INTO dialog SELECT * FROM bak.dialog` 会因为 backup 库和主库的 id 自增序列独立、PK 大量撞光而被静默跳过——`log 待恢复(PK): 0` 和 `dialog 待恢复(PK): 0` 是这种悲剧的典型表现。

```bash
sqlite3 logs.db "ATTACH './backup/logs-20260722.db' AS bak; \
  INSERT OR IGNORE INTO log (username, usage, modelname, request_text) \
  SELECT username, usage, modelname, request_text FROM bak.log; \
  INSERT OR IGNORE INTO dialog (username, chattype, modelname, dialog_name, start_date, context) \
  SELECT username, chattype, modelname, dialog_name, start_date, context FROM bak.dialog; \
  DETACH bak;"
```

> **log 表的列名要按实际 schema 调整**。上面是按 `model/entities.py` 中 `Log` 字段（`username / usage / modelname / request_text`）写的，恢复前先确认当前 schema 没有增减字段。

跳过 id 列后：
- 主库自增分配新 id，PK 永远不会撞
- 唯一索引 `(username, chattype, dialog_name)` 仍是去重安全网（同名对话已被主库覆盖的情况会被 OR IGNORE 跳过，保留主库当前版本）
- INSERT OR IGNORE 命中任一约束都静默跳过、不报错——**执行成功不等于全部插入**，务必在恢复后用具体业务查询（如某 username 在某日期范围）核对实际入库数

### 3. 恢复后核对

恢复后必须按业务维度验证，而不是看 INSERT 没有报错就完事。例如核对 xyj 在某个日期窗口的对话：

```bash
sqlite3 logs.db "SELECT dialog_name, start_date FROM dialog \
  WHERE username='xyj' AND start_date BETWEEN '2026-08-01' AND '2026-08-31' ORDER BY start_date;"
```

对照 backup 库的同名查询：

```bash
sqlite3 backup/logs-20260830.db "SELECT dialog_name, start_date FROM dialog \
  WHERE username='xyj' AND start_date BETWEEN '2026-08-01' AND '2026-08-31' ORDER BY start_date;"
```

两边差异 = 被 `(username, chattype, dialog_name)` 唯一索引挡住的行（通常是被主库同名对话覆盖的历史快照，无需恢复）。

> **不要用 `.dump` 路径**：`sqlite3 backup/logs-*.db ".dump" | sqlite3 logs.db` 会因主库已有同名表 / 唯一索引 `dialog_username_chattype_dialog_name` 而报 `Parse error near line N: index ... already exists`。ATTACH 方案绕开了 schema 重建，直接走 INSERT + 索引去重。

## 替换为新归档

如需新增归档任务，按 `runtime_logging.build_runtime_log_path` 提供的接口实现，**不要再恢复 archive_logs.py**。
