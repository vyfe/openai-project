import os

from playhouse.sqlite_ext import SqliteExtDatabase

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

