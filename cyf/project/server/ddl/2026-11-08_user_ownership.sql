BEGIN IMMEDIATE;
-- Quant DB schema migration: user_ownership
-- Generated at: 2026-11-08 15:07:02
-- Mode: dry-run / soft / hard（脚本调用时选定）
-- 检测到的缺列:
--   quant_strategy.owner_user_id
--   quant_operation_record.owner_user_id
--   quant_position_journal.owner_user_id

-- === 备份（仅 soft 模式会执行）===
-- CREATE TABLE quant_strategy_backup_20261108_150702_owner_user_id AS SELECT * FROM quant_strategy;
-- CREATE TABLE quant_operation_record_backup_20261108_150702_owner_user_id AS SELECT * FROM quant_operation_record;
-- CREATE TABLE quant_position_journal_backup_20261108_150702_owner_user_id AS SELECT * FROM quant_position_journal;

-- === ALTER ===
ALTER TABLE quant_strategy ADD COLUMN owner_user_id INTEGER NULL;
ALTER TABLE quant_operation_record ADD COLUMN owner_user_id INTEGER NULL;
ALTER TABLE quant_position_journal ADD COLUMN owner_user_id INTEGER NULL;
-- user_ownership: column additions and table rebuild form one transaction
CREATE TABLE quant_strategy_new ("id" INTEGER NOT NULL PRIMARY KEY, "name" VARCHAR(255) NOT NULL, "owner_user_id" INTEGER NULL, "market" VARCHAR(255) NOT NULL DEFAULT 'A_SHARE', "status" VARCHAR(255) NOT NULL DEFAULT 'active', "description" TEXT NOT NULL DEFAULT '', "symbols_json" TEXT NOT NULL DEFAULT '[]', "rule_config_json" TEXT NOT NULL DEFAULT '{}', "created_at" DATETIME NOT NULL DEFAULT '2026-11-08T15:07:02', "updated_at" DATETIME NOT NULL DEFAULT '2026-11-08T15:07:02');
INSERT INTO quant_strategy_new (id, name, owner_user_id, market, status, description, symbols_json, rule_config_json, created_at, updated_at) SELECT id, name, owner_user_id, market, status, description, symbols_json, rule_config_json, created_at, updated_at FROM quant_strategy;
DROP TABLE quant_strategy;
ALTER TABLE quant_strategy_new RENAME TO quant_strategy;
CREATE UNIQUE INDEX quant_strategy_owner_name ON quant_strategy (owner_user_id,name) WHERE owner_user_id IS NOT NULL;
CREATE UNIQUE INDEX quant_strategy_name_null_owner ON quant_strategy (name) WHERE owner_user_id IS NULL;
CREATE INDEX quant_strategy_owner_user_id ON quant_strategy (owner_user_id);
CREATE INDEX quant_strategy_market ON quant_strategy (market);
CREATE INDEX quant_strategy_status ON quant_strategy (status);
CREATE INDEX IF NOT EXISTS quant_operation_record_owner_user_id ON quant_operation_record (owner_user_id);
CREATE INDEX IF NOT EXISTS quant_position_journal_owner_user_id ON quant_position_journal (owner_user_id);
COMMIT;
