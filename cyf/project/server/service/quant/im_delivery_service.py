from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from typing import Optional

from conf.settings import settings
from lark_oapi import Client, LogLevel
from lark_oapi.api.im.v1 import CreateMessageRequest, CreateMessageRequestBody, CreateMessageResponse, ReplyMessageRequest, ReplyMessageRequestBody, ReplyMessageResponse
from lark_oapi.event.dispatcher_handler import EventDispatcherHandler
from quant.entities import QuantImInboundEvent, QuantReportDelivery, QuantReportRecord
from service.quant.im_channel_service import load_channel
from service.quant.im_helpers import truncate_text
from service.quant.position_service import list_position_summary


logger = logging.getLogger("quant.im")
_FEISHU_CLIENT: Optional[Client] = None
_FEISHU_EVENT_HANDLER: Optional[EventDispatcherHandler] = None


def get_feishu_client() -> Optional[Client]:
    global _FEISHU_CLIENT
    if _FEISHU_CLIENT is not None:
        return _FEISHU_CLIENT
    app_id = (settings.quant_feishu_app_id or "").strip()
    app_secret = (settings.quant_feishu_app_secret or "").strip()
    if not app_id or not app_secret:
        return None
    _FEISHU_CLIENT = Client.builder().app_id(app_id).app_secret(app_secret).log_level(LogLevel.WARNING).build()
    return _FEISHU_CLIENT


def require_feishu_client() -> Client:
    client = get_feishu_client()
    if client is None:
        raise ValueError("缺少飞书应用 app_id/app_secret 配置")
    return client


def feishu_content_text(content: str) -> str:
    return json.dumps({"text": truncate_text(content)}, ensure_ascii=False)


def send_feishu_text(channel: dict, content: str) -> dict:
    config = channel.get("config") or {}
    receive_id = str(config.get("receive_id") or "").strip()
    receive_id_type = str(config.get("receive_id_type") or "chat_id").strip()
    if not receive_id:
        raise ValueError("飞书通道缺少 receive_id")
    msg_uuid = str(uuid.uuid4())
    request_payload = {
        "receive_id": receive_id,
        "receive_id_type": receive_id_type,
        "msg_type": "text",
        "content": feishu_content_text(content),
        "uuid": msg_uuid,
    }
    client = require_feishu_client()
    req = (
        CreateMessageRequest.builder()
        .receive_id_type(receive_id_type)
        .request_body(
            CreateMessageRequestBody.builder()
            .receive_id(receive_id)
            .msg_type("text")
            .content(feishu_content_text(content))
            .uuid(msg_uuid)
            .build()
        )
        .build()
    )
    resp: CreateMessageResponse = client.im.v1.message.create(req)
    if resp.code != 0:
        raise ValueError(f"飞书消息发送失败: code={resp.code}, msg={resp.msg}")
    return {
        "message_type": "text",
        "request_payload": request_payload,
        "response_payload": {"code": resp.code, "msg": resp.msg, "message_id": resp.data.message_id if resp.data else None},
    }


def reply_feishu_text(message_id: str, content: str, reply_in_thread: bool = False) -> dict:
    if not message_id:
        raise ValueError("飞书回复缺少 message_id")
    msg_uuid = str(uuid.uuid4())
    request_payload = {
        "message_id": message_id,
        "msg_type": "text",
        "content": feishu_content_text(content),
        "reply_in_thread": bool(reply_in_thread),
        "uuid": msg_uuid,
    }
    client = require_feishu_client()
    req = (
        ReplyMessageRequest.builder()
        .message_id(message_id)
        .request_body(
            ReplyMessageRequestBody.builder()
            .msg_type("text")
            .content(feishu_content_text(content))
            .reply_in_thread(bool(reply_in_thread))
            .uuid(msg_uuid)
            .build()
        )
        .build()
    )
    resp: ReplyMessageResponse = client.im.v1.message.reply(req)
    if resp.code != 0:
        raise ValueError(f"飞书消息回复失败: code={resp.code}, msg={resp.msg}")
    return {
        "message_type": "text",
        "request_payload": request_payload,
        "response_payload": {"code": resp.code, "msg": resp.msg, "message_id": resp.data.message_id if resp.data else None},
    }


def list_delivery_records(report_id: Optional[int] = None, channel_id: Optional[int] = None, status: Optional[str] = None, limit: int = 100) -> list[dict]:
    query = QuantReportDelivery.select().order_by(QuantReportDelivery.id.desc())
    if report_id:
        query = query.where(QuantReportDelivery.report_id == report_id)
    if channel_id:
        query = query.where(QuantReportDelivery.channel_id == channel_id)
    if status:
        query = query.where(QuantReportDelivery.status == status)
    query = query.limit(limit)
    return [item.to_dict() for item in query.iterator()]


def list_inbound_events(channel_id: Optional[int] = None, status: Optional[str] = None, limit: int = 100) -> list[dict]:
    query = QuantImInboundEvent.select().order_by(QuantImInboundEvent.id.desc())
    if channel_id:
        query = query.where(QuantImInboundEvent.channel_id == channel_id)
    if status:
        query = query.where(QuantImInboundEvent.status == status)
    return [item.to_dict() for item in query.limit(limit).iterator()]


def create_delivery_record(*, report_id=None, run_id=None, channel_id=None, channel_type="feishu_app", channel_target="", message_type="markdown", status="success", request_payload=None, response_payload=None, error_message="", sent_at=None) -> dict:
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


def send_channel_content(channel: dict, content: str) -> dict:
    return send_feishu_text(channel, content)


def render_position_summary_markdown(strategy_id: Optional[int] = None, created_by: str = "") -> str:
    summary = list_position_summary(strategy_id=strategy_id, created_by=created_by or None)
    title = f"策略 #{strategy_id} 持仓快照" if strategy_id else "持仓快照"
    lines = [
        f"# {title}",
        "",
        f"- 生成时间: `{datetime.now().isoformat(timespec='seconds')}`",
        f"- 当前持仓标的数: `{len(summary)}`",
        "",
        "## 持仓概览",
    ]
    if not summary:
        lines.append("- 当前没有净持仓。")
        return "\n".join(lines)
    for item in summary[:12]:
        pnl_text = "--" if item.get("unrealized_pnl_pct") is None else f"{round(float(item['unrealized_pnl_pct']) * 100, 2)}%"
        lines.append(f"- {item['symbol']} 持仓 `{item['net_quantity']}` 股，成本 `{item.get('avg_cost')}`，现价 `{item.get('latest_price')}`，浮盈 `{pnl_text}`")
    return "\n".join(lines)


def send_report_to_channel(report_id: int, *, channel_id: Optional[int] = None) -> dict:
    report = QuantReportRecord.get_by_id(report_id).to_dict()
    channel = load_channel(channel_id=channel_id)
    try:
        result = send_channel_content(channel, report["final_markdown"])
        return create_delivery_record(
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
        return create_delivery_record(
            report_id=report["id"],
            run_id=report.get("run_id"),
            channel_id=channel["channel_id"],
            channel_type=channel["channel_type"],
            channel_target=channel["channel_target"],
            status="failed",
            error_message=str(exc),
            sent_at=datetime.now(),
        )


def send_position_summary_to_channel(*, channel_id: Optional[int] = None, strategy_id: Optional[int] = None) -> dict:
    channel = load_channel(channel_id=channel_id)
    content = render_position_summary_markdown(strategy_id=strategy_id)
    try:
        result = send_channel_content(channel, content)
        return create_delivery_record(
            channel_id=channel["channel_id"],
            channel_type=channel["channel_type"],
            channel_target=channel["channel_target"],
            message_type=result["message_type"],
            request_payload=result["request_payload"],
            response_payload=result["response_payload"],
            sent_at=datetime.now(),
        )
    except Exception as exc:
        return create_delivery_record(
            channel_id=channel["channel_id"],
            channel_type=channel["channel_type"],
            channel_target=channel["channel_target"],
            status="failed",
            error_message=str(exc),
            sent_at=datetime.now(),
        )


def send_test_message(*, content: str, channel_id: Optional[int] = None) -> dict:
    channel = load_channel(channel_id=channel_id)
    result = send_channel_content(channel, f"# 量化 IM 测试\n\n{str(content or '测试消息').strip()}")
    return {
        "channel_id": channel["channel_id"],
        "channel_target": channel["channel_target"],
        "request_payload": result["request_payload"],
        "response_payload": result["response_payload"],
    }
