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

若需要从旧归档恢复，可使用 `sqlite3` 的 ATTACH 机制把 `backup/logs-YYYYMMDD.db` 挂到主库后写入：

```bash
# 1. 干跑：只看有多少条会被恢复（不会写入）
sqlite3 logs.db "ATTACH './backup/logs-YYYYMMDD.db' AS bak; \
  SELECT 'log 待恢复:', COUNT(*) FROM bak.log WHERE id NOT IN (SELECT id FROM main.log); \
  SELECT 'dialog 待恢复:', COUNT(*) FROM bak.dialog \
    WHERE (username,chattype,dialog_name) NOT IN (SELECT username,chattype,dialog_name FROM main.dialog); \
  DETACH bak;"

# 2. 实际恢复。INSERT OR IGNORE 命中 dialog 唯一索引时静默跳过，避免重复。
sqlite3 logs.db "ATTACH './backup/logs-YYYYMMDD.db' AS bak; \
  INSERT OR IGNORE INTO log SELECT * FROM bak.log; \
  INSERT OR IGNORE INTO dialog SELECT * FROM bak.dialog; \
  DETACH bak;"
```

> **不要用 `.dump` 路径**：`sqlite3 backup/logs-*.db ".dump" | sqlite3 logs.db` 会因主库已有同名表 / 唯一索引 `dialog_username_chattype_dialog_name` 而报 `Parse error near line N: index ... already exists`。ATTACH 方案绕开了 schema 重建，直接走 INSERT + 索引去重。

## 替换为新归档

如需新增归档任务，按 `runtime_logging.build_runtime_log_path` 提供的接口实现，**不要再恢复 archive_logs.py**。
