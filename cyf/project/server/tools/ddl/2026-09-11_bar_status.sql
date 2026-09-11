-- Quant DB schema migration: bar_status
-- Generated at: 2026-09-11
-- Mode: dry-run / soft / hard（脚本调用时选定）
-- 检测到的缺列:
--   quant_daily_bar.status
--   quant_minute_bar.status
-- （weekly 不存在独立表，是从 daily 聚合而来；删除 daily 时自动级联）
--
-- 字段语义：K 线 / 分时数据的"软删除"状态，default='active'（未删除）。
-- 与 quant_instrument.status 对齐：删除股票池时，两表对应 symbol 全部级联更新为 'deleted'。
-- 查询路径（query_service.fetch_*_bars）默认只返回 status='active' 的数据。
--
-- 线上必须 soft 模式（AGENTS.md §3.5.1）：
--   .venv/bin/python tools/quant_db_migrate.py --mode soft

-- === 备份（仅 soft 模式会执行）===
-- CREATE TABLE quant_daily_bar_backup_20260911_HHMMSS_status AS SELECT * FROM quant_daily_bar;
-- CREATE TABLE quant_minute_bar_backup_20260911_HHMMSS_status AS SELECT * FROM quant_minute_bar;

-- === ALTER ===
ALTER TABLE quant_daily_bar ADD COLUMN status VARCHAR NOT NULL DEFAULT 'active';
CREATE INDEX quant_daily_bar_status_idx ON quant_daily_bar(status);

ALTER TABLE quant_minute_bar ADD COLUMN status VARCHAR NOT NULL DEFAULT 'active';
CREATE INDEX quant_minute_bar_status_idx ON quant_minute_bar(status);