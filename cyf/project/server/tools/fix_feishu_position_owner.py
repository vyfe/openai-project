"""修复飞书录入的持仓流水归属。

历史原因：`im_event_service._try_create_position_from_command` 曾把 created_by
写成 ``feishu:{open_id}``，而持仓查询 / 汇总一律按慧聊 username 过滤，
导致这些流水在「持仓」里查不到。

本脚本按 ``quant_feishu_user_binding`` 把 ``feishu:{open_id}`` 改写成绑定的
username。默认 dry-run，只报告不改库；加 ``--apply`` 才真正执行。

    python tools/fix_feishu_position_owner.py
    python tools/fix_feishu_position_owner.py --apply
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from quant.entities import QuantFeishuUserBinding, QuantPositionJournal  # noqa: E402

TABLES = ("quant_position_journal",)


def collect_fixes() -> list[dict]:
    """扫出所有 feishu: 前缀且能映射到已绑定 username 的流水。"""
    bindings = {
        f"feishu:{row.feishu_open_id}": row.username
        for row in QuantFeishuUserBinding.select().iterator()
        if row.username
    }
    fixes: list[dict] = []
    for old_owner in bindings:
        username = bindings[old_owner]
        for entry in QuantPositionJournal.select().where(QuantPositionJournal.created_by == old_owner):
            fixes.append({
                "id": entry.id,
                "symbol": entry.symbol,
                "side": entry.side,
                "quantity": entry.quantity,
                "price": entry.price,
                "occurred_at": entry.occurred_at,
                "old_owner": old_owner,
                "new_owner": username,
            })
    return fixes


def main() -> int:
    parser = argparse.ArgumentParser(description="修复飞书持仓流水归属")
    parser.add_argument("--apply", action="store_true", help="真正写库；缺省只 dry-run 报告")
    args = parser.parse_args()

    fixes = collect_fixes()
    if not fixes:
        print("✅ 没有需要修复的流水")
        return 0

    print(f"发现 {len(fixes)} 条归属错误的流水：\n")
    for item in fixes:
        print(
            f"  #{item['id']} {item['symbol']} {item['side']} "
            f"{item['quantity']}@{item['price']} @ {item['occurred_at']}\n"
            f"      {item['old_owner']}  →  {item['new_owner']}"
        )

    if not args.apply:
        print("\n（dry-run，未改库。确认无误后加 --apply 执行）")
        return 0

    for item in fixes:
        QuantPositionJournal.update(created_by=item["new_owner"]).where(
            QuantPositionJournal.id == item["id"]
        ).execute()
    print(f"\n✅ 已修复 {len(fixes)} 条")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
