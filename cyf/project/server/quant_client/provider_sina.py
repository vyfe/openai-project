from __future__ import annotations

import json
import os
import time
import urllib.request

from quant_client.common import infer_exchange, normalize_code, normalize_symbol, parse_trade_date, to_float
from quant_client.provider_base import BaseAshareProvider

MAX_RETRIES = 3
RETRY_SLEEP_SECONDS = int(os.environ.get("QUANT_RETRY_SLEEP_SECONDS", "60"))

SINA_KLINE_URL = "https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData"


class SinaAshareProvider(BaseAshareProvider):
    """新浪财经日线数据，OHLCV 基本字段，作为东财/AKShare/Baostock 之外的第四备选。"""

    provider_name = "sina"
    provider_version = "sina_kline_v1"

    def fetch_daily_bars(self, symbols: list[str], start_date: str, end_date: str, adjust_flag: str = "qfq") -> list[dict]:
        rows: list[dict] = []
        for raw_symbol in symbols:
            rows.extend(self._fetch_one_symbol(raw_symbol, start_date, end_date, adjust_flag))
        return rows

    def _fetch_one_symbol(self, raw_symbol: str, start_date: str, end_date: str, adjust_flag: str) -> list[dict]:
        code = normalize_code(raw_symbol)
        exchange = infer_exchange(code)
        market_prefix = "sh" if exchange == "SH" else "sz"

        start_dt = parse_trade_date(start_date)
        end_dt = parse_trade_date(end_date)

        # sina returns up to ~2000 records, fetch enough
        total_days = (end_dt - start_dt).days + 1
        datalen = max(total_days * 3, 60)

        url = f"{SINA_KLINE_URL}?symbol={market_prefix}{code}&scale=240&ma=no&datalen={datalen}"

        last_exc = None
        for attempt in range(MAX_RETRIES):
            try:
                req = urllib.request.Request(
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
                        "Referer": "https://finance.sina.com.cn/",
                    },
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    raw_bytes = resp.read()
                    text = raw_bytes.decode("gbk", errors="ignore")
                    payload = json.loads(text)
                break
            except Exception as exc:
                last_exc = exc
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_SLEEP_SECONDS)
                else:
                    raise RuntimeError(f"新浪日线请求失败 (已重试{MAX_RETRIES}次): {last_exc}") from last_exc

        if not isinstance(payload, list) or not payload:
            raise RuntimeError(f"新浪未返回 {code} 的日线数据")

        parsed = []
        prev_close_price = None
        for item in payload:
            trade_dt = parse_trade_date(item.get("day"))
            if trade_dt < start_dt or trade_dt > end_dt:
                continue

            close_price = to_float(item.get("close"))
            pct_change = None
            if close_price is not None and prev_close_price not in (None, 0):
                pct_change = (close_price - prev_close_price) / prev_close_price * 100

            parsed.append(
                {
                    "symbol": normalize_symbol(code),
                    "code": code,
                    "exchange": exchange,
                    "trade_date": trade_dt.isoformat(),
                    "adjust_flag": "raw",  # Sina API 仅返回未复权数据
                    "open_price": to_float(item.get("open")),
                    "high_price": to_float(item.get("high")),
                    "low_price": to_float(item.get("low")),
                    "close_price": close_price,
                    "preclose_price": prev_close_price,
                    "volume": to_float(item.get("volume")),
                    "amount": None,
                    "turnover_rate": None,
                    "pct_change": pct_change,
                    "source": self.provider_name,
                    "data_source_version": self.provider_version,
                }
            )
            prev_close_price = close_price

        if not parsed:
            raise RuntimeError(f"新浪未返回 {code} 在 {start_date}~{end_date} 期间的日线数据")
        return parsed
