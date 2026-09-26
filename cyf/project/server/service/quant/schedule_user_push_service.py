"""单人级通道推送 demo。

按 channel 反查绑定用户，按其持仓过滤报告内容后单独推送。
群聊 channel（无 user 关联）→ 推全量报告（保持现有行为）。
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

from service.quant.channel_user_resolver import resolve_channel_user
from service.quant.im_channel_service import load_channel
from service.quant.im_delivery_service import send_feishu_text
from service.quant.position_service import list_position_summary


_SECTION_RE = re.compile(r"^(## .+)$", re.MULTILINE)
_FILTERED_SECTIONS = {"## 信号概览", "## 建议动作"}
_MEMORY_SECTION = "## 记忆引用"
_KEEP_SECTIONS = {"## 摘要", "## 市场观察", "## 风险提示", "## 契约说明"}


def push_report_filtered_per_channel(channel_ids: list[int], report_id: int) -> list[dict]:
    """单人级 demo：复用同一份报告，按 channel 绑定用户的持仓过滤标的。

    返回每个 channel 的推送结果。
    """
    from quant.entities import QuantReportRecord

    report = QuantReportRecord.get_by_id(report_id)
    base_markdown = report.final_markdown or ""

    results = []
    for cid in (channel_ids or []):
        try:
            user_info = resolve_channel_user(cid)
        except Exception:
            user_info = None

        if not user_info:
            # 群聊 / 无绑定用户：推全量报告（保持现有行为）
            try:
                channel = load_channel(channel_id=int(cid))
                delivery = send_feishu_text(channel=channel, content=base_markdown)
            except Exception as exc:
                results.append({
                    "channel_id": cid,
                    "username": None,
                    "delivery": None,
                    "filter_applied": False,
                    "error": str(exc),
                })
                continue
            results.append({
                "channel_id": cid,
                "username": None,
                "delivery": delivery,
                "filter_applied": False,
            })
            continue

        # 拿用户持仓 symbol 集合
        try:
            positions = list_position_summary(created_by=user_info["username"])
        except Exception as exc:
            results.append({
                "channel_id": cid,
                "username": user_info["username"],
                "delivery": None,
                "filter_applied": True,
                "error": f"position_query_failed: {exc}",
            })
            continue

        held_symbols = {p["symbol"] for p in positions if (p.get("net_quantity") or 0) > 0}

        # 按持仓过滤报告内容
        filtered = filter_report_by_symbols(base_markdown, held_symbols)

        # 拼接用户持仓摘要前缀
        if positions:
            prefix = _render_position_prefix(user_info["username"], positions)
            content = prefix + "\n\n" + filtered
        else:
            content = "（当前无持仓，以下为通用市场观察）\n\n" + filtered

        try:
            channel = load_channel(channel_id=int(cid))
            delivery = send_feishu_text(channel=channel, content=content)
        except Exception as exc:
            results.append({
                "channel_id": cid,
                "username": user_info["username"],
                "delivery": None,
                "filter_applied": True,
                "held_symbols": sorted(held_symbols),
                "error": str(exc),
            })
            continue

        results.append({
            "channel_id": cid,
            "username": user_info["username"],
            "delivery": delivery,
            "filter_applied": True,
            "held_symbols": sorted(held_symbols),
        })
    return results


def filter_report_by_symbols(markdown: str, held_symbols: set[str]) -> str:
    """按段落过滤报告 markdown。

    保留：标题、摘要、市场观察、风险提示、契约说明、custom_sections
    过滤：信号概览 / 建议动作（按行过滤，只保留提及持仓 symbol 的行）
    过滤：记忆引用（按 symbol 列表过滤）
    """
    if not markdown:
        return markdown
    if not held_symbols:
        # 无持仓：过滤掉标的相关段，保留通用段
        held_symbols = set()

    # 按 `## ` 段落切分；split 保留分隔符
    parts = _SECTION_RE.split(markdown)
    # parts 结构：["前导", "## 标题", "正文", "## 信号概览", "正文", ...]
    out: list[str] = []
    title_done = False

    # 如果第一段不是以 ## 开头，是标题段（# 标题）和它的正文
    if parts and parts[0].strip():
        out.append(parts[0])

    i = 1
    while i < len(parts):
        heading = parts[i].strip()
        body = parts[i + 1] if i + 1 < len(parts) else ""
        i += 2

        # 标题段（## xxx 形式）
        if heading.startswith("# ") and not title_done:
            out.append(heading)
            out.append(body)
            title_done = True
            continue

        # 保留段（全局性，不过滤）
        if heading in _KEEP_SECTIONS:
            out.append(heading)
            out.append(body)
            continue

        # 过滤段：按行过滤
        if heading in _FILTERED_SECTIONS:
            kept_lines = _filter_lines_by_symbols(body, held_symbols)
            if kept_lines:
                out.append(heading)
                out.append(kept_lines)
            continue

        # 记忆引用：按 symbol 列表过滤
        if heading == _MEMORY_SECTION:
            kept_lines = _filter_memory_references(body, held_symbols)
            if kept_lines:
                out.append(heading)
                out.append(kept_lines)
            continue

        # 其他段（custom_sections 等）：原样保留
        out.append(heading)
        out.append(body)

    return "\n".join(out)


def _filter_lines_by_symbols(body: str, held_symbols: set[str]) -> str:
    """按行过滤：只保留提及持仓 symbol 的行。"""
    if not body or not held_symbols:
        return ""
    kept = []
    for line in body.splitlines():
        if _line_mentions_any_symbol(line, held_symbols):
            kept.append(line)
    return "\n".join(kept)


def _filter_memory_references(body: str, held_symbols: set[str]) -> str:
    """记忆引用段：按 `- {symbol}` 列表项过滤。"""
    if not body or not held_symbols:
        return ""
    kept = []
    for line in body.splitlines():
        # 格式：- 600519.SH
        match = re.match(r"^\s*-\s*(\S+)", line)
        if match and match.group(1) in held_symbols:
            kept.append(line)
    return "\n".join(kept)


def _line_mentions_any_symbol(line: str, held_symbols: set[str]) -> bool:
    """判断一行是否提及任何持仓 symbol（精确匹配词边界）。"""
    if not line or not held_symbols:
        return False
    # 用 word boundary 避免 "600519.SH" 误匹配 "600519"
    for sym in held_symbols:
        if re.search(rf"(?<![0-9A-Z]){re.escape(sym)}(?![0-9A-Z])", line):
            return True
    return False


def _render_position_prefix(username: str, positions: list[dict]) -> str:
    """渲染用户持仓摘要前缀（轻量 markdown）。"""
    lines = [
        f"## 📊 {username} 当前持仓",
        "",
    ]
    for item in positions[:20]:
        sym = item.get("symbol", "--")
        qty = item.get("net_quantity", 0)
        avg_cost = item.get("avg_cost")
        latest = item.get("latest_price")
        pnl_pct = item.get("unrealized_pnl_pct")
        cost_str = "--" if avg_cost is None else f"{round(float(avg_cost), 2)}"
        price_str = "--" if latest is None else f"{round(float(latest), 2)}"
        pnl_str = "--" if pnl_pct is None else f"{round(float(pnl_pct) * 100, 2)}%"
        lines.append(f"- `{sym}` 持仓 `{qty}` 股 | 成本 `{cost_str}` | 现价 `{price_str}` | 浮盈 `{pnl_str}`")
    lines.extend([
        "",
        f"_数据时间: {datetime.now().isoformat(timespec='seconds')}_",
        "",
        "---",
        "",
    ])
    return "\n".join(lines)
