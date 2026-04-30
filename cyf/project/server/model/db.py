from peewee import TextField
from playhouse.migrate import SqliteMigrator, migrate
from playhouse.sqlite_ext import SqliteExtDatabase

from conf.settings import settings


db = SqliteExtDatabase(settings.conf.get("log", "sqlite3_file"))


def ensure_schema(user_model):
    try:
        table_name = user_model._meta.table_name
        columns = {col.name for col in db.get_columns(table_name)}
        missing = []
        if "browser_conf" not in columns:
            missing.append(("browser_conf", TextField(null=True)))
        if "token" not in columns:
            missing.append(("token", TextField(null=True)))

        if missing:
            migrator = SqliteMigrator(db)
            for column_name, field in missing:
                migrate(migrator.add_column(table_name, column_name, field))
            print(f"[db] 已补齐字段: {', '.join(name for name, _ in missing)}")
    except Exception as exc:
        print(f"[db] 自动更新表结构失败: {exc}")


def init_db(models, user_model):
    db.connect(reuse_if_open=True)
    db.create_tables(models, safe=True)
    ensure_schema(user_model)
