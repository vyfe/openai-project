from __future__ import annotations

import hashlib
import json
import ssl
import time
import urllib.request
from datetime import datetime
from typing import Any

from service.quant.common import infer_exchange

def _now() -> datetime:
    return datetime.now()


def _json_dumps(payload: Any) -> str:
    return json.dumps(payload if payload is not None else {}, ensure_ascii=False)


def _url_hash(board_id: int, url: str) -> str:
    return hashlib.sha256(f"{board_id}:{url}".encode("utf-8")).hexdigest()


def _get_secid(code: str) -> str:
    return f"1.{code}" if code.startswith("6") else f"0.{code}"


def _market_prefix(code: str) -> str:
    return "sh" if infer_exchange(code) == "SH" else "sz"


def _fetch_text(url: str, *, referer: str, timeout: int = 10, encoding: str = "utf-8") -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
            "Referer": referer,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Connection": "close",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode(encoding, errors="ignore")


def _fetch_json(url: str, *, referer: str, timeout: int = 8, attempts: int = 1) -> dict[str, Any]:
    ctx = ssl.create_default_context()
    last_exc: Exception | None = None
    for attempt in range(max(1, attempts)):
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
                "Referer": referer,
                "Accept": "application/json,text/plain,*/*",
                "Connection": "close",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            last_exc = exc
            if attempt < attempts - 1:
                time.sleep(1 + attempt)
    raise RuntimeError(str(last_exc)) from last_exc
