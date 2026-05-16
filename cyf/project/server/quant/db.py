import os

from playhouse.sqlite_ext import SqliteExtDatabase
from playhouse.migrate import SqliteMigrator, migrate
from peewee import TextField

from conf.settings import settings


def _ensure_parent_dir(path: str):
    directory = os.path.dirname(os.path.abspath(path))
    if directory:
        os.makedirs(directory, exist_ok=True)


_ensure_parent_dir(settings.quant_sqlite3_file)

quant_db = SqliteExtDatabase(
    settings.quant_sqlite3_file,
    pragmas={
        "journal_mode": "wal",
        "foreign_keys": 1,
        "busy_timeout": 5000,
        "cache_size": -64 * 1024,
    },
)


def init_quant_db(models):
    quant_db.connect(reuse_if_open=True)
    quant_db.create_tables(models, safe=True)
    ensure_quant_schema()


def ensure_quant_schema():
    try:
        migrator = SqliteMigrator(quant_db)
        missing_records = []
        channel_columns = {col.name for col in quant_db.get_columns("quant_im_channel")}
        if "config_json" not in channel_columns:
            migrate(migrator.add_column("quant_im_channel", "config_json", TextField(default="{}")))
            missing_records.append("quant_im_channel.config_json")
        if missing_records:
            print(f"[quant-db] 已补齐字段: {', '.join(missing_records)}")
    except Exception as exc:
        print(f"[quant-db] 自动更新表结构失败: {exc}")
