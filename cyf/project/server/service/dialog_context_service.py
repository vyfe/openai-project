import json
import ast
from copy import deepcopy
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


DialogMessage = Dict[str, Any]
RoleSetting = Dict[str, Any]


def current_time_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def parse_role_setting(raw_role_setting: Any) -> Optional[RoleSetting]:
    if raw_role_setting is None or raw_role_setting == "":
        return None
    if isinstance(raw_role_setting, dict):
        return deepcopy(raw_role_setting)
    if isinstance(raw_role_setting, str):
        try:
            parsed = json.loads(raw_role_setting)
            return parsed if isinstance(parsed, dict) else None
        except (TypeError, json.JSONDecodeError):
            try:
                parsed = ast.literal_eval(raw_role_setting)
                return parsed if isinstance(parsed, dict) else None
            except (ValueError, SyntaxError):
                return None
    return None


def parse_dialog_context(raw_context: Any) -> Tuple[List[DialogMessage], Optional[RoleSetting]]:
    if raw_context is None or raw_context == "":
        return [], None
    if isinstance(raw_context, str):
        parsed = json.loads(raw_context)
    else:
        parsed = raw_context
    if isinstance(parsed, list):
        return parsed, None
    if isinstance(parsed, dict):
        context = parsed.get("context", [])
        role_setting = parsed.get("role_setting")
        return context if isinstance(context, list) else [], role_setting if isinstance(role_setting, dict) else None
    return [], None


def stamp_dialog_messages(messages: List[DialogMessage], timestamp: Optional[str] = None) -> List[DialogMessage]:
    stamped_at = timestamp or current_time_str()
    stamped_messages = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        next_message = deepcopy(message)
        next_message.setdefault("time", stamped_at)
        stamped_messages.append(next_message)
    return stamped_messages


def preserve_dialog_messages(messages: List[DialogMessage]) -> List[DialogMessage]:
    return [deepcopy(message) for message in messages if isinstance(message, dict)]


def stamp_latest_user_message(messages: List[DialogMessage], timestamp: Optional[str] = None) -> List[DialogMessage]:
    next_messages = preserve_dialog_messages(messages)
    if not next_messages:
        return next_messages
    stamped_at = timestamp or current_time_str()
    for message in reversed(next_messages):
        if message.get("role") == "user":
            message.setdefault("time", stamped_at)
            break
    return next_messages


def build_dialog_context_payload(messages: List[DialogMessage], role_setting: Any = None) -> str:
    payload = {
        "context": preserve_dialog_messages(messages),
        "role_setting": parse_role_setting(role_setting),
    }
    return json.dumps(payload, ensure_ascii=False)
