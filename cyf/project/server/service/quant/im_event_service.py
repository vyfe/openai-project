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

from quant.entities import QuantImChannel, QuantImInboundEvent, QuantReportRecord
from service.auth_service import require_auth
from service.quant.binding_service import get_username_by_feishu, is_feishu_bound
from service.quant.im_channel_service import list_im_channels
from service.quant.im_delivery_service import reply_feishu_text as _reply_feishu_text, render_position_summary_markdown
from service.quant.im_helpers import CHANNEL_FEISHU_APP, json_loads as _json_loads, to_bool as _to_bool, truncate_text as _truncate_text
from service.quant.im_operation_service import handle_operation_command
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


_P2P_VIRTUAL_CHANNEL_NAME_PREFIX = "p2p:"
_P2P_BIND_CMD_RE = re.compile(r"^/(?:bind|unbind|whoami)\b", re.IGNORECASE)


def _ensure_p2p_virtual_channel(chat_id: str, sender_id: str) -> Optional[dict]:
    """为首次私聊的用户自动注册虚拟通道。

    规则：
    - name 用 `p2p:{chat_id}` 作为唯一键，重复调用幂等
    - config.inbound_chat_id 写入 chat_id（用于 _match_feishu_channel 反向匹配）
    - config.receive_id / receive_id_type 用 sender_id / open_id，确保推送回到发起人
    - config.is_p2p_virtual=True 作为标记，前端可隐藏
    - 若同一 chat_id 已被注册过，复用并更新 updated_at
    """
    if not chat_id or not sender_id:
        return None
    name = f"{_P2P_VIRTUAL_CHANNEL_NAME_PREFIX}{chat_id}"
    try:
        record = QuantImChannel.get_or_none(QuantImChannel.name == name)
        if record is not None:
            # 命中已存在：返回它的 dict（上层继续用）
            logger.debug("[p2p-channel] 命中已注册虚拟通道 | name=%s | id=%d", name, record.id)
            return record.to_dict()
        config = {
            "inbound_chat_id": chat_id,
            "receive_id": sender_id,
            "receive_id_type": "open_id",
            "is_p2p_virtual": True,
        }
        record = QuantImChannel.create(
            name=name,
            channel_type=CHANNEL_FEISHU_APP,
            status="active",
            config_json=json.dumps(config, ensure_ascii=False),
            mention_list_json="[]",
            description=f"私聊自动注册 @ {datetime.now().isoformat()}",
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        logger.info("[p2p-channel] 自动注册虚拟通道 | id=%d | name=%s | sender=%s", record.id, name, sender_id[:8])
        return record.to_dict()
    except IntegrityError:
        # 极端并发：name 唯一约束撞上
        logger.warning("[p2p-channel] 并发创建虚拟通道被唯一约束拦截，重读 | name=%s", name)
        record = QuantImChannel.get_or_none(QuantImChannel.name == name)
        return record.to_dict() if record else None
    except Exception as exc:
        logger.exception("[p2p-channel] 自动注册虚拟通道失败 | name=%s | error=%s", name, exc)
        return None


def _p2p_bind_guide_text() -> str:
    """私聊未绑定用户的 bind 引导文案。"""
    return (
        "👋 欢迎使用量化助手！\n\n"
        "您还未绑定慧聊账号，请先绑定：\n\n"
        "  /bind {用户名} {密码}\n\n"
        "示例：/bind admin mypassword123\n\n"
        "绑定后回复「帮助」可查看完整命令列表。"
    )


def _resolve_p2p_access(parsed: dict) -> tuple[Optional[dict], str]:
    """私聊消息访问决策。

    返回 (channel, reason)：
    - channel 为 dict（虚拟通道）+ reason in ("bind_cmd", "bound_user") → 放行
    - channel 为 None + reason == "unbound_guide" → 不放行，调用方应回引导文案
    - channel 为 None + reason == "no_chat_id" → 异常兜底（无 chat_id 也无法回信）

    /bind 系列命令（/bind /unbind /whoami）无论是否绑定一律放行，否则用户首次无入口。
    """
    text = (parsed.get("text") or "").strip()
    sender_id = str(parsed.get("sender_id") or "").strip()
    chat_id = str(parsed.get("chat_id") or "").strip()

    if not chat_id:
        return None, "no_chat_id"

    is_bind_cmd = bool(_P2P_BIND_CMD_RE.match(text))

    if is_bind_cmd:
        channel = _ensure_p2p_virtual_channel(chat_id, sender_id)
        return channel, "bind_cmd"

    if is_feishu_bound(sender_id):
        channel = _ensure_p2p_virtual_channel(chat_id, sender_id)
        return channel, "bound_user"

    return None, "unbound_guide"


_HELP_HINT_INSTRUMENT = (
    "提示：股票识别支持「代码」(如 600519、002837、600519.SH) 或「股票名」(如 贵州茅台)，"
    "前提是已在「数据中心」加入股票池；不在池中会报错并拒绝。"
)


def _feishu_help_text() -> str:
    return "\n".join(
        [
            "═══════════════════════════════",
            "量化助手 · 命令一览",
            "═══════════════════════════════",
            "通用规则：",
            "  · 分隔符「,」「，」「空格」任选，可混合",
            "  · 股票可填代码或名称（须先加入股票池）",
            "",
            "【基础命令】",
            "1. 帮助 — 查看本说明",
            "2. 持仓 — 返回当前持仓快照",
            "3. 报告 — 返回最近一份量化报告",
            "",
            "【登记交易】直接入库，无需二次确认",
            "4. 买,股票,数量,价格,备注",
            "   示例：买,贵州茅台,100,1688,突破年线",
            "5. 卖,股票,数量,价格,备注",
            "   示例：卖,002837,200,12,止损",
            "",
            "【已执行】动作前缀加「已」= 状态自动为「已执行」",
            "   已买/已卖/已加仓/已减仓/已观察",
            "   示例：已买,贵州茅台,100,1688,突破年线  ≡ 买,贵州茅台,100,1688,突破年线,已执行",
            "",
            "【自定义交易日】在「价格」前加 8 位日期 YYYYMMDD",
            "6. 买,股票,日期,数量,价格,备注",
            "   示例：买,002837,20260920,200,12,补仓",
            "   日期不是今天时，自动写入操作记录（QuantOperationRecord），",
            "   便于「操作历史」查询。",
            "",
            "【可选字段】在「备注」之后追加，依次识别：",
            "  状态：草稿/已执行/已结束/已取消（默认草稿）",
            "  标签：用 / 或 , 分隔多个，如 趋势仓/观察仓",
            "  完整示例：买,002837,200,12,20260920,补仓,已执行,趋势仓/观察仓",
            "  注：显式指定的状态会覆盖「已X」自动标记",
            "      如：已买,X,100,10,备注,已结束 → status=已结束（不是已执行）",
            "",
            "【查询】",
            "7. 操作历史 [过滤] — 按过滤条件查本人操作记录",
            "   过滤：今天 / 近7天 / YYYYMMDD / 股票代码 / 状态 / 动作",
            "   示例：操作历史 近7天 002837",
            "",
            "【账号绑定】（仅私聊）",
            "8. /bind {用户名} {密码} — 绑定飞书账号到慧聊用户",
            "   /unbind — 解绑    /whoami — 查询当前绑定",
            "",
            _HELP_HINT_INSTRUMENT,
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
    # 统一分隔符：英文逗号、中文逗号、空白字符（混合也兼容）
    tokens = [item for item in re.split(r"[,，\s]+", str(text or "").strip()) if item]
    if len(tokens) < 3:
        return None
    side_map = {
        "买": "buy",
        "买入": "buy",
        "buy": "buy",
        "b": "buy",
        "加仓": "add",
        "减仓": "reduce",
        "卖": "sell",
        "卖出": "sell",
        "sell": "sell",
        "s": "sell",
    }
    side = side_map.get(tokens[0].lower())
    if not side:
        return None
    # 股票池校验（精确匹配 symbol/code/name/custom_name）
    try:
        from service.quant.im_operation_service import _resolve_symbol_in_pool
        instrument = _resolve_symbol_in_pool(tokens[1])
    except ValueError:
        raise
    symbol = instrument["symbol"]
    quantity = _parse_number_token(tokens[2], as_int=True)
    if not quantity or quantity <= 0:
        raise ValueError(
            "数量必须大于 0，例如：买,002837,200,12,突破年线"
        )
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


def _route_feishu_command(text: str, parsed: dict, event_record_id: int) -> tuple[str, str]:
    command_text = str(text or "").strip()
    if not command_text:
        return "help", _feishu_help_text()
    for rule in _message_rules:
        if rule.pattern.search(command_text):
            result = rule.handler(command_text, parsed)
            if result is not None:
                logger.debug("[rule-engine] 命中规则 | name=%s | text=%s", rule.name, command_text[:60])
                return result
    operation_result = handle_operation_command(command_text, parsed, event_record_id)
    if operation_result is not None:
        return operation_result
    compact = command_text.lower().replace(" ", "")
    if compact in ("help", "帮助", "菜单", "说明"):
        return "help", _feishu_help_text()
    if compact in ("持仓", "持仓摘要", "仓位", "position", "positions"):
        created_by = get_username_by_feishu(parsed.get("sender_id", "") or "") or ""
        if not created_by:
            return "auth_error", "请先在私聊中完成飞书账号绑定，再查询持仓。"
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

    # ---- 私聊准入决策：未绑定用户 → 引导 bind；已绑定或 /bind 系列命令 → 放行 ----
    chat_type = str(parsed.get("chat_type") or "").lower()
    is_private = chat_type in ("p2p", "private")
    channel: Optional[dict] = None
    p2p_reason = ""
    if is_private:
        channel, p2p_reason = _resolve_p2p_access(parsed)
        if p2p_reason == "bind_cmd":
            logger.info("[feishu-event] 私聊 /bind 系列命令，放行 | sender=%s", parsed.get("sender_id", "")[:8])
        elif p2p_reason == "bound_user":
            logger.info("[feishu-event] 私聊已绑定用户，放行 | sender=%s", parsed.get("sender_id", "")[:8])
        elif p2p_reason == "unbound_guide":
            logger.info("[feishu-event] 私聊未绑定用户，引导 bind | sender=%s", parsed.get("sender_id", "")[:8])
        elif p2p_reason == "no_chat_id":
            logger.warning("[feishu-event] 私聊消息缺少 chat_id，无法回信 | sender=%s", parsed.get("sender_id", "")[:8])
    else:
        channel = _match_feishu_channel(parsed.get("chat_id", ""))
        if channel:
            logger.info("[feishu-event] 匹配到通道 | channel_id=%d | name=%s", channel.get("id"), channel.get("name"))
        else:
            logger.info("[feishu-event] 未匹配到任何活跃通道 | chat_id=%s", parsed.get("chat_id"))

    channel_id = channel.get("id") if channel else None
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

    # ---- 私聊未绑定：回 bind 引导并落档 ----
    if is_private and p2p_reason == "unbound_guide":
        guide_text = _p2p_bind_guide_text()
        try:
            response_payload = _reply_feishu_text(
                parsed.get("message_id") or "", guide_text, reply_in_thread=False
            )
            event_record.command = "p2p_unbound_guide"
            event_record.status = "processed"
            event_record.response_payload_json = json.dumps(response_payload, ensure_ascii=False)
            event_record.processed_at = datetime.now()
            event_record.save()
            logger.info("[feishu-event] 已回私聊 bind 引导 | message_id=%s", parsed.get("message_id"))
        except Exception as exc:
            logger.exception("[feishu-event] 回私聊 bind 引导失败 | error=%s", exc)
            event_record.status = "failed"
            event_record.error_message = str(exc)
            event_record.processed_at = datetime.now()
            event_record.save()
        return

    if not channel:
        logger.info("[feishu-event] 未匹配到活跃通道，忽略消息 | chat_id=%s", parsed.get("chat_id"))
        event_record.status = "ignored"
        event_record.command = "unmatched_channel"
        event_record.processed_at = datetime.now()
        event_record.save()
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
        command, response_text = _route_feishu_command(parsed.get("text") or "", parsed, event_record.id)
        logger.info("[feishu-event] 命令路由 | command=%s | response_len=%d", command, len(response_text))
        reply_in_thread = _to_bool(_json_loads(channel.get("config", {}) if channel else {}, {}).get("reply_in_thread"), False) if channel else False
        response_payload = _reply_feishu_text(parsed.get("message_id") or "", response_text, reply_in_thread=reply_in_thread)
        event_record.command = command
        event_record.status = "pending_confirmation" if command == "operation_pending" else "processed"
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
