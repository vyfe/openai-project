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
from service.quant.im_delivery_service import send_channel_content
from service.quant.position_service import list_position_summary


_SECTION_RE = re.compile(r"^(## .+)$", re.MULTILINE)
_FILTERED_SECTIONS = {"## 信号概览", "## 建议动作"}
_MEMORY_SECTION = "## 记忆引用"
_KEEP_SECTIONS = {"## 摘要", "## 市场观察", "## 风险提示", "## 契约说明"}


def _deliver(channel: dict, report: dict, content: str, title: str) -> dict:
    """推一份报告并落审计记录。

    成功/失败都要返回一条 delivery：失败的 status='failed'，调用方据此
    统计「推了几条」而不是「成功几条」，否则失败会静默消失、无从排查。
    """
    from service.quant.im_delivery_service import create_delivery_record

    try:
        result = send_channel_content(channel, content, title=title)
        return create_delivery_record(
            report_id=report.get("id"),
            run_id=report.get("run_id"),
            channel_id=channel.get("channel_id"),
            channel_type=channel.get("channel_type") or "feishu_app",
            channel_target=channel.get("channel_target") or "",
            message_type=result.get("message_type") or "interactive",
            status="success",
            request_payload=result.get("request_payload"),
            response_payload=result.get("response_payload"),
            sent_at=datetime.now(),
        )
    except Exception as exc:
        return create_delivery_record(
            report_id=report.get("id"),
            run_id=report.get("run_id"),
            channel_id=channel.get("channel_id") if channel else None,
            channel_type=(channel.get("channel_type") or "feishu_app") if channel else "feishu_app",
            channel_target=(channel.get("channel_target") or "") if channel else "",
            message_type="interactive",
            status="failed",
            error_message=str(exc),
            sent_at=datetime.now(),
        )


def push_report_filtered_per_channel(channel_ids: list[int], report_id: int) -> list[dict]:
    """单人级 demo：复用同一份报告，按 channel 绑定用户的持仓过滤标的。

    返回每个 channel 的推送结果。``delivery`` 恒为一条审计记录（成功或失败）。
    """
    from quant.entities import QuantReportRecord

    report = QuantReportRecord.get_by_id(report_id).to_dict()
    base_markdown = report.get("final_markdown") or ""
    report_title = str(report.get("title") or "量化报告").strip() or "量化报告"

    results = []
    for cid in (channel_ids or []):
        try:
            user_info = resolve_channel_user(cid)
        except Exception:
            user_info = None

        from quant.entities import QuantStrategy
        from service.quant.ownership import require_quant_user
        strategy = QuantStrategy.get_or_none(QuantStrategy.id == report.get("strategy_id"))
        try:
            target_user = require_quant_user(user_info["username"]) if user_info else None
        except ValueError:
            results.append({"channel_id": cid, "skipped": "账号权限已撤销"})
            continue
        if strategy is not None and strategy.owner_user_id is not None and (target_user is None or target_user.id != strategy.owner_user_id):
            results.append({"channel_id": cid, "skipped": "报告归属不匹配"})
            continue
        if not user_info:
            # 群聊 / 无绑定用户：推全量报告（保持现有行为）
            try:
                channel = load_channel(channel_id=int(cid))
            except Exception as exc:
                results.append({
                    "channel_id": cid,
                    "username": None,
                    "delivery": _deliver(None, report, base_markdown, report_title),
                    "filter_applied": False,
                    "error": str(exc),
                })
                continue
            results.append({
                "channel_id": cid,
                "username": None,
                # 走 interactive 卡片：飞书渲染 markdown，而不是把源码当纯文本甩出来
                "delivery": _deliver(channel, report, base_markdown, report_title),
                "filter_applied": False,
            })
            continue

        # 拿用户持仓 symbol 集合
        try:
            positions = list_position_summary(owner_user_id=target_user.id)
        except Exception as exc:
            results.append({
                "channel_id": cid,
                "username": user_info["username"],
                "delivery": _deliver(None, report, base_markdown, report_title),
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
        except Exception as exc:
            results.append({
                "channel_id": cid,
                "username": user_info["username"],
                "delivery": _deliver(None, report, content, report_title),
                "filter_applied": True,
                "held_symbols": sorted(held_symbols),
                "error": str(exc),
            })
            continue

        results.append({
            "channel_id": cid,
            "username": user_info["username"],
            "delivery": _deliver(channel, report, content, report_title),
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
