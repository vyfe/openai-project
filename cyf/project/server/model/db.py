from peewee import BooleanField, TextField
from playhouse.migrate import SqliteMigrator, migrate
from playhouse.sqlite_ext import SqliteExtDatabase

from conf.settings import settings


db = SqliteExtDatabase(settings.conf.get("log", "sqlite3_file"))


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

        if missing_records:
            print(f"[db] 已补齐字段: {', '.join(missing_records)}")
    except Exception as exc:
        print(f"[db] 自动更新表结构失败: {exc}")


def init_db(models, user_model, model_meta_model):
    db.connect(reuse_if_open=True)
    db.create_tables(models, safe=True)
    ensure_schema(user_model, model_meta_model)
