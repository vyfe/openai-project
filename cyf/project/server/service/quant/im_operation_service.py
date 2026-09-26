"""飞书量化操作记录：位置化解析 + 直接入库（无二次确认）。"""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta
from typing import Optional

from peewee import DoesNotExist

from quant.entities import QuantImInboundEvent
from service.quant.binding_service import get_username_by_feishu
from service.quant.common import normalize_symbol, parse_trade_date
from service.quant.im_helpers import truncate_text
from service.quant.ops_service import create_operation_record, list_operation_records


# ---- 别名常量（保留所有原有映射） ----
_ACTION_ALIASES = {
    "买": "buy",
    "买入": "buy",
    "buy": "buy",
    "加仓": "add",
    "加": "add",
    "add": "add",
    "减仓": "reduce",
    "减": "reduce",
    "reduce": "reduce",
    "卖": "sell",
    "卖出": "sell",
    "sell": "sell",
    "观察": "watch",
    "关注": "watch",
    "watch": "watch",
}
_STATUS_ALIASES = {
    "草稿": "draft",
    "计划": "draft",
    "待执行": "draft",
    "draft": "draft",
    "已执行": "executed",
    "执行": "executed",
    "executed": "executed",
    "已结束": "closed",
    "结束": "closed",
    "closed": "closed",
    "已取消": "cancelled",
    "取消": "cancelled",
    "cancelled": "cancelled",
}
_RESULT_STATUS_ALIASES = {
    "待复盘": "pending",
    "pending": "pending",
    "盈利": "win",
    "胜": "win",
    "win": "win",
    "亏损": "loss",
    "负": "loss",
    "loss": "loss",
    "持平": "flat",
    "flat": "flat",
}
_ACTION_LABELS = {value: key for key, value in {
    "买入": "buy", "加仓": "add", "减仓": "reduce", "卖出": "sell", "观察": "watch",
}.items()}
_STATUS_LABELS = {"draft": "草稿", "executed": "已执行", "closed": "已结束", "cancelled": "已取消"}
_RESULT_STATUS_LABELS = {"pending": "待复盘", "win": "盈利", "loss": "亏损", "flat": "持平"}

# 查询前缀（保留——避免和 position_entry 冲突）
_HISTORY_PREFIXES = ("操作历史", "历史操作", "查操作", "操作记录")

# 已废弃的二次确认命令（向后兼容保留字面，提示用户）
_CONFIRM_RE = re.compile(r"^(?:确认|confirm)\s+OP-(\d+)$", re.IGNORECASE)
_CANCEL_RE = re.compile(r"^(?:取消|cancel)\s+OP-(\d+)$", re.IGNORECASE)


# ---- 工具函数 ----
def _clean_command(text: str) -> str:
    return re.sub(r"^[/#\s]+", "", str(text or "").strip())


def _starts_with(text: str, prefixes: tuple[str, ...]) -> Optional[str]:
    for prefix in prefixes:
        if text == prefix or text.startswith(f"{prefix} ") or text.startswith(f"{prefix}|"):
            return prefix
    return None


def _parse_number(value, *, integer: bool = False, field: str = "数值"):
    text = re.sub(r"[^0-9.\-]", "", str(value or ""))
    if not text:
        raise ValueError(f"{field}必须是数字")
    try:
        number = int(float(text)) if integer else float(text)
    except ValueError as exc:
        raise ValueError(f"{field}格式错误：{value}") from exc
    if number <= 0 and field != "价格":
        raise ValueError(f"{field}必须大于 0")
    return number


def _looks_like_date(value: str) -> bool:
    """判断字符串是否可解析为日期。支持 YYYY-MM-DD / YYYY/MM/DD / YYYYMMDD。"""
    text = str(value or "").strip()
    if not text:
        return False
    if not re.fullmatch(r"\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{8}", text):
        return False
    try:
        parse_trade_date(text)
        return True
    except ValueError:
        return False


def _looks_like_compact_date(value: str) -> bool:
    """判断是否为 8 位紧凑日期 YYYYMMDD（如 20260926）。"""
    text = str(value or "").strip()
    if not re.fullmatch(r"\d{8}", text):
        return False
    try:
        parse_trade_date(text)
        return True
    except ValueError:
        return False


_TRADE_FIELD_SEP_RE = re.compile(r"[,，\s]+")


def _split_trade_command(text: str) -> list[str]:
    """按「,」「，」「空格」任意分隔符切分命令字符串。"""
    if not text:
        return []
    return [item for item in _TRADE_FIELD_SEP_RE.split(str(text).strip()) if item]


def _resolve_symbol_in_pool(symbol_or_name: str) -> dict:
    """校验股票代码/名称是否在 quant_instrument 股票池中。

    匹配顺序（精确匹配）：symbol → code → name → custom_name。
    """
    from quant.entities import QuantInstrument
    raw = str(symbol_or_name or "").strip()
    if not raw:
        raise ValueError("股票代码或名称不能为空")

    candidates = [raw]
    if "." in raw:
        code_only = raw.split(".")[0]
        if code_only and code_only not in candidates:
            candidates.append(code_only)
    else:
        if raw.isdigit() and len(raw) == 6:
            if raw.startswith("6"):
                candidates.append(f"{raw}.SH")
            elif raw.startswith("0") or raw.startswith("3"):
                candidates.append(f"{raw}.SZ")

    record = None
    for cand in candidates:
        record = QuantInstrument.select().where(
            (QuantInstrument.symbol == cand)
            | (QuantInstrument.code == cand)
            | (QuantInstrument.name == cand)
            | (QuantInstrument.custom_name == cand)
        ).first()
        if record:
            break

    if not record:
        raise ValueError(
            f"❌ 股票「{raw}」不在股票池中。\n"
            f"请在「数据中心」页面添加，或使用已加入股票池的股票代码/名称。"
        )
    return {
        "symbol": record.symbol,
        "code": record.code,
        "name": record.name or record.custom_name or record.symbol,
        "exchange": record.exchange,
    }


def _normalize_action(value: str) -> str:
    normalized = _ACTION_ALIASES.get(str(value or "").strip().lower())
    if not normalized:
        raise ValueError("动作仅支持：买入、加仓、减仓、卖出、观察")
    return normalized


def _normalize_status(value: str) -> str:
    normalized = _STATUS_ALIASES.get(str(value or "").strip().lower())
    if not normalized:
        raise ValueError("执行状态仅支持：草稿、已执行、已结束、已取消")
    return normalized


def _normalize_result_status(value: str) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    normalized = _RESULT_STATUS_ALIASES.get(text)
    if normalized is None:
        raise ValueError("结果状态仅支持：待复盘、盈利、亏损、持平")
    return normalized


def _normalize_tags(value: str) -> list[str]:
    return [item.strip() for item in re.split(r"[,，、/]", str(value or "")) if item.strip()]


# ---- 位置化解析（统一快速登记 + 操作登记） ----
def _parse_position_payload(text: str) -> dict:
    """位置化解析交易命令。

    格式：[动作,股票,数量,价格[,8位日期][,备注][,状态][,标签]]
    - 8 位紧凑日期（YYYYMMDD）可以出现在任意位置（除动作/股票外），识别后即作为 trade_date
    - 后续列按顺序识别：状态别名 → status；含 / , 、 的 → tags；其余 → remark
    """
    main_tokens = _split_trade_command(_clean_command(text))
    if len(main_tokens) < 3:
        raise ValueError(_operation_usage())

    # 探测「已X」前缀（已买/已卖/已加仓/已减仓/已观察）→ 自动标记 status=executed
    auto_status: Optional[str] = None
    first_token = main_tokens[0]
    if first_token.startswith("已") and len(first_token) >= 2:
        stripped = first_token[1:]
        if stripped.lower() in {k.lower() for k in _ACTION_ALIASES}:
            main_tokens[0] = stripped
            auto_status = "executed"

    action = _normalize_action(main_tokens[0])
    instrument = _resolve_symbol_in_pool(main_tokens[1])
    symbol = instrument["symbol"]

    # 提取 8 位紧凑日期（如果存在）—— 任意位置出现都识别
    trade_date = date.today()
    date_positions = [i for i, tok in enumerate(main_tokens[2:], start=2) if _looks_like_compact_date(tok)]
    if date_positions:
        trade_date = parse_trade_date(main_tokens[date_positions[0]])
        # 把日期 token 移除，剩下的 main_tokens 视为 [动作,股票,数量,价格,备注,...]
        main_tokens = [tok for i, tok in enumerate(main_tokens) if i not in date_positions]

    # 现在 main_tokens[2]=数量、[3]=价格
    if len(main_tokens) < 4:
        raise ValueError("必须填写数量和价格")
    quantity = _parse_number(main_tokens[2], integer=True, field="数量")
    if action == "watch":
        price = None
    else:
        price = _parse_number(main_tokens[3], field="价格")
        if price is not None and price < 0:
            raise ValueError("价格不能小于 0")

    # 解析剩余 token：状态 / 标签 / 备注（按出现顺序，首个状态别名为 status）
    rest = main_tokens[4:]
    remark_parts: list[str] = []
    status: Optional[str] = None  # 用户显式指定的状态
    tags: list[str] = []
    for tok in rest:
        compact = tok.lower().replace(" ", "")
        if status is None and compact in {k.lower().replace(" ", "") for k in _STATUS_ALIASES}:
            status = _normalize_status(tok)
            continue
        if "/" in tok or "、" in tok or "," in tok:
            tags.extend(_normalize_tags(tok))
            continue
        remark_parts.append(tok)

    # 最终 status 优先级：用户显式 > 已X 前缀自动 > None（None 时由 create_operation_record 默认 draft）
    final_status = status if status is not None else auto_status

    return {
        "symbol": symbol,
        "action": action,
        "quantity": quantity,
        "price": price,
        "trade_date": trade_date,
        "status": final_status,
        "thesis": " ".join(remark_parts),
        "tags": tags,
    }


def _operation_usage() -> str:
    return (
        "用法（分隔符「,」「，」「空格」任选）：\n"
        "  简版（默认今天）：买,002837,200,12,突破年线\n"
        "  带日期（8 位）：买,002837,20260920,200,12,突破年线\n"
        "  完整字段：买,002837,200,12,20260920,突破年线,已执行,趋势仓/观察仓\n"
        "提示：日期格式 YYYYMMDD；状态可选 草稿/已执行/已结束/已取消；"
        "标签用 / , 、 分隔多个。"
    )


def _require_bound_user(parsed: dict) -> str:
    sender_id = str(parsed.get("sender_id") or "").strip()
    username = get_username_by_feishu(sender_id) if sender_id else None
    if not username:
        raise ValueError("当前飞书账号尚未绑定量化用户，请先在私聊中完成绑定")
    return username


def _operation_from_payload(payload: dict, *, username: str) -> dict:
    """将解析结果转换为 create_operation_record 接受的字段并入库。"""
    op = dict(payload)
    op["created_by"] = username
    return create_operation_record(**op)


# ---- 历史 / 详情查询（保留） ----
def _parse_history_query(text: str) -> dict:
    query_text = _clean_command(text)
    prefix = _starts_with(query_text, _HISTORY_PREFIXES)
    if prefix:
        query_text = query_text[len(prefix):].strip()
    query: dict = {"limit": 20}
    for token in [item for item in re.split(r"\s+", query_text) if item]:
        compact = token.lower().replace(" ", "")
        if compact in ("今天", "今日"):
            today = date.today().isoformat()
            query.update(date_from=today, date_to=today)
        elif re.fullmatch(r"近\d+天", compact):
            days = int(re.sub(r"[^0-9]", "", compact))
            query["date_from"] = (date.today() - timedelta(days=max(1, days) - 1)).isoformat()
            query["date_to"] = date.today().isoformat()
        elif compact in _STATUS_ALIASES:
            query["status"] = _normalize_status(compact)
        elif compact in _RESULT_STATUS_ALIASES:
            query["result_status"] = _normalize_result_status(compact)
        elif compact in _ACTION_ALIASES:
            query["action"] = _normalize_action(compact)
        elif _looks_like_date(compact):
            parsed_date = parse_trade_date(compact).isoformat()
            query.update(date_from=parsed_date, date_to=parsed_date)
        else:
            query["symbol"] = normalize_symbol(token)
    return query


def _format_history(records: list[dict], query: dict) -> str:
    if not records:
        return "没有找到符合条件的操作记录。"
    lines = [f"操作历史（{len(records)} 条，最多展示 {query.get('limit', 20)} 条）："]
    for item in records:
        action = _ACTION_LABELS.get(item.get("action"), item.get("action") or "--")
        status = _STATUS_LABELS.get(item.get("status"), item.get("status") or "--")
        result = _RESULT_STATUS_LABELS.get(item.get("result_status"), item.get("result_status") or "--")
        quantity = item.get("quantity") if item.get("quantity") is not None else "--"
        price = item.get("price") if item.get("price") is not None else "--"
        lines.append(f"#{item['id']} {item['trade_date']} {item['symbol']} {action} {quantity}股 @ {price}｜{status}｜{result}")
        if item.get("thesis"):
            lines.append(f"  理由：{truncate_text(item['thesis'], limit=120)}")
    return truncate_text("\n".join(lines), limit=8500)


def _history_command(text: str, parsed: dict) -> tuple[str, str]:
    username = _require_bound_user(parsed)
    query = _parse_history_query(text)
    records = list_operation_records(created_by=username, **query)
    return "operation_history", _format_history(records, query)


def _render_operation_created(operation: dict) -> str:
    """渲染创建成功的简洁消息。"""
    action_label = _ACTION_LABELS.get(operation.get("action"), operation.get("action"))
    symbol = operation.get("symbol")
    quantity = operation.get("quantity")
    price = operation.get("price")
    trade_date = operation.get("trade_date")
    status_label = _STATUS_LABELS.get(operation.get("status"), operation.get("status"))

    price_text = f" @ {price}" if price not in (None, "", 0) else ""
    lines = [
        f"✅ 已登记操作：{action_label} {symbol} {quantity}股{price_text}",
        f"日期：{trade_date}｜状态：{status_label}",
        f"记录 ID: {operation['id']}",
    ]
    if operation.get("thesis"):
        lines.append(f"备注：{truncate_text(operation['thesis'], limit=200)}")
    if operation.get("tags"):
        tag_value = operation.get("tags")
        if isinstance(tag_value, str):
            try:
                tag_list = json.loads(tag_value)
            except (ValueError, TypeError):
                tag_list = [t.strip() for t in tag_value.split(",") if t.strip()]
        else:
            tag_list = list(tag_value)
        if tag_list:
            lines.append(f"标签：{', '.join(tag_list)}")
    return "\n".join(lines)


# ---- 入口 ----
def handle_operation_command(text: str, parsed: dict, event_record_id: int) -> Optional[tuple[str, str]]:
    """处理操作相关命令（直接入库，无二次确认）。

    - /确认 OP-X / /取消 OP-X：已废弃，提示用户
    - 操作历史：查询
    - 其余位置化命令：直接入库
    """
    command_text = _clean_command(text)

    # 已废弃的二次确认
    if _CONFIRM_RE.match(command_text):
        return "operation_deprecated", "ℹ️ 操作登记已改为直接入库，不再需要「确认 OP-x」。"
    if _CANCEL_RE.match(command_text):
        return "operation_deprecated", "ℹ️ 操作登记已改为直接入库，没有待确认项。"

    # 查询类
    if _starts_with(command_text, _HISTORY_PREFIXES):
        try:
            return _history_command(command_text, parsed)
        except ValueError as exc:
            return "operation_history_error", f"❌ {exc}"

    # 操作登记（位置化解析 + 直接入库）
    if _looks_like_operation_payload(command_text):
        try:
            username = _require_bound_user(parsed)
            payload = _parse_position_payload(command_text)
            payload["created_by"] = username
            operation = _operation_from_payload(payload, username=username)
            return "operation_created", _render_operation_created(operation)
        except ValueError as exc:
            return "operation_create_error", f"❌ {exc}\n{_operation_usage()}"

    return None


def _looks_like_operation_payload(text: str) -> bool:
    """判断文本是否应作为操作登记处理（位置化格式）。

    判定条件（任一）：
    1. 主参数至少 4 列，且首列是动作别名（买/卖/...）
    2. 主参数至少 3 列且第 3 或第 4 列是 8 位紧凑日期
    """
    if not text:
        return False
    main_tokens = _split_trade_command(text)
    if len(main_tokens) < 3:
        return False
    # 判定首列是合法动作（含「已X」前缀）→ 入库为 operation record
    first = main_tokens[0]
    action_keys = {k.lower() for k in _ACTION_ALIASES}
    if len(main_tokens) >= 4 and (
        first.lower() in action_keys
        or (first.startswith("已") and len(first) >= 2 and first[1:].lower() in action_keys)
    ):
        return True
    # 仅含日期（短格式）也命中
    if _looks_like_compact_date(main_tokens[2] if len(main_tokens) > 2 else ""):
        return True
    if _looks_like_compact_date(main_tokens[3] if len(main_tokens) > 3 else ""):
        return True
    return False
