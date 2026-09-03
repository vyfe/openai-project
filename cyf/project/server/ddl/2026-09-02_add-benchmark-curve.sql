-- Quant DB schema migration: add-benchmark-curve
-- Generated at: 2026-09-02 19:56:53
-- Mode: dry-run / soft / hard（脚本调用时选定）
-- 检测到的缺列:
--   quant_backtest_run.benchmark_curve_json

-- === 备份（仅 soft 模式会执行）===
-- CREATE TABLE quant_backtest_run_backup_20260902_195653_benchmark_curve_json AS SELECT * FROM quant_backtest_run;

-- === ALTER ===
ALTER TABLE quant_backtest_run ADD COLUMN benchmark_curve_json TEXT NOT NULL DEFAULT '[]';
