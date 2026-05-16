from __future__ import annotations

import base64
import hashlib
import json
import re
import time
import uuid
from datetime import datetime
from typing import Optional
from urllib.parse import quote

import requests
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
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


CHANNEL_FEISHU_APP = "feishu_app"
FEISHU_API_BASE = "https://open.feishu.cn/open-apis"
_FEISHU_TOKEN_CACHE = {"token": "", "expires_at": 0.0}


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


def _get_feishu_tenant_access_token() -> str:
    now = time.time()
    if _FEISHU_TOKEN_CACHE["token"] and now < float(_FEISHU_TOKEN_CACHE["expires_at"]) - 120:
        return str(_FEISHU_TOKEN_CACHE["token"])
    if not settings.quant_feishu_app_id or not settings.quant_feishu_app_secret:
        raise ValueError("缺少飞书应用 app_id/app_secret 配置")
    response = requests.post(
        f"{FEISHU_API_BASE}/auth/v3/tenant_access_token/internal",
        json={
            "app_id": settings.quant_feishu_app_id,
            "app_secret": settings.quant_feishu_app_secret,
        },
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()
    if int(data.get("code", -1)) != 0:
        raise ValueError(f"获取飞书 tenant_access_token 失败: {data}")
    token = str(data.get("tenant_access_token") or "").strip()
    if not token:
        raise ValueError(f"飞书 token 响应缺少 tenant_access_token: {data}")
    _FEISHU_TOKEN_CACHE["token"] = token
    _FEISHU_TOKEN_CACHE["expires_at"] = now + int(data.get("expire", 7200) or 7200)
    return token


def _feishu_headers() -> dict:
    return {
        "Authorization": f"Bearer {_get_feishu_tenant_access_token()}",
        "Content-Type": "application/json; charset=utf-8",
    }


def _feishu_content_text(content: str) -> str:
    return json.dumps({"text": _truncate_text(content)}, ensure_ascii=False)


def _send_feishu_text(channel: dict, content: str) -> dict:
    config = channel.get("config") or {}
    receive_id = str(config.get("receive_id") or "").strip()
    receive_id_type = str(config.get("receive_id_type") or "chat_id").strip()
    if not receive_id:
        raise ValueError("飞书通道缺少 receive_id")
    payload = {
        "receive_id": receive_id,
        "msg_type": "text",
        "content": _feishu_content_text(content),
        "uuid": str(uuid.uuid4()),
    }
    response = requests.post(
        f"{FEISHU_API_BASE}/im/v1/messages?receive_id_type={quote(receive_id_type)}",
        headers=_feishu_headers(),
        json=payload,
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()
    if int(data.get("code", -1)) != 0:
        raise ValueError(f"飞书消息发送失败: {data}")
    return {"message_type": "text", "request_payload": payload, "response_payload": data}


def _reply_feishu_text(message_id: str, content: str, reply_in_thread: bool = False) -> dict:
    if not message_id:
        raise ValueError("飞书回复缺少 message_id")
    payload = {
        "msg_type": "text",
        "content": _feishu_content_text(content),
        "reply_in_thread": bool(reply_in_thread),
        "uuid": str(uuid.uuid4()),
    }
    response = requests.post(
        f"{FEISHU_API_BASE}/im/v1/messages/{quote(message_id, safe='')}/reply",
        headers=_feishu_headers(),
        json=payload,
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()
    if int(data.get("code", -1)) != 0:
        raise ValueError(f"飞书消息回复失败: {data}")
    return {"message_type": "text", "request_payload": payload, "response_payload": data}


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


def _verify_feishu_signature(raw_body: bytes, headers) -> bool:
    encrypt_key = settings.quant_feishu_encrypt_key
    if not encrypt_key:
        return True
    timestamp = headers.get("X-Lark-Request-Timestamp") or headers.get("x-lark-request-timestamp") or ""
    nonce = headers.get("X-Lark-Request-Nonce") or headers.get("x-lark-request-nonce") or ""
    signature = headers.get("X-Lark-Signature") or headers.get("x-lark-signature") or ""
    if not timestamp or not nonce or not signature:
        return False
    expected = hashlib.sha256((timestamp + nonce + encrypt_key).encode("utf-8") + raw_body).hexdigest()
    return expected == signature


def _decrypt_feishu_payload(encrypted: str) -> dict:
    if not settings.quant_feishu_encrypt_key:
        raise ValueError("收到飞书加密事件，但未配置 feishu_encrypt_key")
    key = hashlib.sha256(settings.quant_feishu_encrypt_key.encode("utf-8")).digest()
    raw = base64.b64decode(encrypted)
    if len(raw) < 16:
        raise ValueError("飞书事件解密失败: 密文过短")
    iv = raw[:16]
    ciphertext = raw[16:]
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    padded = decryptor.update(ciphertext) + decryptor.finalize()
    padding = padded[-1]
    if padding < 1 or padding > 16:
        raise ValueError("飞书事件解密失败: padding 非法")
    text = padded[:-padding].decode("utf-8")
    return json.loads(text)


def _verify_feishu_token(payload: dict):
    expected = settings.quant_feishu_verification_token
    if not expected:
        return
    header = payload.get("header") or {}
    actual = header.get("token") or payload.get("token") or ""
    if actual != expected:
        raise ValueError("飞书事件 verification token 不匹配")


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


def _parse_feishu_message_event(payload: dict) -> dict:
    event = payload.get("event") or {}
    sender = event.get("sender") or {}
    sender_id = sender.get("sender_id") or {}
    message = event.get("message") or {}
    return {
        "event_id": (payload.get("header") or {}).get("event_id") or message.get("message_id") or uuid.uuid4().hex,
        "message_id": message.get("message_id") or "",
        "chat_id": message.get("chat_id") or "",
        "chat_type": message.get("chat_type") or "",
        "sender_id": sender_id.get("open_id") or sender_id.get("user_id") or sender_id.get("union_id") or "",
        "sender_type": sender.get("sender_type") or "",
        "message_type": message.get("message_type") or "",
        "mentions": message.get("mentions") or [],
        "text": _extract_feishu_text(message),
        "raw_event": event,
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
    return "unknown", f"暂未识别这条指令：{command_text}\n\n{_feishu_help_text()}"


def _should_process_feishu_message(parsed: dict) -> bool:
    if parsed.get("sender_type") == "bot":
        return False
    chat_type = str(parsed.get("chat_type") or "").lower()
    if chat_type in ("p2p", "private"):
        return True
    return bool(parsed.get("mentions"))


def handle_feishu_event_callback(raw_body: bytes, headers) -> tuple[dict, int]:
    if not raw_body:
        return {"code": 0, "msg": "empty"}, 200
    try:
        payload = json.loads(raw_body.decode("utf-8"))
        is_challenge = payload.get("type") == "url_verification" or bool(payload.get("challenge"))
        if is_challenge:
            if "encrypt" in payload:
                payload = _decrypt_feishu_payload(payload["encrypt"])
            _verify_feishu_token(payload)
            return {"challenge": payload.get("challenge", "")}, 200
        if not _verify_feishu_signature(raw_body, headers):
            return {"code": 401, "msg": "invalid feishu signature"}, 401
        if "encrypt" in payload:
            payload = _decrypt_feishu_payload(payload["encrypt"])
        _verify_feishu_token(payload)
        event_type = (payload.get("header") or {}).get("event_type") or payload.get("type") or ""
        if event_type != "im.message.receive_v1":
            return {"code": 0, "msg": "ignored event"}, 200
        parsed = _parse_feishu_message_event(payload)
        channel = _match_feishu_channel(parsed.get("chat_id", ""))
        channel_id = channel.id if channel else None
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
                raw_payload_json=json.dumps(payload, ensure_ascii=False),
                parsed_payload_json=json.dumps(parsed, ensure_ascii=False),
                received_at=datetime.now(),
            )
        except IntegrityError:
            return {"code": 0, "msg": "duplicate event"}, 200
        if not _should_process_feishu_message(parsed):
            event_record.status = "ignored"
            event_record.command = "ignored"
            event_record.processed_at = datetime.now()
            event_record.save()
            return {"code": 0, "msg": "ignored message"}, 200
        try:
            command, response_text = _route_feishu_command(parsed.get("text") or "", parsed)
            reply_in_thread = _to_bool(_json_loads(channel.config_json, {}).get("reply_in_thread"), False) if channel else False
            response_payload = _reply_feishu_text(parsed.get("message_id") or "", response_text, reply_in_thread=reply_in_thread)
            event_record.command = command
            event_record.status = "processed"
            event_record.response_payload_json = json.dumps(response_payload, ensure_ascii=False)
            event_record.processed_at = datetime.now()
            event_record.save()
        except Exception as exc:
            event_record.status = "failed"
            event_record.error_message = str(exc)
            event_record.processed_at = datetime.now()
            event_record.save()
        return {"code": 0, "msg": "ok"}, 200
    except Exception as exc:
        return {"code": 500, "msg": f"feishu event failed: {exc}"}, 500
