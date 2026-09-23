"""同花顺金融数据 provider（ths）。

数据来源：`https://fuyao.aicubes.cn/api/a-share/prices/historical`
- 鉴权：请求头 `X-api-key: <your-api-key>`（缺失/无效 → `code=2001`）
- 频率：动态限流，触发时 HTTP 429 或 `code=4001`
- 单 thscode / 单请求，循环遍历 symbols

字段映射（`data.item[]` 为 `PriceBarItem`）：
- `date_ms` (ms) → `trade_date` (ISO YYYY-MM-DD，按 Asia/Shanghai)
- `open_price` / `high_price` / `low_price` / `close_price` 直接透传
- `volume` → `volume`（股）
- `turnover` → `amount`（CNY）
- `preclose_price` / `pct_change` / `change` 从相邻 close 反算（首日为 None）
- `turnover_rate` → None（ths 不提供）

复权：`adjust=none/forward/backward` —— `none` → raw，`forward` → qfq，
`backward` → hfq。provider 透传到 THS 服务端计算。

错误处理：
- `code=2001/2003/3001/3002/1001..1004/4001` 与 HTTP 429/4xx → fail-fast，不重试
  （per-symbol 容错在 fetch_daily_bars 层吞掉）
- `code=5001/5002/5003` 与 HTTP 5xx → 退避重试 ≤ 3 次
- 网络异常（超时/连接错）→ 退避重试 ≤ 3 次
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

from quant_client.common import resolve_market_info, to_float
from quant_client.provider_base import BaseAshareProvider

MAX_RETRIES = 3
RETRY_SLEEP_SECONDS = int(os.environ.get("QUANT_RETRY_SLEEP_SECONDS", "60"))

logger = logging.getLogger("quant.client.ths")

THS_BASE_URL = "https://fuyao.aicubes.cn"
THS_HISTORICAL_URL = f"{THS_BASE_URL}/api/a-share/prices/historical"

# 调整标志 → THS adjust 参数
_ADJUST_MAP = {
    "qfq": "forward",
    "hfq": "backward",
    "raw": "none",
    "": "forward",  # 默认前复权
    "none": "none",
}

# 错误码：业务层不重试，立即失败（per-symbol 容错吞掉）
_NON_RETRYABLE_CODES = {1001, 1002, 1003, 1004, 2001, 2003, 3001, 3002, 4001}
# 业务层重试：服务端 / 上游瞬时错误（5001/5002/5003）允许 ≤ 3 次退避
_RETRYABLE_BIZ_CODES = {5001, 5002, 5003}


_SHANGHAI_TZ = timezone(timedelta(hours=8))


def _resolve_api_key() -> str:
    """从环境变量读 THS_API_KEY。conf → env 的注入在 conf/settings.py 末尾完成。"""
    return (os.environ.get("THS_API_KEY") or "").strip()


def _date_to_ms(date_str: str) -> int:
    """`YYYY-MM-DD` → Asia/Shanghai 00:00 的毫秒时间戳。

    THS 要求毫秒 Unix 时间戳，时区按 Asia/Shanghai；用 `00:00 +08:00` 直接转。
    """
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(f"日期格式错误，需 YYYY-MM-DD: {date_str}") from exc
    shanghai_dt = datetime(dt.year, dt.month, dt.day, tzinfo=_SHANGHAI_TZ)
    return int(shanghai_dt.timestamp() * 1000)


class ThsAshareProvider(BaseAshareProvider):
    """同花顺金融数据（fuyao.aicubes.cn）日线 provider。

    字段完整度 6 项直传（open/high/low/close/volume/turnover），preclose/pct_change/change
    从相邻 close 反算；turnover_rate 显式 None。整体接近 tencent 但多了 amount（成交额）。
    """

    provider_name = "ths"
    provider_version = "fuyao_v1"

    def __init__(self, api_key: str | None = None):
        # 允许显式传入 api_key（便于测试 / 自定义场景）；否则从 env 读
        self.api_key = (api_key if api_key is not None else _resolve_api_key()).strip()

    def fetch_daily_bars(
        self,
        symbols: list[str],
        start_date: str,
        end_date: str,
        adjust_flag: str = "qfq",
    ) -> list[dict]:
        if not self.api_key:
            raise RuntimeError(
                "ths provider 未配置 API Key：请在 conf.ini [quant].ths_api_key 或环境变量 THS_API_KEY 设置"
            )

        try:
            start_ms = _date_to_ms(start_date)
            end_ms = _date_to_ms(end_date)
        except ValueError as exc:
            raise ValueError(f"ths 日期参数错误: {exc}") from exc
        if end_ms < start_ms:
            raise ValueError(f"ths 结束日期早于起始: {start_date} > {end_date}")

        # 10 年窗口限制：start/end 都按 86400000ms * 365 * 10 估算，10 年约 315360000000ms
        if end_ms - start_ms > 10 * 365 * 86400 * 1000:
            raise ValueError(
                f"ths 时间窗口超过 10 年上限: {start_date} ~ {end_date}"
            )

        adjust_param = _ADJUST_MAP.get(adjust_flag, "forward")

        rows: list[dict] = []
        for raw_symbol in symbols:
            try:
                rows.extend(
                    self._fetch_one_symbol(
                        raw_symbol, start_ms, end_ms, adjust_flag, adjust_param
                    )
                )
            except Exception as exc:
                logger.warning(
                    "ths_symbol_failed symbol=%s err=%s", raw_symbol, exc,
                )
                continue
        return rows

    def _fetch_one_symbol(
        self,
        raw_symbol: str,
        start_ms: int,
        end_ms: int,
        adjust_flag: str,
        adjust_param: str,
    ) -> list[dict]:
        market = resolve_market_info(raw_symbol)
        code = market.code
        exchange = market.exchange
        # THS 要求 thscode（必带交易所后缀），且只接受单个 —— 与本项目 `code.EXCHANGE` 一致
        thscode = f"{code}.{exchange}"

        params = {
            "thscode": thscode,
            "interval": "1d",
            "start": str(start_ms),
            "end": str(end_ms),
            "adjust": adjust_param,
        }
        url = f"{THS_HISTORICAL_URL}?{urllib.parse.urlencode(params)}"

        # 业务层重试：5xxx 瞬时错误 → 退避重试；其他错误码 → fail-fast
        payload = None
        last_biz_exc: Exception | None = None
        for attempt in range(MAX_RETRIES):
            payload = self._request_with_retry(url)
            if not isinstance(payload, dict):
                raise RuntimeError(f"ths 返回非字典: {thscode}")
            biz_code = payload.get("code")
            if biz_code in (0, None):
                break
            if biz_code in _NON_RETRYABLE_CODES:
                raise RuntimeError(
                    f"ths 业务错误 code={biz_code} msg={payload.get('message') or '(no message)'} "
                    f"request_id={payload.get('request_id') or '-'} thscode={thscode}（不重试）"
                )
            if biz_code in _RETRYABLE_BIZ_CODES:
                last_biz_exc = RuntimeError(
                    f"ths 业务错误 code={biz_code} msg={payload.get('message') or '(no message)'} "
                    f"request_id={payload.get('request_id') or '-'} thscode={thscode}"
                )
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_SLEEP_SECONDS)
                    continue
                raise last_biz_exc
            # 未知业务码：保守按非重试处理
            raise RuntimeError(
                f"ths 未知业务错误 code={biz_code} msg={payload.get('message') or '(no message)'} "
                f"request_id={payload.get('request_id') or '-'} thscode={thscode}"
            )

        data_block = (payload or {}).get("data") or {}
        items = data_block.get("item") or []
        if not items:
            # 业务返回成功但数据空：不是错（标的可能停牌/未上市），返回空列表
            return []

        symbol = f"{code}.{exchange}"
        parsed: list[dict] = []
        prev_close = None
        for item in items:
            if not isinstance(item, dict):
                continue
            date_ms = item.get("date_ms")
            if date_ms is None:
                continue
            try:
                trade_dt = datetime.fromtimestamp(int(date_ms) / 1000, tz=_SHANGHAI_TZ).date()
            except (TypeError, ValueError, OSError):
                continue

            open_price = to_float(item.get("open_price"))
            high_price = to_float(item.get("high_price"))
            low_price = to_float(item.get("low_price"))
            close_price = to_float(item.get("close_price"))
            volume = to_float(item.get("volume"))
            amount = to_float(item.get("turnover"))  # THS 字段名 turnover

            pct_change = None
            change = None
            if prev_close not in (None, 0) and close_price is not None:
                pct_change = (close_price - prev_close) / prev_close * 100
                change = close_price - prev_close

            adjust_flag_out = adjust_flag or "raw"
            if adjust_flag_out not in ("qfq", "hfq", "raw"):
                adjust_flag_out = "raw"

            parsed.append({
                "symbol": symbol,
                "code": code,
                "exchange": exchange,
                "trade_date": trade_dt.isoformat(),
                "adjust_flag": adjust_flag_out,
                "open_price": open_price,
                "high_price": high_price,
                "low_price": low_price,
                "close_price": close_price,
                "preclose_price": prev_close,
                "volume": volume,
                "amount": amount,
                "turnover_rate": None,
                "pct_change": pct_change,
                "change": change,
                "source": self.provider_name,
                "data_source_version": self.provider_version,
            })
            prev_close = close_price

        return parsed

    def _request_with_retry(self, url: str) -> dict | None:
        """GET ths 接口，处理鉴权/限流/重试。

        - HTTP 401/403/404/429 → 不重试（业务层 fail-fast）
        - HTTP 5xx / 网络超时 → 退避重试 ≤ 3 次
        - 业务 code 在 2001/2003/3001/3002/4001/1001..1004 → 不重试
        - 业务 code 5001/5002/5003 → 退避重试 ≤ 3 次
        """
        headers = {
            "Accept": "application/json",
            "X-api-key": self.api_key,
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
        }
        last_exc: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=30) as resp:
                    raw = resp.read()
                return json.loads(raw.decode("utf-8"))
            except urllib.error.HTTPError as exc:
                # 401/403/404/429 → fail-fast（不重试，per-symbol 容错层吞掉）
                if exc.code in (401, 403, 404, 429):
                    raise RuntimeError(
                        f"ths HTTP {exc.code}: {exc.reason}（不重试）"
                    ) from exc
                last_exc = exc
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_SLEEP_SECONDS)
                    continue
                raise RuntimeError(
                    f"ths 请求失败 (已重试{MAX_RETRIES}次): HTTP {exc.code} {exc.reason}"
                ) from exc
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                last_exc = exc
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_SLEEP_SECONDS)
                    continue
                raise RuntimeError(
                    f"ths 请求失败 (已重试{MAX_RETRIES}次): {last_exc}"
                ) from exc

        raise RuntimeError(f"ths 请求失败 (已重试{MAX_RETRIES}次): {last_exc}")