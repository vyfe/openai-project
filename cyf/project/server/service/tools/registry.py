"""工具定义、权限校验和执行入口。"""

from __future__ import annotations

import json
from typing import Any, Dict, Iterable, List

from conf.runtime import runtime_state
from service.tools.google_web_search import (
    GoogleWebSearchError,
    claude_tool_definition,
    execute as execute_google_web_search,
    serialize_result,
    tool_definition,
)

TOOL_WEB_SEARCH = "web_search"
SUPPORTED_TOOLS = {TOOL_WEB_SEARCH}


class ToolConfigurationError(ValueError):
    """工具请求不合法或未完成服务端配置。"""


def normalize_enabled_tools(raw_tools: Any) -> List[str]:
    if raw_tools is None or raw_tools == "":
        return []
    if isinstance(raw_tools, str):
        try:
            raw_tools = json.loads(raw_tools)
        except json.JSONDecodeError:
            raw_tools = [raw_tools]
    if not isinstance(raw_tools, (list, tuple, set)):
        return []
    result = []
    for item in raw_tools:
        name = str(item or "").strip().lower()
        if name and name not in result:
            result.append(name)
    return result


def _model_allows_network(model: str) -> bool:
    models = runtime_state.model_cache.get("models") or []
    for item in models:
        if not isinstance(item, dict):
            continue
        if str(item.get("id", "")).strip().lower() == str(model).strip().lower():
            return item.get("allow_net") is not False
    return True


def validate_enabled_tools(raw_tools: Any, model: str) -> List[str]:
    tools = normalize_enabled_tools(raw_tools)
    unsupported = [name for name in tools if name not in SUPPORTED_TOOLS]
    if unsupported:
        raise ToolConfigurationError(f"不支持的工具: {', '.join(unsupported)}")
    if TOOL_WEB_SEARCH in tools:
        if not _model_allows_network(model):
            raise ToolConfigurationError("当前模型未开启联网能力")
        if not bool(getattr(runtime_state.settings, "google_web_search_enabled", False)):
            raise ToolConfigurationError("服务端未启用网络搜索")
    return tools


def get_tool_definitions(tool_names: Iterable[str], provider: str = "openai") -> List[Dict[str, Any]]:
    names = set(normalize_enabled_tools(list(tool_names)))
    if TOOL_WEB_SEARCH not in names:
        return []
    return [claude_tool_definition() if provider == "claude" else tool_definition()]


def execute_tool(name: str, arguments: Dict[str, Any], logger=None) -> Dict[str, Any]:
    if name != TOOL_WEB_SEARCH:
        raise ToolConfigurationError(f"不支持的工具: {name}")
    try:
        result = execute_google_web_search(arguments, logger=logger)
    except GoogleWebSearchError:
        raise
    return {"name": name, "text": result.get("text", ""), "sources": result.get("sources", [])}


def serialize_tool_result(result: Dict[str, Any]) -> str:
    return serialize_result({"text": result.get("text", ""), "sources": result.get("sources", [])})
