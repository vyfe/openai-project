from __future__ import annotations

import json
import os
import time
import urllib.request

from quant_client.common import infer_exchange, normalize_code, normalize_symbol, parse_trade_date, to_float
from quant_client.provider_base import BaseAshareProvider

MAX_RETRIES = 3
RETRY_SLEEP_SECONDS = int(os.environ.get("QUANT_RETRY_SLEEP_SECONDS", "60"))

# 腾讯自选股 K 线接口：日线 + 前/后/不复权三套数据
# ⚠️ fqkline 接口精简版只返回 6 个字段：[日期, 开盘, 收盘, 最高, 最低, 成交量(手)]
# 成交额 / 换手率 / 振幅 / 涨跌额 / 涨跌幅 该接口均不提供（涨跌幅可通过相邻收盘价反算）
TENCENT_KLINE_URL = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"

# 复权类型 → 返回字段名
_ADJUST_FIELD = {
    "qfq": "qfqday",
    "hfq": "hfqday",
    "raw": "day",
    "": "qfq",
}


class TencentAshareProvider(BaseAshareProvider):
    """腾讯自选股日线数据，OHLCV + 成交量（成交额/换手率/振幅 不提供，涨跌幅可反算）。"""

    provider_name = "tencent"
    provider_version = "tencent_fqkline_v1"

    def fetch_daily_bars(self, symbols: list[str], start_date: str, end_date: str, adjust_flag: str = "qfq") -> list[dict]:
        rows: list[dict] = []
        for raw_symbol in symbols:
            rows.extend(self._fetch_one_symbol(raw_symbol, start_date, end_date, adjust_flag))
        return rows

    def _fetch_one_symbol(self, raw_symbol: str, start_date: str, end_date: str, adjust_flag: str) -> list[dict]:
        code = normalize_code(raw_symbol)
        exchange = infer_exchange(code)
        market_prefix = "sh" if exchange == "SH" else "sz"
        field = _ADJUST_FIELD.get(adjust_flag, "qfqday")

        start_dt = parse_trade_date(start_date)
        end_dt = parse_trade_date(end_date)
        total_days = (end_dt - start_dt).days + 1
        # 腾讯一次返回的 K 线数量上限受 count 参数控制
        count = max(min(total_days * 3, 800), 60)

        url = f"{TENCENT_KLINE_URL}?param={market_prefix}{code},day,,,{count},{adjust_flag or 'qfq'}"

        last_exc = None
        payload = None
        for attempt in range(MAX_RETRIES):
            try:
                req = urllib.request.Request(
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
                        "Referer": "https://gu.qq.com/",
                    },
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    payload = json.loads(resp.read().decode("utf-8"))
                break
            except Exception as exc:
                last_exc = exc
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_SLEEP_SECONDS)
                else:
                    raise RuntimeError(f"腾讯日线请求失败 (已重试{MAX_RETRIES}次): {last_exc}") from last_exc

        if not isinstance(payload, dict) or payload.get("code") != 0:
            raise RuntimeError(f"腾讯返回异常 (code={payload.get('code') if isinstance(payload, dict) else 'n/a'}, msg={payload.get('msg') if isinstance(payload, dict) else 'n/a'})")

        data_block = payload.get("data") or {}
        stock_data = data_block.get(f"{market_prefix}{code}") or {}
        if not stock_data:
            raise RuntimeError(f"腾讯未返回 {code} 的日线数据")

        # 优先按请求的复权字段取；缺失则降级到 day
        bars = stock_data.get(field) or stock_data.get("day") or []
        if not bars:
            raise RuntimeError(f"腾讯未返回 {code} 的 {field} 数据")

        parsed = []
        prev_close = None
        for item in bars:
            if not isinstance(item, list) or len(item) < 6:
                continue
            trade_dt = parse_trade_date(item[0])
            if trade_dt < start_dt or trade_dt > end_dt:
                # 仍记录上一交易日收盘价，便于反算区间内首日的涨跌幅
                _close_tmp = to_float(item[2])
                if _close_tmp is not None:
                    prev_close = _close_tmp
                continue

            open_price = to_float(item[1])
            close_price = to_float(item[2])
            high_price = to_float(item[3])
            low_price = to_float(item[4])
            volume_hand = to_float(item[5])  # 腾讯成交量单位为「手」，1手=100股
            volume = volume_hand * 100 if volume_hand is not None else None

            # 涨跌幅反算：当前 close 与上一交易日 close 的差比
            pct_change = None
            if prev_close not in (None, 0) and close_price is not None:
                pct_change = (close_price - prev_close) / prev_close * 100

            parsed.append(
                {
                    "symbol": normalize_symbol(code),
                    "code": code,
                    "exchange": exchange,
                    "trade_date": trade_dt.isoformat(),
                    "adjust_flag": "qfq" if field == "qfqday" else "hfq" if field == "hfqday" else "raw",
                    "open_price": open_price,
                    "high_price": high_price,
                    "low_price": low_price,
                    "close_price": close_price,
                    "preclose_price": prev_close,
                    "volume": volume,
                    "amount": None,         # 腾讯 fqkline 不提供
                    "turnover_rate": None,  # 腾讯 fqkline 不提供
                    "pct_change": pct_change,
                    "change": None,         # 腾讯 fqkline 不提供
                    "source": self.provider_name,
                    "data_source_version": self.provider_version,
                }
            )
            prev_close = close_price

        if not parsed:
            raise RuntimeError(f"腾讯未返回 {code} 在 {start_date}~{end_date} 期间的日线数据")
        return parsed
