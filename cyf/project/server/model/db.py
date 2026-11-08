from peewee import BooleanField, FloatField, TextField
from playhouse.migrate import SqliteMigrator, migrate
from playhouse.sqlite_ext import SqliteExtDatabase

from conf.settings import settings


db = SqliteExtDatabase(settings.conf.get("log", "sqlite3_file"))


def _add_missing_columns(migrator, table_name, columns):
    """为已存在的表补齐缺失列，返回补齐的列名。"""
    existing = {col.name for col in db.get_columns(table_name)}
    added = []
    for name, field in columns:
        if name not in existing:
            migrate(migrator.add_column(table_name, name, field))
            added.append(f"{table_name}.{name}")
    return added


def ensure_schema(user_model, model_meta_model):
    try:
        migrator = SqliteMigrator(db)
        missing_records = []

        user_table_name = user_model._meta.table_name
        user_columns = {col.name for col in db.get_columns(user_table_name)}
        if "browser_conf" not in user_columns:
            migrate(migrator.add_column(user_table_name, "browser_conf", TextField(null=True)))
            missing_records.append(f"{user_table_name}.browser_conf")
        if "token" not in user_columns:
            migrate(migrator.add_column(user_table_name, "token", TextField(null=True)))
            missing_records.append(f"{user_table_name}.token")

        model_meta_table_name = model_meta_model._meta.table_name
        model_meta_columns = {col.name for col in db.get_columns(model_meta_table_name)}
        if "allow_net" not in model_meta_columns:
            migrate(migrator.add_column(model_meta_table_name, "allow_net", BooleanField(default=True)))
            missing_records.append(f"{model_meta_table_name}.allow_net")

        # 音乐表在迭代中新增过列，存量库需要补齐；这里在函数内导入以避开 entities 与 db 的循环依赖。
        from model.entities import MusicTrack

        music_table_name = MusicTrack._meta.table_name
        missing_records += _add_missing_columns(migrator, music_table_name, [
            ("cover_feature_id", TextField(null=True)),
            ("reference_duration", FloatField(null=True)),
        ])


        if missing_records:
            print(f"[db] 已补齐字段: {', '.join(missing_records)}")
    except Exception as exc:
        print(f"[db] 自动更新表结构失败: {exc}")


def ensure_permission_migration():
    """启动期检查平台权限迁移版本；缺失时执行一次性回填，失败则阻止业务启动。"""
    from service.platform_migration import PermissionMigrationError, ensure_applied

    try:
        result = ensure_applied()
    except PermissionMigrationError as exc:
        raise PermissionMigrationError(
            f"平台权限迁移未完成，业务启动已停止：{exc}\n"
            "请执行：.venv/bin/python tools/platform_permissions_migrate.py --db <平台库路径> --mode soft --output ddl/platform_permissions.sql"
        ) from exc
    if result.get("applied"):
        print(f"[db] 平台权限迁移已应用: version={result['version']} backfilled={result['backfilled']}")
    return result


def init_db(models, user_model, model_meta_model):
    db.connect(reuse_if_open=True)
    fresh = not db.get_tables()
    if not fresh:
        # 先检查，再 create_tables：旧表缺列时 Peewee 建索引也会失败。
        ensure_permission_migration()
        expected = {"user": {"deleted_at"}, "voice_reading": {"owner_user_id"}, "music_track": {"owner_user_id"}}
        for table, columns in expected.items():
            if table in db.get_tables() and not columns <= {col.name for col in db.get_columns(table)}:
                raise RuntimeError(f"{table} 权限字段缺失，请先执行平台权限迁移")
    db.create_tables(models, safe=True)
    ensure_schema(user_model, model_meta_model)
    if fresh:
        from service.platform_migration import apply_backfill
        apply_backfill()
