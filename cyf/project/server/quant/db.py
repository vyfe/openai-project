import os

from playhouse.sqlite_ext import SqliteExtDatabase
from playhouse.migrate import SqliteMigrator, migrate
from peewee import FloatField, IntegerField, TextField

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
    fresh = not quant_db.get_tables()
    if not fresh:
        check_ownership_schema()
    quant_db.create_tables(models, safe=True)
    if fresh:
        quant_db.execute_sql("CREATE UNIQUE INDEX IF NOT EXISTS quant_strategy_name_null_owner ON quant_strategy (name) WHERE owner_user_id IS NULL")
    ensure_quant_schema()


def check_ownership_schema():
    """存量库只检查；列与约束必须由 quant_db_migrate 显式迁移。"""
    for table in ("quant_strategy", "quant_operation_record", "quant_position_journal"):
        if "owner_user_id" not in {col.name for col in quant_db.get_columns(table)}:
            raise RuntimeError(f"{table} 缺少归属迁移，请执行 tools/quant_db_migrate.py --change-name user_ownership --mode soft")
    indexes = quant_db.get_indexes("quant_strategy")
    if (any(idx.unique and idx.columns == ["name"] and "WHERE" not in (idx.sql or "").upper() for idx in indexes)
            or not any(idx.unique and idx.columns == ["owner_user_id", "name"] for idx in indexes)):
        raise RuntimeError("策略名约束未迁移，请执行 tools/quant_db_migrate.py --change-name user_ownership --mode soft")


def ensure_quant_schema():
    try:
        migrator = SqliteMigrator(quant_db)
        missing_records = []

        channel_columns = {col.name for col in quant_db.get_columns("quant_im_channel")}
        if "config_json" not in channel_columns:
            migrate(migrator.add_column("quant_im_channel", "config_json", TextField(default="{}")))
            missing_records.append("quant_im_channel.config_json")

        bar_columns = {col.name for col in quant_db.get_columns("quant_daily_bar")}
        if "change" not in bar_columns:
            migrate(migrator.add_column("quant_daily_bar", "change", FloatField(null=True)))
            missing_records.append("quant_daily_bar.change")
        if "amplitude_pct" not in bar_columns:
            migrate(migrator.add_column("quant_daily_bar", "amplitude_pct", FloatField(null=True)))
            missing_records.append("quant_daily_bar.amplitude_pct")

        schedule_run_columns = {col.name for col in quant_db.get_columns("quant_schedule_run")}
        if "log_file" not in schedule_run_columns:
            migrate(migrator.add_column("quant_schedule_run", "log_file", TextField(default="")))
            missing_records.append("quant_schedule_run.log_file")

        client_task_columns = {col.name for col in quant_db.get_columns("quant_client_task")}
        if "schedule_run_id" not in client_task_columns:
            migrate(migrator.add_column("quant_client_task", "schedule_run_id", IntegerField(null=True)))
            quant_db.execute_sql("CREATE INDEX IF NOT EXISTS quant_client_task_schedule_run_id ON quant_client_task (schedule_run_id)")
            missing_records.append("quant_client_task.schedule_run_id")

        existing_tables = set(quant_db.get_tables())
        new_tables = {"quant_feishu_user_binding", "quant_daily_indicator", "quant_client_task", "quant_minute_bar"} - existing_tables
        if new_tables:
            from quant.entities import QuantClientTask, QuantDailyIndicator, QuantFeishuUserBinding, QuantMinuteBar
            quant_db.create_tables([QuantFeishuUserBinding, QuantDailyIndicator, QuantClientTask, QuantMinuteBar], safe=True)
            missing_records.append(f"new_tables: {', '.join(new_tables)}")

        if missing_records:
            print(f"[quant-db] 已补齐字段: {', '.join(missing_records)}")
    except Exception as exc:
        print(f"[quant-db] 自动更新表结构失败: {exc}")
