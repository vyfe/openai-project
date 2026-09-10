-- Quant DB schema migration: prompt_template_extra_sections
-- Generated at: 2026-09-10 20:45:45
-- Mode: dry-run / soft / hard（脚本调用时选定）
-- 检测到的缺列:
--   quant_prompt_template.extra_sections

-- === 备份（仅 soft 模式会执行）===
-- CREATE TABLE quant_prompt_template_backup_20260910_204545_extra_sections AS SELECT * FROM quant_prompt_template;

-- === ALTER ===
ALTER TABLE quant_prompt_template ADD COLUMN extra_sections TEXT NOT NULL DEFAULT '[]';
