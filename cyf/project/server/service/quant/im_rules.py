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
