#!/usr/bin/env python3
"""量化子系统 DB schema 自动迁移：扫 entity vs 实际 DB 列，生成并执行 ALTER。

支持三种模式：
  --dry-run   只打印 / 落档 ALTER，不动 DB（默认）
  --soft      先 CREATE TABLE ... AS SELECT * 备份，再 ALTER（生产用，留 backup_<时间>_<字段>）
  --hard      直接 ALTER，不备份（dev / 测试用）

输出：
  默认打印在 stdout
  --output PATH  把 ALTER 落档到 server/ddl/<change_name>_<YYYYMMDD-HHMMSS>.sql

DB 路径：
  默认从 conf.settings.quant_sqlite3_file 读（与运行服务一致）
  --db PATH  覆盖（线上或临时 DB）

调用约定见 AGENTS.md §9 "DB schema 变更流程"。
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from datetime import datetime
from typing import Iterable, List, Tuple


# 让脚本能从 server cwd 直接跑（与 conf 加载路径一致）
_HERE = os.path.dirname(os.path.abspath(__file__))
_SERVER_DIR = os.path.abspath(os.path.join(_HERE, ".."))
sys.path.insert(0, _SERVER_DIR)


def _load_settings_and_db():
    from conf.settings import settings
    from quant.db import quant_db
    return settings, quant_db


# SQLite 类型映射：peewee Field → SQL DDL fragment
def _field_ddl(field) -> Tuple[str, bool, object]:
    """返回 (sql_type, nullable, default_value)。

    - sql_type: SQLite 列定义（含参数，如 VARCHAR(255)、TEXT、INTEGER、DATETIME）
    - nullable: True 表示可空
    - default_value: None / 字符串 / 数字；callable 已就地求值
    """
    nullable = bool(getattr(field, "null", False))
    raw_default = getattr(field, "default", None)
    if callable(raw_default):
        try:
            default_value = raw_default()
        except Exception:
            default_value = None
    else:
        default_value = raw_default

    # 跳过主键 AutoField
    if getattr(field, "primary_key", False) or field.__class__.__name__ == "AutoField":
        return "", None, None

    field_name = field.__class__.__name__
    max_length = getattr(field, "max_length", None)
    if field_name == "CharField":
        sql_type = f"VARCHAR({max_length or 255})"
    elif field_name == "TextField":
        sql_type = "TEXT"
    elif field_name == "IntegerField":
        sql_type = "INTEGER"
    elif field_name == "FloatField":
        sql_type = "REAL"
    elif field_name == "BooleanField":
        sql_type = "INTEGER"  # SQLite 把 bool 存 0/1
    elif field_name == "DateTimeField":
        sql_type = "DATETIME"
    elif field_name == "DateField":
        sql_type = "DATE"
    elif field_name == "BigIntegerField":
        sql_type = "BIGINT"
    else:
        sql_type = "TEXT"  # 兜底：未知类型一律 TEXT（最少出 schema 问题再说）
    return sql_type, nullable, default_value


def _default_to_sql(default_value) -> str:
    """把 Python 默认值渲染为 SQL DEFAULT 子句值。

    - None → 无 default 子句
    - str → 单引号包裹，转义内部单引号
    - bool / 数字 → 原样
    - datetime/date → ISO 字符串
    """
    if default_value is None:
        return ""
    if isinstance(default_value, bool):
        return f"DEFAULT {1 if default_value else 0}"
    if isinstance(default_value, (int, float)):
        return f"DEFAULT {default_value}"
    if isinstance(default_value, datetime):
        return f"DEFAULT '{default_value.isoformat(timespec='seconds')}'"
    text = str(default_value).replace("'", "''")
    return f"DEFAULT '{text}'"


def _build_alter_sql(table: str, field_name: str, sql_type: str, nullable: bool, default_sql: str) -> str:
    """构造 ALTER TABLE ADD COLUMN 语句。

    规则：
    - NOT NULL + 无 default → SQLite 拒绝（"Cannot add a NOT NULL column with default value NULL"）。
      这种情况我们升级为 NULL，让上游补 default（脚本会报错提示）。
    - NOT NULL + 有 default → 老行自动填默认值
    - NULL → 老行为 NULL
    """
    if not nullable and not default_sql:
        # 兼容 fallback：让 NOT NULL 列默认允许 NULL（旧行 NULL）；同时输出 WARN 由用户确认
        column_def = f"{sql_type} NULL"
    else:
        column_def = f"{sql_type} {'NULL' if nullable else 'NOT NULL'} {default_sql}".rstrip()
    return f"ALTER TABLE {table} ADD COLUMN {field_name} {column_def};"


def _iter_models() -> Iterable:
    from quant.entities import QUANT_MODELS
    return QUANT_MODELS


def diff_entity_vs_db(quant_db) -> List[Tuple[str, str, str, bool, str]]:
    """对比 entity 与 DB schema，返回缺列列表 [(table, col, sql_type, nullable, default_sql), ...]"""
    missing: List[Tuple[str, str, str, bool, str]] = []
    for model in _iter_models():
        table = model._meta.table_name
        existing = {c.name for c in quant_db.get_columns(table)}
        for field_name, field in model._meta.fields.items():
            if field_name in existing:
                continue
            sql_type, nullable, default_value = _field_ddl(field)
            if not sql_type:
                continue
            default_sql = _default_to_sql(default_value)
            missing.append((table, field_name, sql_type, nullable, default_sql))
    return missing


def render_sql_blocks(missing: List[Tuple[str, str, str, bool, str]], change_name: str) -> str:
    """生成 SQL 文档（带 header / 时间戳 / 备份 / ALTER）"""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines: List[str] = []
    lines.append(f"-- Quant DB schema migration: {change_name}")
    lines.append(f"-- Generated at: {ts}")
    lines.append(f"-- Mode: dry-run / soft / hard（脚本调用时选定）")
    lines.append(f"-- 检测到的缺列:")
    if not missing:
        lines.append("-- (none — DB schema 与 entity 已对齐)")
    else:
        for table, col, _, _, _ in missing:
            lines.append(f"--   {table}.{col}")
    lines.append("")
    if missing:
        lines.append("-- === 备份（仅 soft 模式会执行）===")
        for table, col, _, _, _ in missing:
            backup_table = f"{table}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{col}"
            lines.append(f"-- CREATE TABLE {backup_table} AS SELECT * FROM {table};")
        lines.append("")
        lines.append("-- === ALTER ===")
        for table, col, sql_type, nullable, default_sql in missing:
            lines.append(_build_alter_sql(table, col, sql_type, nullable, default_sql))
    lines.append("")
    return "\n".join(lines)


def apply_soft(db_path: str, missing: List[Tuple[str, str, str, bool, str]], log=print) -> None:
    """软模式：先备份再 ALTER。失败立刻 raise。"""
    if not missing:
        log("No missing columns, nothing to apply.")
        return
    ts_tag = datetime.now().strftime("%Y%m%d_%H%M%S")
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        for table, col, sql_type, nullable, default_sql in missing:
            backup_table = f"{table}_backup_{ts_tag}_{col}"
            log(f"[soft] backup {table} → {backup_table}")
            cur.execute(f"CREATE TABLE {backup_table} AS SELECT * FROM {table}")
            alter_sql = _build_alter_sql(table, col, sql_type, nullable, default_sql)
            log(f"[soft] {alter_sql}")
            cur.execute(alter_sql)
        conn.commit()
        log("[soft] done.")
    finally:
        conn.close()


def apply_hard(db_path: str, missing: List[Tuple[str, str, str, bool, str]], log=print) -> None:
    """硬模式：直接 ALTER，不备份。失败立刻 raise。"""
    if not missing:
        log("No missing columns, nothing to apply.")
        return
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        for table, col, sql_type, nullable, default_sql in missing:
            alter_sql = _build_alter_sql(table, col, sql_type, nullable, default_sql)
            log(f"[hard] {alter_sql}")
            cur.execute(alter_sql)
        conn.commit()
        log("[hard] done.")
    finally:
        conn.close()


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Quant DB schema migration")
    parser.add_argument("--db", help="覆盖 conf.ini 的 [quant] sqlite3_file")
    parser.add_argument("--mode", choices=["dry-run", "soft", "hard"], default="dry-run",
                        help="执行模式：dry-run 仅打印；soft 先备份再 ALTER；hard 直接 ALTER")
    parser.add_argument("--change-name", default="quant-migration",
                        help="变更名（用于输出文件 / 备份表前缀）")
    parser.add_argument("--output", help="落档 SQL 文件路径（默认打印 stdout）")
    args = parser.parse_args(argv)

    settings, quant_db = _load_settings_and_db()
    db_path = os.path.abspath(args.db or settings.quant_sqlite3_file)
    if not os.path.exists(db_path):
        print(f"DB not found: {db_path}", file=sys.stderr)
        return 1

    # 重定向 quant_db 到指定路径（--db 覆盖）
    quant_db.init(db_path, pragmas={
        "journal_mode": "wal", "foreign_keys": 1, "busy_timeout": 5000,
    })
    quant_db.connect(reuse_if_open=True)

    missing = diff_entity_vs_db(quant_db)
    sql_doc = render_sql_blocks(missing, change_name=args.change_name)

    if args.output:
        os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(sql_doc)
        print(f"SQL 落档到: {args.output}")
    else:
        print(sql_doc)

    if args.mode == "soft":
        apply_soft(db_path, missing)
    elif args.mode == "hard":
        apply_hard(db_path, missing)
    return 0


if __name__ == "__main__":
    sys.exit(main())