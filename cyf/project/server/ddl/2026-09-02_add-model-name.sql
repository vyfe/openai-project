-- Quant DB schema migration: add-model-name
-- Generated at: 2026-09-02 17:51:36
-- 适用版本: openai-project 阶段 2（AI 改写报告）
-- 内容: QuantPromptTemplate.model_name (VARCHAR(255) NOT NULL DEFAULT '')
--
-- 本文件由 tools/quant_db_migrate.py 生成，留作审计与回滚参考。
-- 重新生成方式：cd cyf/project/server && .venv/bin/python tools/quant_db_migrate.py --mode dry-run --output <本文件路径> --change-name add-model-name
--
-- 应用方式（生产环境推荐 soft）：
--   .venv/bin/python tools/quant_db_migrate.py --mode soft --change-name add-model-name
--
-- 检测到的缺列:
--   quant_prompt_template.model_name

-- === 备份（仅 soft 模式会执行）===
-- CREATE TABLE quant_prompt_template_backup_20260902_175113_model_name AS SELECT * FROM quant_prompt_template;

-- === ALTER ===
ALTER TABLE quant_prompt_template ADD COLUMN model_name VARCHAR(255) NOT NULL DEFAULT '';