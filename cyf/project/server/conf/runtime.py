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


runtime_state = RuntimeState(settings=settings)
