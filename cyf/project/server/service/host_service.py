import random
import threading
import time

from openai import OpenAI

from conf.runtime import runtime_state
from model.repositories.user_repository import get_user_api_key


def is_host_blacklisted(url_index: int) -> bool:
    with runtime_state.blacklist_lock:
        if url_index in runtime_state.api_host_blacklist:
            if time.time() < runtime_state.api_host_blacklist[url_index]:
                return True
            del runtime_state.api_host_blacklist[url_index]
        return False


def blacklist_host(url_index: int, logger=None):
    with runtime_state.blacklist_lock:
        runtime_state.api_host_blacklist[url_index] = time.time() + runtime_state.blacklist_duration
        if logger:
            logger.warning(f"API Host {runtime_state.settings.api_hosts[url_index]} 被拉黑 5 分钟")


def get_available_host_indices() -> list:
    return [i for i in range(len(runtime_state.settings.api_hosts)) if not is_host_blacklisted(i)]


def cleanup_expired_blacklist():
    with runtime_state.blacklist_lock:
        current_time = time.time()
        expired = [idx for idx, end_time in runtime_state.api_host_blacklist.items() if current_time >= end_time]
        for idx in expired:
            del runtime_state.api_host_blacklist[idx]


def blacklist_cleanup_worker():
    while True:
        time.sleep(60)
        cleanup_expired_blacklist()


def start_blacklist_cleanup_thread():
    thread = threading.Thread(target=blacklist_cleanup_worker, daemon=True)
    thread.start()
    return thread


def get_current_url_index():
    return getattr(runtime_state.thread_local, "url_index", None)


def set_current_url_index(index: int):
    runtime_state.thread_local.url_index = index


def ensure_clients():
    if not runtime_state.clients:
        runtime_state.build_clients()
    return runtime_state.clients


def random_client() -> tuple:
    clients = ensure_clients()
    available_indices = get_available_host_indices()
    if not available_indices:
        url_index = random.randint(0, len(clients) - 1)
        return clients[url_index], url_index
    selected_index = random.choice(available_indices)
    set_current_url_index(selected_index)
    return clients[selected_index], selected_index


def get_client_for_url_index(url_index: int, api_key: str = None) -> OpenAI:
    if api_key:
        return OpenAI(api_key=api_key, base_url=runtime_state.settings.api_hosts[url_index])
    return ensure_clients()[url_index]


def get_client_for_user(username: str) -> tuple:
    api_key = get_user_api_key(username) if runtime_state.use_db_auth else runtime_state.user_api_keys.get(username)
    available_indices = get_available_host_indices()
    if not available_indices:
        url_index = random.randint(0, len(runtime_state.settings.api_hosts) - 1)
    else:
        url_index = random.choice(available_indices)
    set_current_url_index(url_index)
    if api_key:
        return OpenAI(api_key=api_key, base_url=runtime_state.settings.api_hosts[url_index]), url_index
    return ensure_clients()[url_index], url_index


# =============================================================================
# Claude 模型支持
# =============================================================================


def get_model_grp_from_cache(model_name: str) -> str:
    """从运行时缓存获取模型的 model_grp。默认返回空字符串。"""
    try:
        models = runtime_state.model_cache.get("models")
        if not models:
            return ""
        model_name_lower = model_name.lower()
        for m in models:
            if str(m.get("id", "")).lower() == model_name_lower:
                return str(m.get("model_grp", "") or "").strip()
        return ""
    except Exception:
        return ""


def is_claude_model(model_name: str) -> bool:
    """判断模型是否属于 Claude 分组（model_grp == 'claude'）。"""
    return get_model_grp_from_cache(model_name) == "claude"


def ensure_claude_clients():
    if not runtime_state.claude_clients:
        runtime_state.build_claude_clients()
    return runtime_state.claude_clients


def get_claude_client_for_user(username: str) -> tuple:
    """获取 Claude 客户端。返回 (client, url_index)。

    与 OpenAI 路径一致：随机选取可用 host，支持多 host 轮询。
    """
    if not runtime_state.claude_clients:
        runtime_state.build_claude_clients()
    if not runtime_state.claude_clients:
        raise RuntimeError(
            "Claude SDK 未配置（请确保 conf.ini 的 [api] 段已配置 api_key + api_host，"
            "或在 [claude] 段配置独立凭证）"
        )
    available_indices = get_available_host_indices()
    if not available_indices:
        url_index = random.randint(0, len(runtime_state.claude_clients) - 1)
    else:
        url_index = random.choice(available_indices)
    return runtime_state.claude_clients[url_index], url_index
