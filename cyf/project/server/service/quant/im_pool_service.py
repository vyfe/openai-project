"""飞书「加入股票池」指令。

命令格式：``加入,600519,贵州茅台``（分隔符「,」「，」「空格」任选）
别名：加池 / 加自选 / 添加 / 关注池

加入成功后自动排一个日线回补任务，与新建持仓时的回补行为保持一致，
用户不需要再去「数据中心」点一次「立即获取数据」。
"""

from __future__ import annotations

import re
from typing import Optional

from service.quant.im_help_text import pool_usage
from service.quant.instrument_pool_service import add_instruments_by_keywords


_POOL_PREFIXES = ("加入", "加池", "加自选", "添加", "关注池")
_POOL_SPLIT_RE = re.compile(r"[,，\s]+")
_MAX_KEYWORDS = 10


def _clean(text: str) -> str:
    return re.sub(r"^[/#\s]+", "", str(text or "").strip())


def strip_pool_prefix(text: str) -> Optional[str]:
    """匹配股票池命令前缀，返回去掉前缀后的参数串；不匹配返回 None。

    要求前缀后必须有内容，避免「加入」二字单独成句被误判为命令。
    """
    cleaned = _clean(text)
    for prefix in _POOL_PREFIXES:
        if cleaned == prefix:
            return ""
        if not cleaned.startswith(prefix):
            continue
        rest = cleaned[len(prefix):]
        # 前缀后面必然跟分隔符（逗号/空格），否则「加入茅台」这种会被误当命令
        if not rest or rest[0] not in ",， \t":
            continue
        return rest.lstrip(",， \t").strip()
    return None


def _render_result(result: dict, *, username: str) -> str:
    added = result.get("added") or []
    existing = result.get("existing") or []
    failed = result.get("failed") or []

    lines: list[str] = []
    if added:
        lines.append(f"✅ 已加入股票池（{len(added)} 只）：")
        for item in added:
            lines.append(f"  · {item['code']} {item['name']}")
    if existing:
        lines.append(f"ℹ️ 已在池中（{len(existing)} 只）：" + "、".join(
            f"{i['code']} {i['name']}" for i in existing
        ))
    if failed:
        if lines:
            lines.append("")
        lines.append(f"❌ 有 {len(failed)} 只没加成功：")
        for item in failed:
            lines.append(f"  · 「{item['keyword']}」{item['reason']}")
            for candidate in item.get("candidates") or []:
                lines.append(f"      候选：{candidate}")

    if added:
        symbols = [item["symbol"] for item in added]
        lines.append("")
        lines.append(f"已排日线回补任务（{len(symbols)} 只，近 6 个月），行情到账约需一两分钟。")
        lines.append("现在可以直接登记交易了，例如：买入," + added[0]["code"] + ",100,10")

    if not lines:
        return f"❌ 没有解析到要加入的标的。\n{pool_usage()}"

    return "\n".join(lines)


def handle_pool_command(text: str, parsed: dict) -> Optional[tuple[str, str]]:
    """处理股票池命令。参数为空或解析失败时返回 None，交给后续路由兜底。"""
    from service.quant.im_operation_service import _require_bound_user

    arg_text = strip_pool_prefix(text)
    if arg_text is None:
        return None

    if not arg_text:
        return "pool_usage", f"请在「加入」后面跟股票代码或中文名。\n{pool_usage()}"

    username = _require_bound_user(parsed)
    from service.quant.ownership import require_quant_user
    from model.repositories.user_repository import get_user_roles
    if 'admin' not in get_user_roles(require_quant_user(username).id):
        return "auth_error", "股票池管理需要管理员权限"
    keywords = [item for item in _POOL_SPLIT_RE.split(arg_text) if item]
    if len(keywords) > _MAX_KEYWORDS:
        return "pool_error", f"一次最多加入 {_MAX_KEYWORDS} 只，请分批发送。"

    result = add_instruments_by_keywords(keywords, source=f"feishu:{username}")
    if result.get("added"):
        _enqueue_backfill([item["symbol"] for item in result["added"]], username=username)

    command = "pool_added" if result.get("added") else "pool_noop"
    return command, _render_result(result, username=username)


def _enqueue_backfill(symbols: list[str], *, username: str) -> None:
    """排日线回补任务。失败只记日志，不影响加入成功的回复。"""
    import logging

    from service.quant.position_service import DEFAULT_BACKFILL_DAYS, enqueue_position_backfill_task

    try:
        enqueue_position_backfill_task(
            symbols=symbols,
            created_by=username,
            lookback_days=DEFAULT_BACKFILL_DAYS,
            note="backfill:feishu_pool_add",
        )
    except Exception as exc:
        logging.getLogger("quant.im").warning(
            "[im-pool] 回补任务创建失败 | symbols=%s | error=%s", symbols, exc
        )
