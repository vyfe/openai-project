#!/usr/bin/env python3
"""LLM 对话历史手动备份 / 恢复工具。

数据源：`logs.db` 中 `dialog` 表（实体见 `model.entities.Dialog`）。
  - 字段：id, username, chattype, modelname, dialog_name, start_date, context
  - context 是 JSON 字符串，包含消息列表 / role_setting / usage

子命令：
  backup     备份 dialog 到 JSON 或独立 SQLite 文件
  restore    从备份文件恢复到主库（按 username+chattype+dialog_name 唯一索引去重）
  list       列出备份文件里的 dialog 清单（仅 sqlite 格式有意义）
  stats      打印主库 dialog 表统计信息

DB 路径默认从 `conf.settings.log_sqlite3_file` 读；可用 `--db` 覆盖。

示例：
  python tools/dialog_backup.py stats
  python tools/dialog_backup.py backup --out backups/dialog-20260908.json --user alice
  python tools/dialog_backup.py backup --out backups/dialog-20260908.db --format sqlite
  python tools/dialog_backup.py list --from backups/dialog-20260908.db
  python tools/dialog_backup.py restore --from backups/dialog-20260908.json --dry-run
  python tools/dialog_backup.py restore --from backups/dialog-20260908.db --user alice --on-conflict rename
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime
from typing import Iterable, List, Optional, Tuple


_HERE = os.path.dirname(os.path.abspath(__file__))
_SERVER_DIR = os.path.abspath(os.path.join(_HERE, ".."))
sys.path.insert(0, _SERVER_DIR)


def _resolve_db_path(explicit: Optional[str]) -> str:
    if explicit:
        return os.path.abspath(explicit)
    from conf.settings import settings

    configured = settings.conf.get("log", "sqlite3_file")
    if not os.path.isabs(configured):
        return os.path.abspath(os.path.join(_SERVER_DIR, configured))
    return configured


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _build_filters(args: argparse.Namespace) -> Tuple[str, List]:
    clauses: List[str] = []
    params: List = []
    if getattr(args, "user", None):
        clauses.append("username = ?")
        params.append(args.user)
    if getattr(args, "chattype", None):
        clauses.append("chattype = ?")
        params.append(args.chattype)
    if getattr(args, "since", None):
        clauses.append("start_date >= ?")
        params.append(args.since)
    if getattr(args, "until", None):
        clauses.append("start_date <= ?")
        params.append(args.until)
    return (" WHERE " + " AND ".join(clauses)) if clauses else "", params


def _fetch_dialogs(conn: sqlite3.Connection, where_sql: str, params: List) -> List[sqlite3.Row]:
    sql = (
        "SELECT id, username, chattype, modelname, dialog_name, start_date, context "
        "FROM dialog" + where_sql + " ORDER BY id ASC"
    )
    return list(conn.execute(sql, params))


def cmd_stats(args: argparse.Namespace) -> int:
    db_path = _resolve_db_path(args.db)
    if not os.path.exists(db_path):
        print(f"[stats] 主库不存在: {db_path}")
        return 1
    with _connect(db_path) as conn:
        total = conn.execute("SELECT COUNT(*) FROM dialog").fetchone()[0]
        users = conn.execute(
            "SELECT username, COUNT(*) AS n FROM dialog GROUP BY username ORDER BY n DESC"
        ).fetchall()
        date_range = conn.execute(
            "SELECT MIN(start_date), MAX(start_date) FROM dialog"
        ).fetchone()
    print(f"[stats] DB: {db_path}")
    print(f"[stats] dialog 总数: {total}")
    if date_range[0]:
        print(f"[stats] 日期范围: {date_range[0]} ~ {date_range[1]}")
    print("[stats] 按用户:")
    for row in users:
        print(f"  - {row['username']:<24} {row['n']:>6}")
    return 0


def cmd_backup(args: argparse.Namespace) -> int:
    db_path = _resolve_db_path(args.db)
    if not os.path.exists(db_path):
        print(f"[backup] 主库不存在: {db_path}")
        return 1
    where_sql, params = _build_filters(args)
    with _connect(db_path) as conn:
        rows = _fetch_dialogs(conn, where_sql, params)

    if not rows:
        print("[backup] 没有匹配的 dialog，未生成文件")
        return 0

    out_path = os.path.abspath(args.out)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    fmt = args.format or _infer_format(out_path)

    if fmt == "json":
        payload = {
            "version": 1,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "source_db": db_path,
            "filters": {
                "user": args.user,
                "chattype": args.chattype,
                "since": args.since,
                "until": args.until,
            },
            "count": len(rows),
            "dialogs": [dict(row) for row in rows],
        }
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
        print(f"[backup] 格式: json, {len(rows)} 条 dialog → {out_path}")
        return 0

    if os.path.exists(out_path):
        os.remove(out_path)
    with _connect(out_path) as out:
        out.execute(
            "CREATE TABLE dialog ("
            "id INTEGER, username TEXT, chattype TEXT, modelname TEXT, "
            "dialog_name TEXT, start_date TEXT, context TEXT)"
        )
        out.execute(
            "CREATE TABLE backup_meta ("
            "key TEXT PRIMARY KEY, value TEXT)"
        )
        meta = [
            ("version", "1"),
            ("created_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            ("source_db", db_path),
            ("count", str(len(rows))),
        ]
        if args.user:
            meta.append(("filter_user", args.user))
        if args.chattype:
            meta.append(("filter_chattype", args.chattype))
        if args.since:
            meta.append(("filter_since", args.since))
        if args.until:
            meta.append(("filter_until", args.until))
        out.executemany("INSERT INTO backup_meta(key, value) VALUES (?, ?)", meta)
        out.executemany(
            "INSERT INTO dialog(id, username, chattype, modelname, dialog_name, start_date, context) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    row["id"],
                    row["username"],
                    row["chattype"],
                    row["modelname"],
                    row["dialog_name"],
                    row["start_date"],
                    row["context"],
                )
                for row in rows
            ],
        )

    print(f"[backup] 格式: sqlite, {len(rows)} 条 dialog → {out_path}")
    return 0


def _load_backup(backup_path: str, fmt: str) -> Tuple[List[dict], dict]:
    if fmt == "json":
        with open(backup_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if data.get("version") != 1:
            raise ValueError(f"备份文件版本不受支持: {data.get('version')}")
        return data.get("dialogs", []), data
    with _connect(backup_path) as conn:
        meta = {row["key"]: row["value"] for row in conn.execute("SELECT key, value FROM backup_meta")}
        rows = [dict(r) for r in conn.execute(
            "SELECT id, username, chattype, modelname, dialog_name, start_date, context FROM dialog"
        )]
    return rows, meta


def cmd_list(args: argparse.Namespace) -> int:
    if not os.path.exists(args.source):
        print(f"[list] 备份文件不存在: {args.source}")
        return 1
    fmt = args.format or _infer_format(args.source)
    rows, meta = _load_backup(args.source, fmt)
    print(f"[list] 备份: {args.source} (format={fmt})")
    print(f"[list] version={meta.get('version', '?')} created_at={meta.get('created_at', '?')} count={len(rows)}")
    if "filter_user" in meta:
        print(f"[list] filter_user={meta['filter_user']}")
    for row in rows:
        print(
            f"  id={row['id']:<6} user={row['username']:<20} "
            f"type={row['chattype']:<8} name={row['dialog_name']}"
        )
    return 0


def _infer_format(path: str) -> str:
    if path.endswith(".json"):
        return "json"
    if path.endswith(".db") or path.endswith(".sqlite"):
        return "sqlite"
    raise ValueError(f"无法推断备份格式: {path}（请用 --format 指定）")


def cmd_restore(args: argparse.Namespace) -> int:
    db_path = _resolve_db_path(args.db)
    if not os.path.exists(db_path):
        print(f"[restore] 主库不存在: {db_path}")
        return 1
    if not os.path.exists(args.source):
        print(f"[restore] 备份文件不存在: {args.source}")
        return 1
    fmt = args.format or _infer_format(args.source)
    rows, meta = _load_backup(args.source, fmt)
    if args.user:
        rows = [r for r in rows if r["username"] == args.user]
    if not rows:
        print("[restore] 没有可恢复的 dialog")
        return 0

    print(f"[restore] 源: {args.source} ({len(rows)} 条) → 主库: {db_path}")
    print(f"[restore] 冲突策略: {args.on_conflict}{' (dry-run)' if args.dry_run else ''}")

    plan = {"insert": 0, "skip": 0, "overwrite": 0, "rename": 0}
    with _connect(db_path) as conn:
        existing = {
            (r["username"], r["chattype"], r["dialog_name"]): r["id"]
            for r in conn.execute(
                "SELECT id, username, chattype, dialog_name FROM dialog"
            )
        }
        new_id_hint = (conn.execute("SELECT COALESCE(MAX(id), 0) FROM dialog").fetchone()[0] or 0) + 1

        for row in rows:
            key = (row["username"], row["chattype"], row["dialog_name"])
            if key in existing:
                if args.on_conflict == "skip":
                    plan["skip"] += 1
                    continue
                if args.on_conflict == "overwrite":
                    plan["overwrite"] += 1
                    if not args.dry_run:
                        conn.execute(
                            "UPDATE dialog SET modelname=?, start_date=?, context=? WHERE id=?",
                            (row["modelname"], row["start_date"], row["context"], existing[key]),
                        )
                    continue
                if args.on_conflict == "rename":
                    plan["rename"] += 1
                    new_name = f"{row['dialog_name']}_restored_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                    if not args.dry_run:
                        conn.execute(
                            "INSERT INTO dialog(username, chattype, modelname, dialog_name, start_date, context) "
                            "VALUES (?, ?, ?, ?, ?, ?)",
                            (
                                row["username"],
                                row["chattype"],
                                row["modelname"],
                                new_name,
                                row["start_date"],
                                row["context"],
                            ),
                        )
                        new_id_hint += 1
                    continue
            plan["insert"] += 1
            if not args.dry_run:
                conn.execute(
                    "INSERT INTO dialog(username, chattype, modelname, dialog_name, start_date, context) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        row["username"],
                        row["chattype"],
                        row["modelname"],
                        row["dialog_name"],
                        row["start_date"],
                        row["context"],
                    ),
                )

    print(f"[restore] 计划: {plan}")
    if args.dry_run:
        print("[restore] dry-run 未写入；去掉 --dry-run 实际执行")
    else:
        print("[restore] 完成")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="LLM 对话历史备份 / 恢复工具")
    parser.add_argument("--db", help="主库 logs.db 路径，默认从 conf.ini 读")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_stats = sub.add_parser("stats", help="主库 dialog 表统计")
    p_stats.set_defaults(func=cmd_stats)

    p_backup = sub.add_parser("backup", help="备份 dialog")
    p_backup.add_argument("--out", required=True, help="输出文件路径（.json 或 .db）")
    p_backup.add_argument("--format", choices=["json", "sqlite"], help="输出格式（默认按扩展名推断）")
    p_backup.add_argument("--user", help="按 username 过滤")
    p_backup.add_argument("--chattype", help="按 chattype 过滤")
    p_backup.add_argument("--since", help="起始日期 YYYY-MM-DD（含）")
    p_backup.add_argument("--until", help="截止日期 YYYY-MM-DD（含）")
    p_backup.set_defaults(func=cmd_backup)

    p_list = sub.add_parser("list", help="查看备份文件清单")
    p_list.add_argument("--from", dest="source", required=True, help="备份文件路径")
    p_list.add_argument("--format", choices=["json", "sqlite"], help="备份格式（默认按扩展名推断）")
    p_list.set_defaults(func=cmd_list)

    p_restore = sub.add_parser("restore", help="从备份恢复到主库")
    p_restore.add_argument("--from", dest="source", required=True, help="备份文件路径")
    p_restore.add_argument("--format", choices=["json", "sqlite"], help="备份格式（默认按扩展名推断）")
    p_restore.add_argument("--user", help="只恢复指定用户的 dialog")
    p_restore.add_argument(
        "--on-conflict",
        choices=["skip", "overwrite", "rename"],
        default="skip",
        help="遇到 (username, chattype, dialog_name) 已存在时的处理（默认 skip）",
    )
    p_restore.add_argument("--dry-run", action="store_true", help="只打印计划，不写库")
    p_restore.set_defaults(func=cmd_restore)

    return parser


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
