"""东财反限流补丁 — NID 令牌注入 + User-Agent 轮换。

用法：
    from quant_client.eastmoney_patch import EastmoneySession
    session = EastmoneySession()
    
    # 获取请求头和 cookie
    headers, cookie = session.get_headers()
    
    # 使用示例：
    req = urllib.request.Request(url, headers=headers)
    req.add_header("Cookie", cookie)
    with urllib.request.urlopen(req) as resp: ...

环境变量：
    ENABLE_EASTMONEY_PATCH=true  启用补丁（默认启用）
"""

from __future__ import annotations

import http.cookiejar
import os
import random
import time
import urllib.request
from typing import Optional

# ── User-Agent 池（主流桌面浏览器） ──
_USER_AGENTS = [
    # Chrome 135 macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    # Chrome 135 Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    # Edge 135 macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36 Edg/135.0.0.0",
    # Edge 135 Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36 Edg/135.0.0.0",
    # Firefox 137 macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:137.0) Gecko/20100101 Firefox/137.0",
    # Firefox 137 Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:137.0) Gecko/20100101 Firefox/137.0",
    # Safari 18 macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.3 Safari/605.1.15",
]

_NID_ACQUIRE_URL = "https://www.eastmoney.com/"
_NID_COOKIE_NAME = "NID"
_NID_CACHE_SECONDS = 600


class EastmoneySession:
    """管理东财 NID cookie 和 UA 轮换的会话。"""

    def __init__(self):
        self._nid_value: Optional[str] = None
        self._nid_fetched_at: float = 0.0
        self._enabled = os.environ.get("ENABLE_EASTMONEY_PATCH", "true").lower() in ("true", "1", "yes")

    @property
    def enabled(self) -> bool:
        return self._enabled

    def get_headers(self) -> tuple[dict[str, str], str]:
        """返回 (headers_dict, cookie_string)"""
        ua = random.choice(_USER_AGENTS)
        headers = {
            "User-Agent": ua,
            "Accept": "application/json,text/plain,*/*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Referer": "https://quote.eastmoney.com/",
            "Origin": "https://quote.eastmoney.com",
        }
        cookie = ""
        if self._enabled:
            cookie = self._get_cookie_string()
        return headers, cookie

    def _get_cookie_string(self) -> str:
        nid = self._ensure_nid()
        if nid:
            return f"{_NID_COOKIE_NAME}={nid}"
        return ""

    def _ensure_nid(self) -> Optional[str]:
        now = time.time()
        if self._nid_value and (now - self._nid_fetched_at) < _NID_CACHE_SECONDS:
            return self._nid_value

        nid = self._fetch_nid()
        if nid:
            self._nid_value = nid
            self._nid_fetched_at = now
        return self._nid_value

    def _fetch_nid(self) -> Optional[str]:
        """访问 eastmoney.com 首页获取 NID cookie"""
        try:
            cookie_jar = http.cookiejar.CookieJar()
            opener = urllib.request.build_opener(
                urllib.request.HTTPCookieProcessor(cookie_jar),
                urllib.request.HTTPRedirectHandler(),
            )
            req = urllib.request.Request(
                _NID_ACQUIRE_URL,
                headers={
                    "User-Agent": random.choice(_USER_AGENTS),
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                },
            )
            with opener.open(req, timeout=15) as resp:
                resp.read()  # consume body

            for cookie in cookie_jar:
                if cookie.name == _NID_COOKIE_NAME:
                    return cookie.value
            return None
        except Exception:
            return None

    def apply_to_request(self, req: urllib.request.Request):
        """将补丁应用到已有的 urllib Request 对象上"""
        headers, cookie = self.get_headers()
        for key, value in headers.items():
            req.headers[key] = value
        if cookie:
            req.add_header("Cookie", cookie)


# ── 全局单例 ──
_global_session: Optional[EastmoneySession] = None


def get_eastmoney_session() -> EastmoneySession:
    global _global_session
    if _global_session is None:
        _global_session = EastmoneySession()
    return _global_session
