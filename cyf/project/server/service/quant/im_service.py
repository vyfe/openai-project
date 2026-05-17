from __future__ import annotations

import logging
import json
import re
import time
import uuid
from datetime import datetime
from dataclasses import dataclass, field
from typing import Callable, List, Optional

from peewee import IntegrityError

from conf.settings import settings
from quant.entities import (
    QuantImChannel,
    QuantImInboundEvent,
    QuantPositionJournal,
    QuantReportDelivery,
    QuantReportRecord,
)
from service.quant.common import normalize_symbol
from service.quant.position_service import create_position_entry, list_position_summary

logger = logging.getLogger("quant.im")


# ---- 正则消息规则注册表 ----
@dataclass
class MessageRule:
    """正则匹配规则，priority 越小越优先"""
    pattern: "re.Pattern"
    handler: Callable[[str, dict], Optional[tuple[str, str]]]
    priority: int
    name: str


_message_rules: List[MessageRule] = []


def register_message_handler(pattern: str, priority: int = 50):
    """装饰器：注册一个基于正则的消息处理器。priority 越小优先级越高。"""
    def decorator(func: Callable[[str, dict], Optional[tuple[str, str]]]):
        _message_rules.append(MessageRule(
            pattern=re.compile(pattern),
            handler=func,
            priority=priority,
            name=func.__name__,
        ))
        _message_rules.sort(key=lambda r: r.priority)
        logger.info("[rule-registry] 注册消息规则 | name=%s | pattern=%s | priority=%d", func.__name__, pattern, priority)
        return func
    return decorator


from lark_oapi import Client, LogLevel
from lark_oapi.core.model import Config
from lark_oapi.api.im.v1 import (
    CreateMessageRequest,
    CreateMessageRequestBody,
    CreateMessageResponse,
    ReplyMessageRequest,
    ReplyMessageRequestBody,
    ReplyMessageResponse,
)
from lark_oapi.api.im.v1.model.p2_im_message_receive_v1 import P2ImMessageReceiveV1
from lark_oapi.core.const import UTF_8
from lark_oapi.core.model import RawRequest, RawResponse
from lark_oapi.event.dispatcher_handler import EventDispatcherHandler

CHANNEL_FEISHU_APP = "feishu_app"

_FEISHU_CLIENT: Optional[Client] = None
_FEISHU_EVENT_HANDLER: Optional[EventDispatcherHandler] = None

def _get_feishu_client() -> Optional[Client]:
    global _FEISHU_CLIENT
    if _FEISHU_CLIENT is not None:
        return _FEISHU_CLIENT
    app_id = (settings.quant_feishu_app_id or "").strip()
    app_secret = (settings.quant_feishu_app_secret or "").strip()
    if not app_id or not app_secret:
        return None
    logger.info("[feishu-client] 初始化飞书 SDK Client | app_id=%s***", app_id[:8] if len(app_id) > 8 else "***")
    _FEISHU_CLIENT = (
        Client.builder()
        .app_id(app_id)
        .app_secret(app_secret)
        .log_level(LogLevel.WARNING)
        .build()
    )
    return _FEISHU_CLIENT

def get_feishu_event_handler() -> Optional[EventDispatcherHandler]:
    global _FEISHU_EVENT_HANDLER
    if _FEISHU_EVENT_HANDLER is not None:
        return _FEISHU_EVENT_HANDLER
    encrypt_key = (settings.quant_feishu_encrypt_key or "").strip()
    verification_token = (settings.quant_feishu_verification_token or "").strip()
    builder = EventDispatcherHandler.builder(encrypt_key, verification_token)
    builder.register_p2_im_message_receive_v1(_on_im_message_receive)
    _FEISHU_EVENT_HANDLER = builder.build()
    logger.info("[feishu-handler] 初始化 EventDispatcherHandler | encrypt_key=%s | verification_token=%s",
                "已配置" if encrypt_key else "未配置",
                "已配置" if verification_token else "未配置")
    return _FEISHU_EVENT_HANDLER

def _require_feishu_client() -> Client:
    client = _get_feishu_client()
    if client is None:
        raise ValueError("缺少飞书应用 app_id/app_secret 配置")
    return client

def _json_loads(value, default):
    if value in (None, ""):
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(str(value))
    except Exception:
        return default

def _normalize_mentions(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value or "").strip()
    if not text:
        return []
    if text.startswith("["):
        parsed = _json_loads(text, [])
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]
    return [item.strip() for item in text.split(",") if item.strip()]

def _to_bool(value, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value in (None, ""):
        return default
    return str(value).strip().lower() in ("1", "true", "yes", "on")

def _truncate_text(content: str, limit: int = 9000) -> str:
    text = str(content or "").strip()
    if len(text) <= limit:
        return text
    return f"{text[:limit - 24]}\n\n内容过长，已截断展示。"

def _truncate_markdown(content: str, limit: int = 3800) -> str:
    text = str(content or "").strip()
    if len(text) <= limit:
        return text
    return f"{text[:limit - 24]}\n\n> 内容过长，已截断展示。"

def _mask_secret(text: str, keep: int = 6) -> str:
    value = str(text or "")
    if len(value) <= keep * 2:
        return value
    return f"{value[:keep]}...{value[-keep:]}"

def _mask_feishu_target(config: dict) -> str:
    receive_id_type = str(config.get("receive_id_type") or "chat_id")
    receive_id = str(config.get("receive_id") or "")
    return f"feishu:{receive_id_type}:{_mask_secret(receive_id)}" if receive_id else "feishu:app"

def _normalize_channel_type(value: str) -> str:
    channel_type = str(value or CHANNEL_FEISHU_APP).strip() or CHANNEL_FEISHU_APP
    if channel_type != CHANNEL_FEISHU_APP:
        raise ValueError(f"不支持的 IM 通道类型: {channel_type}")
    return channel_type

def _normalize_feishu_config(config) -> dict:
    payload = _json_loads(config, {}) or {}
    receive_id = str(
        payload.get("receive_id")
        or payload.get("chat_id")
        or payload.get("open_id")
        or payload.get("user_id")
        or ""
    ).strip()
    receive_id_type = str(payload.get("receive_id_type") or "").strip()
    if not receive_id_type:
        if receive_id.startswith("oc_"):
            receive_id_type = "chat_id"
        elif receive_id.startswith("ou_"):
            receive_id_type = "open_id"
        else:
            receive_id_type = "chat_id"
    if receive_id_type not in ("chat_id", "open_id", "user_id", "union_id", "email"):
        raise ValueError("飞书 receive_id_type 仅支持 chat_id/open_id/user_id/union_id/email")
    return {
        "receive_id": receive_id,
        "receive_id_type": receive_id_type,
        "reply_in_thread": _to_bool(payload.get("reply_in_thread"), default=False),
        "inbound_chat_id": str(
            payload.get("inbound_chat_id")
            or (receive_id if receive_id_type == "chat_id" else "")
        ).strip(),
    }

def _normalize_channel_config(channel_type: str, config=None) -> dict:
    if channel_type == CHANNEL_FEISHU_APP:
        normalized = _normalize_feishu_config(config)
        if not normalized.get("receive_id"):
            raise ValueError("飞书通道需要配置 receive_id")
        return normalized
    raise ValueError(f"不支持的 IM 通道类型: {channel_type}")

def list_im_channels(status: Optional[str] = None, channel_type: Optional[str] = None) -> list[dict]:
    query = QuantImChannel.select().order_by(QuantImChannel.id.desc())
    if status:
        query = query.where(QuantImChannel.status == status)
    if channel_type:
        query = query.where(QuantImChannel.channel_type == channel_type)
    return [item.to_dict() for item in query.iterator()]

def get_im_channel(channel_id: int) -> dict:
    return QuantImChannel.get_by_id(channel_id).to_dict()

def create_im_channel(
    *,
    name: str,
    channel_type: str = CHANNEL_FEISHU_APP,
    status: str = "active",
    mention_list=None,
    description: str = "",
    config=None,
) -> dict:
    if not str(name or "").strip():
        raise ValueError("name 不能为空")
    final_channel_type = _normalize_channel_type(channel_type)
    final_config = _normalize_channel_config(final_channel_type, config=config)
    record = QuantImChannel.create(
        name=str(name or "").strip(),
        channel_type=final_channel_type,
        status=str(status or "active").strip() or "active",
        config_json=json.dumps(final_config, ensure_ascii=False),
        mention_list_json=json.dumps(_normalize_mentions(mention_list), ensure_ascii=False),
        description=str(description or "").strip(),
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    return record.to_dict()

def update_im_channel(channel_id: int, **updates) -> dict:
    record = QuantImChannel.get_by_id(channel_id)
    next_channel_type = _normalize_channel_type(updates.get("channel_type", record.channel_type))
    next_config = _json_loads(updates.get("config", record.config_json), {}) if "config" in updates else _json_loads(record.config_json, {})
    if "name" in updates:
        record.name = str(updates["name"] or "").strip()
    if "channel_type" in updates:
        record.channel_type = next_channel_type
    if "config" in updates or "channel_type" in updates:
        record.config_json = json.dumps(_normalize_channel_config(next_channel_type, config=next_config), ensure_ascii=False)
    if "status" in updates:
        record.status = str(updates["status"] or "active").strip() or "active"
    if "mention_list" in updates:
        record.mention_list_json = json.dumps(_normalize_mentions(updates["mention_list"]), ensure_ascii=False)
    if "description" in updates:
        record.description = str(updates["description"] or "").strip()
    record.updated_at = datetime.now()
    record.save()
    return record.to_dict()

def delete_im_channel(channel_id: int) -> bool:
    record = QuantImChannel.get_by_id(channel_id)
    record.delete_instance()
    return True

def list_delivery_records(
    report_id: Optional[int] = None,
    channel_id: Optional[int] = None,
    status: Optional[str] = None,
    limit: int = 100,
) -> list[dict]:
    query = QuantReportDelivery.select().order_by(QuantReportDelivery.id.desc())
    if report_id:
        query = query.where(QuantReportDelivery.report_id == report_id)
    if channel_id:
        query = query.where(QuantReportDelivery.channel_id == channel_id)
    if status:
        query = query.where(QuantReportDelivery.status == status)
    query = query.limit(limit)
    return [item.to_dict() for item in query.iterator()]

def list_inbound_events(
    channel_id: Optional[int] = None,
    status: Optional[str] = None,
    limit: int = 100,
) -> list[dict]:
    query = QuantImInboundEvent.select().order_by(QuantImInboundEvent.id.desc())
    if channel_id:
        query = query.where(QuantImInboundEvent.channel_id == channel_id)
    if status:
        query = query.where(QuantImInboundEvent.status == status)
    return [item.to_dict() for item in query.limit(limit).iterator()]

def _load_channel(channel_id: Optional[int] = None) -> dict:
    if not channel_id:
        raise ValueError("飞书通道需要指定 channel_id")
    channel = QuantImChannel.get_by_id(channel_id).to_dict()
    if channel["status"] != "active":
        raise ValueError("当前 IM 通道未启用")
    config = channel.get("config") or {}
    if channel["channel_type"] != CHANNEL_FEISHU_APP:
        raise ValueError("当前版本仅支持飞书通道")
    return {
        "channel_id": channel["id"],
        "channel_type": channel["channel_type"],
        "config": config,
        "mention_list": channel.get("mention_list", []),
        "channel_target": _mask_feishu_target(config),
    }

def _feishu_content_text(content: str) -> str:
    return json.dumps({"text": _truncate_text(content)}, ensure_ascii=False)

def _send_feishu_text(channel: dict, content: str) -> dict:
    config = channel.get("config") or {}
    receive_id = str(config.get("receive_id") or "").strip()
    receive_id_type = str(config.get("receive_id_type") or "chat_id").strip()
    if not receive_id:
        raise ValueError("飞书通道缺少 receive_id")
    logger.info("[feishu-send] 发送消息 | receive_id=%s | receive_id_type=%s | content_len=%d", receive_id, receive_id_type, len(content))
    msg_uuid = str(uuid.uuid4())
    request_payload = {
        "receive_id": receive_id,
        "receive_id_type": receive_id_type,
        "msg_type": "text",
        "content": _feishu_content_text(content),
        "uuid": msg_uuid,
    }
    client = _require_feishu_client()
    req = (
        CreateMessageRequest.builder()
        .receive_id_type(receive_id_type)
        .request_body(
            CreateMessageRequestBody.builder()
            .receive_id(receive_id)
            .msg_type("text")
            .content(_feishu_content_text(content))
            .uuid(msg_uuid)
            .build()
        )
        .build()
    )
    resp: CreateMessageResponse = client.im.v1.message.create(req)
    if resp.code != 0:
        raise ValueError(f"飞书消息发送失败: code={resp.code}, msg={resp.msg}")
    response_payload = {
        "code": resp.code,
        "msg": resp.msg,
        "message_id": resp.data.message_id if resp.data else None,
    }
    return {"message_type": "text", "request_payload": request_payload, "response_payload": response_payload}

def _reply_feishu_text(message_id: str, content: str, reply_in_thread: bool = False) -> dict:
    if not message_id:
        raise ValueError("飞书回复缺少 message_id")
    logger.info("[feishu-reply] 回复消息 | message_id=%s | reply_in_thread=%s | content_len=%d", message_id, reply_in_thread, len(content))
    msg_uuid = str(uuid.uuid4())
    request_payload = {
        "message_id": message_id,
        "msg_type": "text",
        "content": _feishu_content_text(content),
        "reply_in_thread": bool(reply_in_thread),
        "uuid": msg_uuid,
    }
    client = _require_feishu_client()
    req = (
        ReplyMessageRequest.builder()
        .message_id(message_id)
        .request_body(
            ReplyMessageRequestBody.builder()
            .msg_type("text")
            .content(_feishu_content_text(content))
            .reply_in_thread(bool(reply_in_thread))
            .uuid(msg_uuid)
            .build()
        )
        .build()
    )
    resp: ReplyMessageResponse = client.im.v1.message.reply(req)
    if resp.code != 0:
        raise ValueError(f"飞书消息回复失败: code={resp.code}, msg={resp.msg}")
    response_payload = {
        "code": resp.code,
        "msg": resp.msg,
        "message_id": resp.data.message_id if resp.data else None,
    }
    return {"message_type": "text", "request_payload": request_payload, "response_payload": response_payload}

def _send_channel_content(channel: dict, content: str) -> dict:
    return _send_feishu_text(channel, content)

def _create_delivery_record(
    *,
    report_id=None,
    run_id=None,
    channel_id=None,
    channel_type=CHANNEL_FEISHU_APP,
    channel_target="",
    message_type="markdown",
    status="success",
    request_payload=None,
    response_payload=None,
    error_message="",
    sent_at=None,
) -> dict:
    record = QuantReportDelivery.create(
        report_id=report_id,
        run_id=run_id,
        channel_id=channel_id,
        channel_type=channel_type,
        channel_target=channel_target,
        message_type=message_type,
        status=status,
        request_payload_json=json.dumps(request_payload or {}, ensure_ascii=False),
        response_payload_json=json.dumps(response_payload or {}, ensure_ascii=False),
        error_message=str(error_message or "").strip(),
        sent_at=sent_at,
        created_at=datetime.now(),
    )
    return record.to_dict()

def send_report_to_channel(
    report_id: int,
    *,
    channel_id: Optional[int] = None,
) -> dict:
    report = QuantReportRecord.get_by_id(report_id).to_dict()
    channel = _load_channel(channel_id=channel_id)
    content = report["final_markdown"]
    try:
        result = _send_channel_content(channel, content)
        return _create_delivery_record(
            report_id=report["id"],
            run_id=report.get("run_id"),
            channel_id=channel["channel_id"],
            channel_type=channel["channel_type"],
            channel_target=channel["channel_target"],
            message_type=result["message_type"],
            request_payload=result["request_payload"],
            response_payload=result["response_payload"],
            sent_at=datetime.now(),
        )
    except Exception as exc:
        return _create_delivery_record(
            report_id=report["id"],
            run_id=report.get("run_id"),
            channel_id=channel["channel_id"],
            channel_type=channel["channel_type"],
            channel_target=channel["channel_target"],
            status="failed",
            error_message=str(exc),
            sent_at=datetime.now(),
        )

def render_position_summary_markdown(strategy_id: Optional[int] = None) -> str:
    summary = list_position_summary(strategy_id=strategy_id)
    journal_count = QuantPositionJournal.select().count() if strategy_id is None else (
        QuantPositionJournal.select().where(QuantPositionJournal.strategy_id == strategy_id).count()
    )
    title = "持仓快照"
    if strategy_id:
        title = f"策略 #{strategy_id} 持仓快照"
    lines = [
        f"# {title}",
        "",
        f"- 生成时间: `{datetime.now().isoformat(timespec='seconds')}`",
        f"- 当前持仓标的数: `{len(summary)}`",
        f"- 累计持仓流水: `{journal_count}`",
        "",
        "## 持仓概览",
    ]
    if not summary:
        lines.append("- 当前没有净持仓。")
        return "\n".join(lines)
    for item in summary[:12]:
        pnl_text = "--" if item.get("unrealized_pnl_pct") is None else f"{round(float(item['unrealized_pnl_pct']) * 100, 2)}%"
        lines.append(
            f"- {item['symbol']} 持仓 `{item['net_quantity']}` 股，成本 `{item.get('avg_cost')}`，现价 `{item.get('latest_price')}`，浮盈 `{pnl_text}`"
        )
    return "\n".join(lines)

def send_position_summary_to_channel(
    *,
    channel_id: Optional[int] = None,
    strategy_id: Optional[int] = None,
) -> dict:
    channel = _load_channel(channel_id=channel_id)
    content = render_position_summary_markdown(strategy_id=strategy_id)
    try:
        result = _send_channel_content(channel, content)
        return _create_delivery_record(
            report_id=None,
            run_id=None,
            channel_id=channel["channel_id"],
            channel_type=channel["channel_type"],
            channel_target=channel["channel_target"],
            message_type=result["message_type"],
            request_payload=result["request_payload"],
            response_payload=result["response_payload"],
            sent_at=datetime.now(),
        )
    except Exception as exc:
        return _create_delivery_record(
            report_id=None,
            run_id=None,
            channel_id=channel["channel_id"],
            channel_type=channel["channel_type"],
            channel_target=channel["channel_target"],
            status="failed",
            error_message=str(exc),
            sent_at=datetime.now(),
        )

def send_test_message(
    *,
    content: str,
    channel_id: Optional[int] = None,
) -> dict:
    channel = _load_channel(channel_id=channel_id)
    body = f"# 量化 IM 测试\n\n{str(content or '测试消息').strip()}"
    result = _send_channel_content(channel, body)
    return {
        "channel_id": channel["channel_id"],
        "channel_target": channel["channel_target"],
        "request_payload": result["request_payload"],
        "response_payload": result["response_payload"],
    }

def available_im_channel_options() -> list[dict]:
    return [
        {"id": item["id"], "name": item["name"], "channel_type": item["channel_type"], "status": item["status"]}
        for item in list_im_channels(status="active")
    ]

def _extract_feishu_text(message: dict) -> str:
    content = _json_loads(message.get("content"), {})
    msg_type = str(message.get("message_type") or "").strip()
    text = ""
    if msg_type == "text":
        text = str(content.get("text") or "")
    elif msg_type == "post":
        title = str((content.get("title") or content.get("zh_cn", {}).get("title") or "")).strip()
        fragments = []
        blocks = content.get("content") or content.get("zh_cn", {}).get("content") or []
        for row in blocks:
            for item in row if isinstance(row, list) else []:
                if isinstance(item, dict):
                    fragments.append(str(item.get("text") or item.get("name") or ""))
        text = "\n".join([title, "".join(fragments)]).strip()
    text = re.sub(r"<at[^>]*>.*?</at>", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"^@\S+\s*", "", text).strip()
    return text

def _normalize_feishu_mentions(mentions) -> list[dict]:
    """将 SDK 的 MentionEvent 对象列表转为 JSON 可序列化的纯 dict 列表。"""
    if not mentions:
        return []
    result = []
    for m in mentions:
        uid = m.id
        result.append({
            "key": m.key,
            "id": {"open_id": uid.open_id, "user_id": uid.user_id, "union_id": uid.union_id} if uid else None,
            "name": m.name,
            "tenant_key": m.tenant_key,
        })
    return result


def _parse_feishu_event_from_sdk(data: P2ImMessageReceiveV1) -> dict:
    event = data.event
    message = event.message if event else None
    sender = event.sender if event else None
    sender_id_obj = sender.sender_id if sender else None
    sender_id = ""
    if sender_id_obj:
        sender_id = sender_id_obj.open_id or sender_id_obj.user_id or sender_id_obj.union_id or ""
    message_dict = {
        "message_id": message.message_id,
        "chat_id": message.chat_id,
        "chat_type": message.chat_type,
        "message_type": message.message_type,
        "content": message.content,
        "mentions": message.mentions,
    } if message else {}
    return {
        "event_id": (data.header.event_id if data.header else None) or (message.message_id if message else None) or uuid.uuid4().hex,
        "message_id": message.message_id if message else "",
        "chat_id": message.chat_id if message else "",
        "chat_type": message.chat_type if message else "",
        "sender_id": sender_id,
        "sender_type": sender.sender_type if sender else "",
        "message_type": message.message_type if message else "",
        "mentions": _normalize_feishu_mentions(message.mentions) if message else [],
        "text": _extract_feishu_text(message_dict) if message else "",
        "raw_event": {},
    }

def _match_feishu_channel(chat_id: str) -> Optional[QuantImChannel]:
    channels = QuantImChannel.select().where(
        (QuantImChannel.channel_type == CHANNEL_FEISHU_APP) & (QuantImChannel.status == "active")
    )
    for channel in channels.iterator():
        config = _json_loads(channel.config_json, {}) or {}
        if chat_id and chat_id in (config.get("inbound_chat_id"), config.get("receive_id")):
            return channel
    return None

def _feishu_help_text() -> str:
    return "\n".join(
        [
            "量化助手可用命令：",
            "1. 帮助：查看命令。",
            "2. 持仓 / 持仓摘要：返回当前持仓快照。",
            "3. 最新报告 / 报告：返回最近一份量化报告。",
            "4. 买入 600519 100 1688 备注：登记一条买入持仓流水。",
            "5. 卖出 600519 100 1688 备注：登记一条卖出持仓流水。",
        ]
    )

def _latest_report_text() -> str:
    report = QuantReportRecord.select().order_by(QuantReportRecord.id.desc()).first()
    if not report:
        return "当前还没有可发送的量化报告。"
    return _truncate_text(report.final_markdown, limit=9000)

def _parse_number_token(token: str, *, as_int: bool = False):
    text = re.sub(r"[^0-9.\-]", "", str(token or ""))
    if not text:
        return None
    return int(float(text)) if as_int else float(text)

def _try_create_position_from_command(text: str, sender_id: str) -> Optional[dict]:
    normalized = re.sub(r"[，,]+", " ", str(text or "")).strip()
    tokens = [item for item in re.split(r"\s+", normalized) if item]
    if len(tokens) < 3:
        return None
    side_map = {
        "买": "buy",
        "买入": "buy",
        "buy": "buy",
        "b": "buy",
        "卖": "sell",
        "卖出": "sell",
        "sell": "sell",
        "s": "sell",
    }
    side = side_map.get(tokens[0].lower())
    if not side:
        return None
    symbol = normalize_symbol(tokens[1])
    quantity = _parse_number_token(tokens[2], as_int=True)
    if not quantity or quantity <= 0:
        raise ValueError("数量必须大于 0，例如：买入 600519 100 1688")
    price = _parse_number_token(tokens[3]) if len(tokens) >= 4 else None
    remark = " ".join(tokens[4:]) if len(tokens) >= 5 else ""
    entry = create_position_entry(
        symbol=symbol,
        side=side,
        quantity=quantity,
        price=price,
        occurred_at=datetime.now(),
        source="feishu_im",
        reason="飞书对话录入",
        remark=remark,
        created_by=f"feishu:{sender_id}",
    )
    return entry

def _route_feishu_command(text: str, parsed: dict) -> tuple[str, str]:
    command_text = str(text or "").strip()
    if not command_text:
        return "help", _feishu_help_text()

    # 1. 正则规则引擎（可扩展，按 priority 排序，越小越优先）
    for rule in _message_rules:
        if rule.pattern.search(command_text):
            result = rule.handler(command_text, parsed)
            if result is not None:
                logger.debug("[rule-engine] 命中规则 | name=%s | text=%s", rule.name, command_text[:60])
                return result

    # 2. 硬编码命令（向后兼容）
    compact = command_text.lower().replace(" ", "")
    if compact in ("help", "帮助", "菜单", "说明"):
        return "help", _feishu_help_text()
    if compact in ("持仓", "持仓摘要", "仓位", "position", "positions"):
        return "position_summary", render_position_summary_markdown()
    if compact in ("报告", "最新报告", "日报", "report", "latestreport"):
        return "latest_report", _latest_report_text()
    entry = _try_create_position_from_command(command_text, parsed.get("sender_id") or "")
    if entry:
        price_text = "--" if entry.get("price") is None else entry.get("price")
        return (
            "position_entry",
            f"已登记持仓流水：{entry['side']} {entry['symbol']} {entry['quantity']} 股，价格 {price_text}。\n记录 ID: {entry['id']}",
        )

    # 3. 兜底：回显当前时间
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return "time_echo", f"⏰ 当前时间：{now}"


# ---- 内置规则：当前时间回显（priority 极高，兜底） ----
@register_message_handler(r"^[时间|几点|现在几点].*", priority=15)
def _time_query_handler(text: str, parsed: dict) -> Optional[tuple[str, str]]:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return "time_query", f"⏰ 当前时间：{now}"


def _should_process_feishu_message(parsed: dict) -> bool:
    if parsed.get("sender_type") == "bot":
        return False
    chat_type = str(parsed.get("chat_type") or "").lower()
    if chat_type in ("p2p", "private"):
        return True
    return bool(parsed.get("mentions"))

def _on_im_message_receive(data: P2ImMessageReceiveV1) -> None:
    logger.info("[feishu-event] 收到 im.message.receive_v1")
    parsed = _parse_feishu_event_from_sdk(data)
    logger.debug(
        "[feishu-event] 解析结果 | chat_id=%s | message_id=%s | sender_id=%s | chat_type=%s | text_preview=%s",
        parsed.get("chat_id"), parsed.get("message_id"), parsed.get("sender_id"),
        parsed.get("chat_type"), (parsed.get("text") or "")[:80],
    )
    channel = _match_feishu_channel(parsed.get("chat_id", ""))
    channel_id = channel.id if channel else None
    if channel:
        logger.info("[feishu-event] 匹配到通道 | channel_id=%d | name=%s", channel.id, channel.name)
    else:
        logger.info("[feishu-event] 未匹配到任何活跃通道 | chat_id=%s", parsed.get("chat_id"))
    try:
        event_record = QuantImInboundEvent.create(
            event_id=parsed["event_id"],
            channel_id=channel_id,
            channel_type=CHANNEL_FEISHU_APP,
            message_id=parsed.get("message_id") or "",
            chat_id=parsed.get("chat_id") or "",
            sender_id=parsed.get("sender_id") or "",
            sender_type=parsed.get("sender_type") or "",
            message_type=parsed.get("message_type") or "",
            raw_payload_json=json.dumps({}, ensure_ascii=False),
            parsed_payload_json=json.dumps(parsed, ensure_ascii=False),
            received_at=datetime.now(),
        )
    except IntegrityError:
        logger.info("[feishu-event] 重复事件，跳过 | event_id=%s", parsed.get("event_id"))
        return
    if not _should_process_feishu_message(parsed):
        logger.info(
            "[feishu-event] 消息被忽略 | chat_type=%s | has_mentions=%s",
            parsed.get("chat_type"), bool(parsed.get("mentions"))
        )
        event_record.status = "ignored"
        event_record.command = "ignored"
        event_record.processed_at = datetime.now()
        event_record.save()
        return
    logger.info("[feishu-event] 开始处理 | command_text=%s", (parsed.get("text") or "")[:100])
    try:
        command, response_text = _route_feishu_command(parsed.get("text") or "", parsed)
        logger.info("[feishu-event] 命令路由 | command=%s | response_len=%d", command, len(response_text))
        reply_in_thread = _to_bool(_json_loads(channel.config_json, {}).get("reply_in_thread"), False) if channel else False
        response_payload = _reply_feishu_text(parsed.get("message_id") or "", response_text, reply_in_thread=reply_in_thread)
        event_record.command = command
        event_record.status = "processed"
        event_record.response_payload_json = json.dumps(response_payload, ensure_ascii=False)
        event_record.processed_at = datetime.now()
        event_record.save()
    except Exception as exc:
        logger.exception("[feishu-event] 处理失败 | error=%s", exc)
        event_record.status = "failed"
        event_record.error_message = str(exc)
        event_record.processed_at = datetime.now()
        event_record.save()

def handle_feishu_event_callback(raw_body: bytes, headers) -> tuple[dict, int]:
    if not raw_body:
        logger.info("[feishu-callback] 收到空请求体")
        return {"code": 0, "msg": "empty"}, 200
    handler = get_feishu_event_handler()
    if handler is None:
        logger.error("[feishu-callback] EventDispatcherHandler 未初始化（缺少飞书配置）")
        return {"code": 503, "msg": "feishu not configured"}, 503
    important_headers = {k: v for k, v in headers.items()
                         if k.lower() in ("content-type", "x-lark-request-timestamp",
                                          "x-lark-request-nonce", "x-lark-signature", "user-agent")}
    logger.info("[feishu-callback] 收到请求 | body_len=%d | headers=%s", len(raw_body), important_headers)
    try:
        raw_req = RawRequest()
        raw_req.uri = "/never_guess_my_usage/quant/im/feishu/events"
        raw_req.body = raw_body
        raw_req.headers = {k.lower(): v for k, v in headers.items()}
        logger.debug("[feishu-callback] 转发到 SDK EventDispatcherHandler...")
        raw_resp: RawResponse = handler.do(raw_req)
        status_code = raw_resp.status_code or 200
        if raw_resp.content:
            body = json.loads(raw_resp.content.decode(UTF_8))
            logger.info("[feishu-callback] SDK 返回 | status=%d | body=%s", status_code, body)
            return body, status_code
        logger.info("[feishu-callback] SDK 返回 | status=%d (无 content)", status_code)
        return {"code": 0, "msg": "ok"}, status_code
    except Exception as exc:
        logger.exception("[feishu-callback] 处理失败 | error=%s", exc)
        return {"code": 500, "msg": f"feishu event failed: {exc}"}, 500
