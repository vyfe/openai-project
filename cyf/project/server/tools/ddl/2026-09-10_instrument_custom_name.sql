-- Quant DB schema migration: instrument_custom_name
-- Generated at: 2026-09-10
-- Mode: dry-run / soft / hard（脚本调用时选定）
-- 检测到的缺列:
--   quant_instrument.custom_name
--
-- 字段语义：用户自定义显示名（数据中心维护）。非空时优先于 name 用于
-- - 报告渲染（service/quant/report_generation_service._bulk_lookup_instrument_names）
-- - dashboard 渲染（service/quant/dashboard_service._bulk_lookup_names）
-- - 前端策略池 / 信号列表展示
-- 不参与东财 / 腾讯等数据源；不影响 quant_instrument.name 权威值。
--
-- 线上必须 soft 模式（AGENTS.md §3.5.1）：
--   .venv/bin/python tools/quant_db_migrate.py --mode soft

-- === 备份（仅 soft 模式会执行）===
-- CREATE TABLE quant_instrument_backup_20260910_HHMMSS_custom_name AS SELECT * FROM quant_instrument;

-- === ALTER ===
ALTER TABLE quant_instrument ADD COLUMN custom_name VARCHAR;