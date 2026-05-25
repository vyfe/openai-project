from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, List, Optional

logger = logging.getLogger("quant.im.rules")


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


def get_message_rules() -> List[MessageRule]:
    """返回当前注册的所有消息规则（按 priority 升序）。"""
    return list(_message_rules)


# ---- 内置规则：当前时间回显（priority 极高，兜底） ----
@register_message_handler(r"^[时间|几点|现在几点].*", priority=15)
def _time_query_handler(text: str, parsed: dict) -> Optional[tuple[str, str]]:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return "time_query", f"⏰ 当前时间：{now}"


# ---- 飞书绑定命令 ----
@register_message_handler(r"^/bind\s+(\S+)\s+(\S+)", priority=5)
def _bind_command_handler(text: str, parsed: dict) -> Optional[tuple[str, str]]:
    """绑定飞书账户到慧聊用户: /bind {username} {password}"""
    import re as _re
    from service.quant.binding_service import bind_user
    m = _re.match(r"^/bind\s+(\S+)\s+(\S+)", text)
    if not m:
        return None
    username = m.group(1)
    password = m.group(2)
    sender_id = parsed.get("sender_id") or ""
    if not sender_id:
        return "bind_error", "❌ 无法获取你的飞书身份，请重试"
    try:
        bind_user(sender_id, username, password)
        return "bind_success", f"✅ 已绑定慧聊用户: {username}"
    except Exception as e:
        return "bind_error", f"❌ 绑定失败: {e}"


@register_message_handler(r"^/unbind", priority=5)
def _unbind_command_handler(text: str, parsed: dict) -> Optional[tuple[str, str]]:
    """解绑飞书账户"""
    from service.quant.binding_service import unbind_user, get_binding
    sender_id = parsed.get("sender_id") or ""
    if not sender_id:
        return "unbind_error", "❌ 无法获取你的飞书身份"
    binding = get_binding(sender_id)
    if not binding:
        return "unbind_info", "ℹ️ 你还没有绑定慧聊账户"
    username = binding.get("username", "")
    unbind_user(sender_id)
    return "unbind_success", f"✅ 已解绑慧聊用户: {username}"


@register_message_handler(r"^/whoami", priority=5)
def _whoami_command_handler(text: str, parsed: dict) -> Optional[tuple[str, str]]:
    """查询当前绑定状态"""
    from service.quant.binding_service import get_binding
    sender_id = parsed.get("sender_id") or ""
    if not sender_id:
        return "whoami_error", "❌ 无法获取你的飞书身份"
    binding = get_binding(sender_id)
    if binding:
        return "whoami", f"👤 已绑定慧聊用户: {binding['username']}\n绑定时间: {binding['bound_at']}"
    return "whoami", "👤 未绑定慧聊账户。发送 /bind {用户名} {密码} 进行绑定"
