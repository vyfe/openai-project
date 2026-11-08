-- Platform permissions 2026-11-08-user-ownership
-- rows={'user': 8, 'dialog': 52, 'log': 140, 'voice_reading': 2, 'music_track': 0, 'voice_account_state': 2}; roles={'admin': 2, 'user': 6}; applied=False
BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS user_role (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, role TEXT NOT NULL, created_at DATETIME NOT NULL);
CREATE UNIQUE INDEX IF NOT EXISTS user_role_user_id_role ON user_role (user_id, role);
CREATE INDEX IF NOT EXISTS user_role_user_id ON user_role (user_id);
CREATE TABLE IF NOT EXISTS voice_asset_ownership (id INTEGER PRIMARY KEY, scope TEXT NOT NULL, voice_id TEXT NOT NULL, owner_user_id INTEGER NOT NULL, created_at DATETIME NOT NULL);
CREATE UNIQUE INDEX IF NOT EXISTS voice_asset_ownership_scope_voice_id ON voice_asset_ownership (scope, voice_id);
CREATE TABLE IF NOT EXISTS platform_schema_migration (version TEXT PRIMARY KEY, applied_at DATETIME NOT NULL, note TEXT NOT NULL DEFAULT '');
ALTER TABLE "user" ADD COLUMN "deleted_at" DATETIME;
ALTER TABLE "voice_reading" ADD COLUMN "owner_user_id" INTEGER;
ALTER TABLE "music_track" ADD COLUMN "owner_user_id" INTEGER;
CREATE INDEX IF NOT EXISTS "voice_reading_owner_user_id" ON "voice_reading" (owner_user_id);
CREATE INDEX IF NOT EXISTS "music_track_owner_user_id" ON "music_track" (owner_user_id);
INSERT INTO user_role (user_id, role, created_at) SELECT u.id, CASE u.role WHEN 'admin' THEN 'admin' ELSE 'chat' END, CURRENT_TIMESTAMP FROM user u WHERE u.role IN ('user','admin') AND NOT EXISTS (SELECT 1 FROM platform_schema_migration WHERE version='2026-11-08-user-ownership') AND NOT EXISTS (SELECT 1 FROM user_role r WHERE r.user_id=u.id);
INSERT OR IGNORE INTO platform_schema_migration (version,applied_at,note) VALUES ('2026-11-08-user-ownership',CURRENT_TIMESTAMP,'legacy roles migrated');
COMMIT;
