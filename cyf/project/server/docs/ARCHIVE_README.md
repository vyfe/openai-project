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

若需要从旧归档恢复，可使用 `sqlite3` 直接读取 `backup/logs-YYYYMMDD.db`：

```bash
sqlite3 backup/logs-20240201.db ".dump" > backup_data.sql
sqlite3 logs.db < backup_data.sql
```

## 替换为新归档

如需新增归档任务，按 `runtime_logging.build_runtime_log_path` 提供的接口实现，**不要再恢复 archive_logs.py**。
