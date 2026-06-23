import threading
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from openai import OpenAI

from conf.settings import settings


@dataclass
class RuntimeState:
    settings: Any
    server_start_time: float = field(default_factory=time.time)
    model_cache: dict = field(default_factory=dict)
    cache_expiry_time: dict = field(default_factory=dict)
    api_host_blacklist: dict = field(default_factory=dict)
    blacklist_lock: threading.Lock = field(default_factory=threading.Lock)
    stream_cancel_lock: threading.Lock = field(default_factory=threading.Lock)
    stream_cancel_registry: dict = field(default_factory=dict)
    model_meta_timer_lock: threading.Lock = field(default_factory=threading.Lock)
    model_meta_timer: Optional[threading.Timer] = None
    thread_local: threading.local = field(default_factory=threading.local)
    clients: list = field(default_factory=list)
    claude_clients: list = field(default_factory=list)
    allowed_extensions: set = field(default_factory=lambda: {"txt", "pdf", "png", "jpg", "jpeg", "gif", "ppt", "pptx", "md"})
    use_db_auth: bool = True
    blacklist_duration: int = 5 * 60
    user_credentials: dict = field(default_factory=dict)
    user_api_keys: dict = field(default_factory=dict)

    def build_clients(self):
        self.clients = [
            OpenAI(api_key=self.settings.default_api_key, base_url=host)
            for host in self.settings.api_hosts
            if host
        ]
        return self.clients

    def build_claude_clients(self):
        """构建 Claude (Anthropic SDK) 客户端列表。

        默认复用 [api] 段的 api_key 和 api_hosts（与 OpenAI 共享同一套凭证）。
        注意：Anthropic SDK 的 base_url 不需要 /v1 后缀（SDK 自行追加 /v1/messages），
        而 OpenAI SDK 需要。此处自动 strip 末尾的 /v1。
        """
        try:
            import anthropic
        except ImportError:
            self.claude_clients = []
            return self.claude_clients

        # 优先使用 [claude] 独立配置，否则回退到 [api] 共享配置
        claude_api_key = self.settings.claude_api_key or self.settings.default_api_key
        if not claude_api_key:
            self.claude_clients = []
            return self.claude_clients

        claude_hosts = self.settings.claude_api_hosts if self.settings.claude_api_hosts else self.settings.api_hosts
        if not claude_hosts:
            self.claude_clients = []
            return self.claude_clients

        self.claude_clients = [
            anthropic.Anthropic(api_key=claude_api_key, base_url=_strip_v1_suffix(host))
            for host in claude_hosts
            if host
        ]
        return self.claude_clients


def _strip_v1_suffix(url: str) -> str:
    """移除 URL 末尾的 /v1（或 /v1/），因为 Anthropic SDK 自行追加 /v1/messages。

    OpenAI SDK 需要 base_url 包含 /v1，但它附加的是 /chat/completions；
    Anthropic SDK 的 base_url 不应包含 /v1，它附加的是 /v1/messages。
    两套 SDK 的路径拼接策略不同，此处统一处理。
    """
    return url.rstrip("/").removesuffix("/v1")


runtime_state = RuntimeState(settings=settings)
