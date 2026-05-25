from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime
from typing import Optional

from conf.settings import settings
from lark_oapi import Client, LogLevel
from lark_oapi.api.im.v1 import ReplyMessageRequest, ReplyMessageRequestBody, ReplyMessageResponse
from lark_oapi.api.im.v1.model.p2_im_message_receive_v1 import P2ImMessageReceiveV1
from lark_oapi.core.const import UTF_8
from lark_oapi.core.model import RawRequest, RawResponse
from lark_oapi.event.dispatcher_handler import EventDispatcherHandler
from peewee import IntegrityError

from quant.entities import QuantImInboundEvent, QuantReportRecord
from service.auth_service import require_auth
from service.quant.binding_service import get_username_by_feishu
from service.quant.im_channel_service import list_im_channels
from service.quant.im_delivery_service import reply_feishu_text as _reply_feishu_text, render_position_summary_markdown
from service.quant.im_helpers import CHANNEL_FEISHU_APP, json_loads as _json_loads, to_bool as _to_bool, truncate_text as _truncate_text
from service.quant.im_rules import _message_rules, register_message_handler  # noqa: F401
from service.quant.position_service import create_position_entry

logger = logging.getLogger("quant.im")
_FEISHU_EVENT_HANDLER: Optional[EventDispatcherHandler] = None


def get_feishu_event_handler() -> Optional[EventDispatcherHandler]:
    global _FEISHU_EVENT_HANDLER
    if _FEISHU_EVENT_HANDLER is not None:
        return _FEISHU_EVENT_HANDLER
    encrypt_key = (settings.quant_feishu_encrypt_key or "").strip()
    verification_token = (settings.quant_feishu_verification_token or "").strip()
    builder = EventDispatcherHandler.builder(encrypt_key, verification_token)
    builder.register_p2_im_message_receive_v1(_on_im_message_receive)
    _FEISHU_EVENT_HANDLER = builder.build()
    logger.info(
        "[feishu-handler] 初始化 EventDispatcherHandler | encrypt_key=%s | verification_token=%s",
        "已配置" if encrypt_key else "未配置",
        "已配置" if verification_token else "未配置",
    )
    return _FEISHU_EVENT_HANDLER


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
    if not mentions:
        return []
    result = []
    for m in mentions:
        uid = m.id
        result.append(
            {
                "key": m.key,
                "id": {"open_id": uid.open_id, "user_id": uid.user_id, "union_id": uid.union_id} if uid else None,
                "name": m.name,
                "tenant_key": m.tenant_key,
            }
        )
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


def _match_feishu_channel(chat_id: str):
    channels = list_im_channels(status="active", channel_type=CHANNEL_FEISHU_APP)
    for channel in channels:
        config = channel.get("config") or {}
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
    symbol = tokens[1]
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
    for rule in _message_rules:
        if rule.pattern.search(command_text):
            result = rule.handler(command_text, parsed)
            if result is not None:
                logger.debug("[rule-engine] 命中规则 | name=%s | text=%s", rule.name, command_text[:60])
                return result
    compact = command_text.lower().replace(" ", "")
    if compact in ("help", "帮助", "菜单", "说明"):
        return "help", _feishu_help_text()
    if compact in ("持仓", "持仓摘要", "仓位", "position", "positions"):
        created_by = get_username_by_feishu(parsed.get("sender_id", "") or "") or ""
        return "position_summary", render_position_summary_markdown(created_by=created_by)
    if compact in ("报告", "最新报告", "日报", "report", "latestreport"):
        return "latest_report", _latest_report_text()
    entry = _try_create_position_from_command(command_text, parsed.get("sender_id") or "")
    if entry:
        price_text = "--" if entry.get("price") is None else entry.get("price")
        return (
            "position_entry",
            f"已登记持仓流水：{entry['side']} {entry['symbol']} {entry['quantity']} 股，价格 {price_text}。\n记录 ID: {entry['id']}",
        )
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return "time_echo", f"⏰ 当前时间：{now}"


def _should_process_feishu_message(parsed: dict) -> bool:
    if parsed.get("sender_type") == "bot":
        return False
    debug_suffix = (settings.quant_feishu_debug_suffix or "").strip()
    if debug_suffix:
        text = str(parsed.get("text") or "")
        expected_tag = f"[{debug_suffix}]"
        if expected_tag not in text:
            logger.debug("[feishu-filter] 消息不含 debug suffix=%s，丢弃 | text=%s", expected_tag, text[:80])
            return False
        logger.debug("[feishu-filter] debug suffix 匹配成功 | suffix=%s", expected_tag)
    chat_type = str(parsed.get("chat_type") or "").lower()
    if chat_type in ("p2p", "private"):
        return True
    return bool(parsed.get("mentions"))


def _on_im_message_receive(data: P2ImMessageReceiveV1) -> None:
    logger.info("[feishu-event] 收到 im.message.receive_v1")
    parsed = _parse_feishu_event_from_sdk(data)
    logger.debug(
        "[feishu-event] 解析结果 | chat_id=%s | message_id=%s | sender_id=%s | chat_type=%s | text_preview=%s",
        parsed.get("chat_id"),
        parsed.get("message_id"),
        parsed.get("sender_id"),
        parsed.get("chat_type"),
        (parsed.get("text") or "")[:80],
    )
    channel = _match_feishu_channel(parsed.get("chat_id", ""))
    channel_id = channel.get("id") if channel else None
    if channel:
        logger.info("[feishu-event] 匹配到通道 | channel_id=%d | name=%s", channel.get("id"), channel.get("name"))
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
            parsed.get("chat_type"),
            bool(parsed.get("mentions")),
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
        reply_in_thread = _to_bool(_json_loads(channel.get("config", {}) if channel else {}, {}).get("reply_in_thread"), False) if channel else False
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
    important_headers = {
        k: v
        for k, v in headers.items()
        if k.lower() in ("content-type", "x-lark-request-timestamp", "x-lark-request-nonce", "x-lark-signature", "user-agent")
    }
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
