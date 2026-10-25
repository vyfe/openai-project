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


def init_db(models, user_model, model_meta_model):
    db.connect(reuse_if_open=True)
    db.create_tables(models, safe=True)
    ensure_schema(user_model, model_meta_model)
