"""平台权限显式迁移；dry-run 只读，soft 使用 SQLite backup 保存一致性副本。"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sqlite3
import sys
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from service.permission_service import PLATFORM_MIGRATION_VERSION as PLATFORM_VERSION

LEGACY_ROLE_MAPPING = {"user": "chat", "admin": "admin"}
OWNERSHIP_COLUMNS = (("user", "deleted_at", "DATETIME"),
                     ("voice_reading", "owner_user_id", "INTEGER"),
                     ("music_track", "owner_user_id", "INTEGER"))
NEW_TABLES = (
    "CREATE TABLE IF NOT EXISTS user_role (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, role TEXT NOT NULL, created_at DATETIME NOT NULL)",
    "CREATE UNIQUE INDEX IF NOT EXISTS user_role_user_id_role ON user_role (user_id, role)",
    "CREATE INDEX IF NOT EXISTS user_role_user_id ON user_role (user_id)",
    "CREATE TABLE IF NOT EXISTS voice_asset_ownership (id INTEGER PRIMARY KEY, scope TEXT NOT NULL, voice_id TEXT NOT NULL, owner_user_id INTEGER NOT NULL, created_at DATETIME NOT NULL)",
    "CREATE UNIQUE INDEX IF NOT EXISTS voice_asset_ownership_scope_voice_id ON voice_asset_ownership (scope, voice_id)",
    "CREATE TABLE IF NOT EXISTS platform_schema_migration (version TEXT PRIMARY KEY, applied_at DATETIME NOT NULL, note TEXT NOT NULL DEFAULT '')",
)


def readonly_connection(db_path):
    return sqlite3.connect(Path(db_path).resolve().as_uri() + "?mode=ro", uri=True)


def backup_database(db_path, log=print):
    backup_path = f"{db_path}.bak.{datetime.now():%Y%m%d_%H%M%S_%f}"
    with readonly_connection(db_path) as source, sqlite3.connect(backup_path) as target:
        source.backup(target)
    log(f"[backup] {backup_path}")
    return backup_path


def _table_exists(cur, table):
    return cur.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone() is not None


def _columns(cur, table):
    return {row[1] for row in cur.execute(f'PRAGMA table_info("{table}")')}


def _collect(cur):
    if not _table_exists(cur, "user"):
        raise ValueError("缺少 user 表，请先初始化平台库")
    applied = _table_exists(cur, "platform_schema_migration") and bool(cur.execute(
        "SELECT 1 FROM platform_schema_migration WHERE version=?", (PLATFORM_VERSION,)).fetchone())
    stats = {"tables": {}, "roles": {}, "inactive": 0, "unknown_roles": [], "missing": [], "applied": applied}
    for role, count in cur.execute("SELECT COALESCE(role, ''), COUNT(*) FROM user GROUP BY role"):
        stats["roles"][role] = count
        if not applied and role not in LEGACY_ROLE_MAPPING:
            stats["unknown_roles"].append(role)
    stats["inactive"] = cur.execute("SELECT COUNT(*) FROM user WHERE is_active=0").fetchone()[0]
    for table in ("user", "dialog", "log", "voice_reading", "music_track", "voice_account_state"):
        if _table_exists(cur, table):
            stats["tables"][table] = cur.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
    for table, column, sql_type in OWNERSHIP_COLUMNS:
        if _table_exists(cur, table) and column not in _columns(cur, table):
            stats["missing"].append((table, column, sql_type))
    return stats


def collect_stats(db_path):
    with readonly_connection(db_path) as conn:
        return _collect(conn.cursor())


def migration_statements(stats):
    statements = list(NEW_TABLES)
    statements.extend(f'ALTER TABLE "{table}" ADD COLUMN "{column}" {sql_type}'
                      for table, column, sql_type in stats["missing"])
    for table in ("voice_reading", "music_track"):
        if table in stats["tables"]:
            statements.append(f'CREATE INDEX IF NOT EXISTS "{table}_owner_user_id" ON "{table}" (owner_user_id)')
    if not stats["applied"]:
        # 版本条件同样写入 SQL，手动重复应用落档 SQL 也不能恢复已撤销角色。
        version_guard = f"NOT EXISTS (SELECT 1 FROM platform_schema_migration WHERE version='{PLATFORM_VERSION}')"
        statements.append(
            "INSERT INTO user_role (user_id, role, created_at) "
            "SELECT u.id, CASE u.role WHEN 'admin' THEN 'admin' ELSE 'chat' END, CURRENT_TIMESTAMP FROM user u "
            f"WHERE u.role IN ('user','admin') AND {version_guard} "
            "AND NOT EXISTS (SELECT 1 FROM user_role r WHERE r.user_id=u.id)")
        statements.append(
            "INSERT OR IGNORE INTO platform_schema_migration (version,applied_at,note) "
            f"VALUES ('{PLATFORM_VERSION}',CURRENT_TIMESTAMP,'legacy roles migrated')")
    return statements


def render_sql(stats):
    header = [f"-- Platform permissions {PLATFORM_VERSION}",
              f"-- rows={stats['tables']}; roles={stats['roles']}; applied={stats['applied']}"]
    if stats["unknown_roles"]:
        raise ValueError(f"未知旧角色，迁移中止: {stats['unknown_roles']}")
    return "\n".join(header + ["BEGIN IMMEDIATE;"] + [s + ";" for s in migration_statements(stats)] + ["COMMIT;", ""])


def apply_migration(db_path, stats, mode, log=print):
    if stats["unknown_roles"]:
        raise ValueError(f"未知旧角色，迁移中止: {stats['unknown_roles']}")
    if mode == "soft":
        backup_database(db_path, log)
    with sqlite3.connect(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        current = _collect(conn.cursor())
        if current["unknown_roles"]:
            raise ValueError(f"未知旧角色，迁移中止: {current['unknown_roles']}")
        for statement in migration_statements(current):
            conn.execute(statement)
    log("[done] 平台权限迁移完成；已迁移版本不会再次回填角色。")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--mode", choices=["dry-run", "soft", "hard"], default="dry-run")
    parser.add_argument("--output")
    args = parser.parse_args(argv)
    if not os.path.isfile(args.db):
        parser.error("数据库不存在")
    stats = collect_stats(args.db)
    sql = render_sql(stats)
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(sql, encoding="utf-8")
        print(f"SQL: {args.output}")
    else:
        print(sql)
    if args.mode != "dry-run":
        apply_migration(args.db, stats, args.mode)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
