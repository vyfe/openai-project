"""股票名称批量回填服务 — 走腾讯一次性 metadata 端点补 quant_instrument.name。

背景：4 个数据 provider 都不回传 name，导致 K 线 bundle 落库时 name 字段为空。
本服务从腾讯 https://qt.gtimg.cn/q=sz002837 拉中文名（第二个字段），批量写回 DB。
"""

from __future__ import annotations

import os
import re
import time
import urllib.parse
import urllib.request
from typing import Optional

from quant.entities import QuantInstrument

TENCENT_META_URL = "https://qt.gtimg.cn/q={codes}"
MAX_BATCH = 60  # 一次请求最多 60 个 symbol，避免 URL 过长
REQUEST_TIMEOUT = 15
MAX_RETRIES = 2

_QUOTE_RE = re.compile(r'(?:^|;)\s*([A-Za-z0-9_]+)="([^"]*)"')


def _to_qt_code(symbol: str) -> Optional[str]:
    """把 002837.SZ 转成 sz002837，识别不出来返回 None。"""
    s = str(symbol or "").strip().lower()
    if not s:
        return None
    if "." in s:
        left, _, right = s.rpartition(".")
        if right in ("sh", "sz", "bj"):
            return f"{right}{left}"
    # 纯 6 位代码
    if re.fullmatch(r"\d{6}", s):
        if s.startswith(("6", "5", "9")):
            return f"sh{s}"
        if s.startswith(("0", "2", "3")):
            return f"sz{s}"
        if s.startswith(("4", "8")):
            return f"bj{s}"
    return None


def _parse_qt_response(body: str) -> dict[str, str]:
    """解析 v_sz002837="51~英维克~002837~..." 这类响应，返回 {qt_code: name}。"""
    result: dict[str, str] = {}
    for match in _QUOTE_RE.finditer(body):
        qt_code = match.group(1).lstrip("v_").strip().lower()
        payload = match.group(2)
        if not qt_code or "~" not in payload:
            continue
        fields = payload.split("~")
        if len(fields) < 2:
            continue
        name = fields[1].strip()
        if name:
            result[qt_code] = name
    return result


def _fetch_batch(qt_codes: list[str]) -> dict[str, str]:
    """从腾讯拉一批 symbol 的名称。返回 {qt_code: name}，失败的 qt_code 不在结果中。"""
    if not qt_codes:
        return {}
    url = TENCENT_META_URL.format(codes=urllib.parse.quote(",".join(qt_codes), safe=","))
    last_exc: Optional[Exception] = None
    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
                    "Referer": "https://gu.qq.com/",
                },
            )
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
                body = resp.read().decode("gbk", errors="ignore")
            return _parse_qt_response(body)
        except Exception as exc:
            last_exc = exc
            if attempt < MAX_RETRIES - 1:
                time.sleep(1)
    return {}


def refresh_instrument_names(only_empty: bool = True, batch_size: int = MAX_BATCH) -> dict:
    """批量刷新 quant_instrument.name。

    Args:
        only_empty: True 只补 name='' 的；False 强制刷新全部
        batch_size: 每次 HTTP 请求最多带多少个 symbol

    Returns:
        {"scanned": 扫描数, "updated": 更新数, "skipped": 跳过数, "failed": 失败数, "errors": [...]}
    """
    query = QuantInstrument.select(QuantInstrument.symbol)
    if only_empty:
        query = query.where((QuantInstrument.name == "") | (QuantInstrument.name.is_null()))
    scanned = query.count()
    if scanned == 0:
        return {"scanned": 0, "updated": 0, "skipped": 0, "failed": 0, "errors": []}

    symbols = [row.symbol for row in query.iterator()]
    qt_to_symbol: dict[str, str] = {}
    for sym in symbols:
        qt = _to_qt_code(sym)
        if qt:
            qt_to_symbol[qt] = sym

    if not qt_to_symbol:
        return {"scanned": scanned, "updated": 0, "skipped": scanned, "failed": 0, "errors": ["所有 symbol 都无法映射到腾讯代码"]}

    updated = 0
    failed = 0
    errors: list[str] = []
    qt_codes = list(qt_to_symbol.keys())

    for i in range(0, len(qt_codes), batch_size):
        chunk = qt_codes[i:i + batch_size]
        name_map = _fetch_batch(chunk)
        for qt in chunk:
            sym = qt_to_symbol[qt]
            if qt not in name_map:
                failed += 1
                continue
            try:
                QuantInstrument.update(name=name_map[qt]).where(
                    QuantInstrument.symbol == sym
                ).execute()
                updated += 1
            except Exception as exc:
                failed += 1
                errors.append(f"{sym}: {exc}")
        # 批次间轻 sleep，避免触发腾讯限流
        if i + batch_size < len(qt_codes):
            time.sleep(0.5)

    return {
        "scanned": scanned,
        "updated": updated,
        "skipped": scanned - updated - failed,
        "failed": failed,
        "errors": errors[:10],
    }
