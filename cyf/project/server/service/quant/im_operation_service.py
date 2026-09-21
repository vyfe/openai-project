"""飞书量化操作登记 MVP：文本指令、二次确认与历史查询。"""

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
from service.quant.ops_service import create_operation_record, get_operation_record, list_operation_records


_ACTION_ALIASES = {
    "买": "buy",
    "买入": "buy",
    "buy": "buy",
    "加仓": "add",
    "add": "add",
    "减仓": "reduce",
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
_ACTION_LABELS = {value: key for key, value in {"买入": "buy", "加仓": "add", "减仓": "reduce", "卖出": "sell", "观察": "watch"}.items()}
_STATUS_LABELS = {"draft": "草稿", "executed": "已执行", "closed": "已结束", "cancelled": "已取消"}
_RESULT_STATUS_LABELS = {"pending": "待复盘", "win": "盈利", "loss": "亏损", "flat": "持平"}
_OPERATION_PREFIXES = ("录入操作", "新增操作", "操作登记", "记录操作")
_HISTORY_PREFIXES = ("操作历史", "历史操作", "查操作", "操作记录")
_DETAIL_PREFIXES = ("操作详情", "查看操作")
_CONFIRM_RE = re.compile(r"^(?:确认|confirm)\s+OP-(\d+)$", re.IGNORECASE)
_CANCEL_RE = re.compile(r"^(?:取消|cancel)\s+OP-(\d+)$", re.IGNORECASE)


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
        raise ValueError(f"{field}必须是数字") from exc
    return number


def _looks_like_date(value: str) -> bool:
    text = str(value or "").strip()
    return bool(re.fullmatch(r"\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{8}", text))


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
    if not normalized:
        raise ValueError("结果状态仅支持：待复盘、盈利、亏损、持平")
    return normalized


def _normalize_tags(value: str) -> list[str]:
    return [item.strip() for item in re.split(r"[,，、]", str(value or "")) if item.strip()]


def _parse_key_values(parts: list[str]) -> dict[str, str]:
    values: dict[str, str] = {}
    for part in parts:
        item = part.strip()
        if not item:
            continue
        matched = re.match(r"^([^=:：]+)\s*[=:：]\s*(.*)$", item)
        if not matched:
            raise ValueError(f"扩展参数格式错误：{item}，请使用“字段=值”")
        key = matched.group(1).strip().lower()
        values[key] = matched.group(2).strip()
    return values


def _parse_operation_payload(text: str) -> dict:
    sections = [item.strip() for item in _clean_command(text).split("|")]
    main_tokens = [item for item in re.split(r"\s+", sections[0]) if item]
    if len(main_tokens) < 3:
        raise ValueError(_operation_usage())

    action = _normalize_action(main_tokens[1])
    symbol = normalize_symbol(main_tokens[2])
    tail = main_tokens[3:]
    trade_date = date.today()
    if tail and _looks_like_date(tail[0]):
        trade_date = parse_trade_date(tail.pop(0))

    quantity = None
    price = None
    if action != "watch":
        if not tail:
            raise ValueError("买入/卖出等交易操作必须填写数量")
        quantity = _parse_number(tail.pop(0), integer=True, field="数量")
        if quantity <= 0:
            raise ValueError("数量必须大于 0")
        if tail:
            price = _parse_number(tail.pop(0), field="价格")
            if price < 0:
                raise ValueError("价格不能小于 0")
    elif tail:
        price = _parse_number(tail.pop(0), field="价格")
        if price < 0:
            raise ValueError("价格不能小于 0")
    if tail:
        raise ValueError("主参数过多，请使用“| 字段=值”补充理由、标签等信息")

    extras = _parse_key_values(sections[1:])
    key_aliases = {
        "日期": "trade_date",
        "交易日": "trade_date",
        "trade_date": "trade_date",
        "状态": "status",
        "status": "status",
        "结果": "result_status",
        "结果状态": "result_status",
        "result_status": "result_status",
        "理由": "thesis",
        "原因": "thesis",
        "thesis": "thesis",
        "备注": "execution_note",
        "执行备注": "execution_note",
        "execution_note": "execution_note",
        "复盘": "review_note",
        "复盘备注": "review_note",
        "review_note": "review_note",
        "标签": "tags",
        "tags": "tags",
        "收益率": "result_pct",
        "结果收益率": "result_pct",
        "result_pct": "result_pct",
        "结果金额": "result_amount",
        "result_amount": "result_amount",
        "金额": "amount",
        "amount": "amount",
        "策略": "strategy_id",
        "策略id": "strategy_id",
        "strategy_id": "strategy_id",
        "运行id": "run_id",
        "run_id": "run_id",
        "信号id": "signal_id",
        "signal_id": "signal_id",
    }
    normalized_extras = {key_aliases.get(key, key): value for key, value in extras.items()}
    supported_fields = {
        "trade_date",
        "status",
        "result_status",
        "thesis",
        "execution_note",
        "review_note",
        "tags",
        "result_pct",
        "result_amount",
        "amount",
        "price",
        "quantity",
        "strategy_id",
        "run_id",
        "signal_id",
    }
    unknown_fields = sorted(set(normalized_extras) - supported_fields)
    if unknown_fields:
        raise ValueError(f"不支持的字段：{', '.join(unknown_fields)}")
    if "trade_date" in normalized_extras:
        trade_date = parse_trade_date(normalized_extras["trade_date"])
    if "status" in normalized_extras:
        status = _normalize_status(normalized_extras["status"])
    else:
        status = "draft"
    result_status = _normalize_result_status(normalized_extras.get("result_status", ""))
    if "quantity" in normalized_extras:
        quantity = _parse_number(normalized_extras["quantity"], integer=True, field="数量")
        if quantity <= 0:
            raise ValueError("数量必须大于 0")
    if "price" in normalized_extras:
        price = _parse_number(normalized_extras["price"], field="价格")
        if price < 0:
            raise ValueError("价格不能小于 0")

    payload = {
        "symbol": symbol,
        "trade_date": trade_date.isoformat(),
        "action": action,
        "status": status,
        "result_status": result_status,
        "price": price,
        "quantity": quantity,
        "amount": _parse_number(normalized_extras["amount"], field="金额") if "amount" in normalized_extras else None,
        "thesis": normalized_extras.get("thesis", ""),
        "execution_note": normalized_extras.get("execution_note", ""),
        "review_note": normalized_extras.get("review_note", ""),
        "result_pct": _parse_number(normalized_extras["result_pct"], field="结果收益率") if "result_pct" in normalized_extras else None,
        "result_amount": _parse_number(normalized_extras["result_amount"], field="结果金额") if "result_amount" in normalized_extras else None,
        "tags": _normalize_tags(normalized_extras.get("tags", "")),
    }
    for field in ("strategy_id", "run_id", "signal_id"):
        if field in normalized_extras:
            payload[field] = int(_parse_number(normalized_extras[field], integer=True, field=field))
    return payload


def _operation_usage() -> str:
    return (
        "用法：录入操作 买入 600519.SH 2026-09-18 100 1688.00 "
        "| 理由=突破年线 | 状态=已执行 | 标签=观察仓,趋势"
    )


def _require_bound_user(parsed: dict) -> str:
    sender_id = str(parsed.get("sender_id") or "").strip()
    username = get_username_by_feishu(sender_id) if sender_id else None
    if not username:
        raise ValueError("当前飞书账号尚未绑定量化用户，请先在私聊中完成绑定")
    return username


def _operation_from_payload(payload: dict, *, username: str, parsed: dict) -> dict:
    operation = dict(payload)
    meta = dict(operation.get("meta") or {})
    meta.update(
        {
            "source": "feishu_im",
            "feishu_event_id": parsed.get("event_id") or "",
            "feishu_message_id": parsed.get("message_id") or "",
            "feishu_chat_id": parsed.get("chat_id") or "",
        }
    )
    operation["meta"] = meta
    operation["created_by"] = username
    return create_operation_record(**operation)


def _pending_payload(record: QuantImInboundEvent) -> dict:
    parsed = json.loads(record.parsed_payload_json or "{}")
    payload = parsed.get("operation_payload")
    return payload if isinstance(payload, dict) else {}


def _format_operation_confirmation(payload: dict, token: str) -> str:
    action = _ACTION_LABELS.get(payload.get("action"), payload.get("action"))
    lines = [
        "待确认操作：",
        f"标的：{payload.get('symbol')}",
        f"动作：{action}",
        f"交易日：{payload.get('trade_date')}",
        f"数量：{payload.get('quantity') if payload.get('quantity') is not None else '--'}",
        f"价格：{payload.get('price') if payload.get('price') is not None else '--'}",
        f"理由：{payload.get('thesis') or '--'}",
        "",
        f"回复“确认 {token}”写入，或回复“取消 {token}”。",
    ]
    return "\n".join(lines)


def _create_pending_operation(text: str, parsed: dict, event_record_id: int) -> tuple[str, str]:
    username = _require_bound_user(parsed)
    payload = _parse_operation_payload(text)
    payload["created_by"] = username
    record = QuantImInboundEvent.get_by_id(event_record_id)
    token = f"OP-{record.id}"
    stored = json.loads(record.parsed_payload_json or "{}")
    stored["operation_payload"] = payload
    stored["pending_token"] = token
    record.parsed_payload_json = json.dumps(stored, ensure_ascii=False)
    record.command = "operation_pending"
    record.status = "pending_confirmation"
    record.save()
    return "operation_pending", _format_operation_confirmation(payload, token)


def _load_pending(token_id: int, parsed: dict) -> tuple[QuantImInboundEvent, dict, str]:
    try:
        record = QuantImInboundEvent.get_by_id(token_id)
    except DoesNotExist as exc:
        raise ValueError("确认码不存在或已过期") from exc
    if record.status != "pending_confirmation":
        if record.status == "processed":
            payload = json.loads(record.response_payload_json or "{}")
            operation_id = payload.get("operation_id")
            if operation_id:
                return record, {}, f"该操作已确认，记录 ID：{operation_id}"
        raise ValueError("该确认码已处理或已失效")
    if record.sender_id != str(parsed.get("sender_id") or "") or record.chat_id != str(parsed.get("chat_id") or ""):
        raise ValueError("确认码不属于当前飞书账号或会话")
    if record.received_at and datetime.now() - record.received_at > timedelta(minutes=10):
        record.status = "expired"
        record.processed_at = datetime.now()
        record.save()
        raise ValueError("确认码已过期，请重新发起操作登记")
    username = _require_bound_user(parsed)
    payload = _pending_payload(record)
    if payload.get("created_by") != username:
        raise ValueError("确认码不属于当前绑定用户")
    return record, payload, ""


def _confirm_operation(token_id: int, parsed: dict) -> tuple[str, str]:
    pending, payload, existing_message = _load_pending(token_id, parsed)
    if existing_message:
        return "operation_confirmed", existing_message
    operation = _operation_from_payload(payload, username=payload["created_by"], parsed=parsed)
    pending.status = "processed"
    pending.command = "operation_confirmed"
    pending.response_payload_json = json.dumps({"operation_id": operation["id"]}, ensure_ascii=False)
    pending.processed_at = datetime.now()
    pending.save()
    return "operation_confirmed", f"✅ 操作已登记，记录 ID：{operation['id']}。操作登记不会自动改变持仓。"


def _cancel_operation(token_id: int, parsed: dict) -> tuple[str, str]:
    pending, _, existing_message = _load_pending(token_id, parsed)
    if existing_message:
        return "operation_cancelled", existing_message
    pending.status = "cancelled"
    pending.command = "operation_cancelled"
    pending.processed_at = datetime.now()
    pending.save()
    return "operation_cancelled", "已取消本次操作登记。"


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
        elif compact in ("昨天", "昨日"):
            target = date.today() - timedelta(days=1)
            query.update(date_from=target.isoformat(), date_to=target.isoformat())
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


def _detail_command(text: str, parsed: dict) -> tuple[str, str]:
    username = _require_bound_user(parsed)
    match = re.search(r"(\d+)\s*$", _clean_command(text))
    if not match:
        raise ValueError("用法：操作详情 记录ID")
    try:
        record = get_operation_record(int(match.group(1)), created_by=username)
    except DoesNotExist as exc:
        raise ValueError("操作记录不存在，或不属于当前绑定用户") from exc
    return "operation_detail", _format_history([record], {"limit": 1})


def handle_operation_command(text: str, parsed: dict, event_record_id: int) -> Optional[tuple[str, str]]:
    """处理操作登记相关命令；非操作命令返回 None。"""
    command_text = _clean_command(text)
    confirm_match = _CONFIRM_RE.match(command_text)
    if confirm_match:
        try:
            return _confirm_operation(int(confirm_match.group(1)), parsed)
        except ValueError as exc:
            return "operation_confirm_error", f"❌ {exc}"

    cancel_match = _CANCEL_RE.match(command_text)
    if cancel_match:
        try:
            return _cancel_operation(int(cancel_match.group(1)), parsed)
        except ValueError as exc:
            return "operation_cancel_error", f"❌ {exc}"

    if _starts_with(command_text, _OPERATION_PREFIXES):
        try:
            return _create_pending_operation(command_text, parsed, event_record_id)
        except ValueError as exc:
            return "operation_create_error", f"❌ {exc}\n{_operation_usage()}"

    if _starts_with(command_text, _HISTORY_PREFIXES):
        try:
            return _history_command(command_text, parsed)
        except ValueError as exc:
            return "operation_history_error", f"❌ {exc}"

    if _starts_with(command_text, _DETAIL_PREFIXES):
        try:
            return _detail_command(command_text, parsed)
        except ValueError as exc:
            return "operation_detail_error", f"❌ {exc}"
    return None
