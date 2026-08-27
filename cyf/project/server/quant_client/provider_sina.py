from __future__ import annotations

import json
import logging
import os
import time
import urllib.request
from datetime import date, datetime

from quant_client.common import normalize_symbol, parse_trade_date, parse_trade_datetime, resolve_market_info, to_float
from quant_client.provider_base import BaseAshareProvider

MAX_RETRIES = 3
RETRY_SLEEP_SECONDS = int(os.environ.get("QUANT_RETRY_SLEEP_SECONDS", "60"))

logger = logging.getLogger("quant.client.sina")

SINA_KLINE_URL = "https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData"


class SinaAshareProvider(BaseAshareProvider):
    """新浪财经日线数据，OHLCV 基本字段，作为东财/AKShare/Baostock 之外的第四备选。"""

    provider_name = "sina"
    provider_version = "sina_kline_v1"

    _INTERVAL_TO_SCALE = {"1m": "1", "5m": "5", "15m": "15", "30m": "30", "60m": "60"}

    def fetch_daily_bars(self, symbols: list[str], start_date: str, end_date: str, adjust_flag: str = "qfq") -> list[dict]:
        rows: list[dict] = []
        for raw_symbol in symbols:
            try:
                rows.extend(self._fetch_one_symbol(raw_symbol, start_date, end_date, adjust_flag))
            except Exception as exc:
                logger.warning(
                    "sina_symbol_failed symbol=%s err=%s", raw_symbol, exc,
                )
                continue
        return rows

    def fetch_minute_bars(
        self,
        symbols: list[str],
        interval: str,
        start_dt: str,
        end_dt: str,
        adjust_flag: str = "qfq",
    ) -> list[dict]:
        if interval not in self._INTERVAL_TO_SCALE:
            raise ValueError(f"新浪不支持的 interval: {interval}")
        # 新浪分时接口仅返回当日数据，跨日 / 历史区间直接拒绝
        try:
            start_day = parse_trade_date(start_dt).isoformat()
            end_day = parse_trade_date(end_dt).isoformat()
        except ValueError as exc:
            raise ValueError(f"新浪分时 start_dt/end_dt 必须为日期字符串: {exc}") from exc
        if start_day != end_day or start_day != date.today().isoformat():
            raise ValueError(
                f"新浪分时仅支持当日数据：start_dt={start_dt} end_dt={end_dt} today={date.today().isoformat()}"
            )

        rows: list[dict] = []
        for raw_symbol in symbols:
            try:
                rows.extend(self._fetch_one_symbol_minute(raw_symbol, interval))
            except Exception as exc:
                logger.warning(
                    "sina_minute_symbol_failed symbol=%s err=%s", raw_symbol, exc,
                )
                continue
        return rows

    def _fetch_one_symbol(self, raw_symbol: str, start_date: str, end_date: str, adjust_flag: str) -> list[dict]:
        market = resolve_market_info(raw_symbol)
        code = market.code
        exchange = market.exchange
        market_prefix = market.market_prefix

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

    def _fetch_one_symbol_minute(self, raw_symbol: str, interval: str) -> list[dict]:
        market = resolve_market_info(raw_symbol)
        code = market.code
        exchange = market.exchange
        market_prefix = market.market_prefix
        scale = self._INTERVAL_TO_SCALE[interval]

        # 当日 ~48 根 5min，多预留一些防异常
        url = f"{SINA_KLINE_URL}?symbol={market_prefix}{code}&scale={scale}&ma=no&datalen=480"

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
                    raise RuntimeError(f"新浪分时请求失败 (已重试{MAX_RETRIES}次): {last_exc}") from last_exc

        if not isinstance(payload, list) or not payload:
            raise RuntimeError(f"新浪未返回 {code} 的分时数据")

        today = date.today().isoformat()
        parsed = []
        prev_close_price = None
        for item in payload:
            day_text = (item.get("day") or "").strip()
            # 新浪分时 day 字段形如 "2024-01-02 09:35"
            try:
                trade_dt = parse_trade_datetime(day_text)
            except ValueError:
                continue
            trade_date_text = trade_dt.date().isoformat()
            if trade_date_text != today:
                continue

            close_price = to_float(item.get("close"))
            parsed.append(
                {
                    "symbol": normalize_symbol(code),
                    "code": code,
                    "exchange": exchange,
                    "trade_datetime": trade_dt.isoformat(),
                    "trade_date": trade_date_text,
                    "interval": interval,
                    "adjust_flag": "raw",  # Sina API 仅返回未复权数据
                    "open_price": to_float(item.get("open")),
                    "high_price": to_float(item.get("high")),
                    "low_price": to_float(item.get("low")),
                    "close_price": close_price,
                    "preclose_price": prev_close_price,
                    "volume": to_float(item.get("volume")),
                    "amount": None,
                    "turnover_rate": None,
                    "pct_change": None,
                    "source": self.provider_name,
                    "data_source_version": self.provider_version,
                }
            )
            prev_close_price = close_price

        if not parsed:
            raise RuntimeError(f"新浪未返回 {code} 当日的 {interval} 分时数据")
        return parsed
