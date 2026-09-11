from __future__ import annotations

import json
import logging
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime

from quant_client.eastmoney_patch import get_eastmoney_session
from quant_client.common import is_minute_bar_skip_symbol, normalize_symbol, parse_trade_date, parse_trade_datetime, resolve_market_info, to_float
from quant_client.provider_base import BaseAshareProvider


EASTMONEY_KLINE_URL = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
EASTMONEY_UT = "fa5fd1943c7b386f172d6893dbfba10b"
MAX_RETRIES = 3
RETRY_SLEEP_SECONDS = int(os.environ.get("QUANT_RETRY_SLEEP_SECONDS", "60"))

logger = logging.getLogger("quant.client.eastmoney")


def _get_secid(code: str, exchange: str = "") -> str:
    """东财 secid 格式：`{market_id}.{code}`，market_id 由交易所决定。

    沪市=1、深市=0（与 code 前缀不是 1:1 关系，所以这里信任传入的 exchange 而非推断）。
    """
    if exchange == "SH":
        return f"1.{code}"
    if exchange == "SZ":
        return f"0.{code}"
    # fallback：仅在调用方没传 exchange 时使用
    return f"1.{code}" if code.startswith("6") else f"0.{code}"


def _request_kline(url: str, label: str) -> dict:
    last_exc = None
    for attempt in range(MAX_RETRIES):
        try:
            session = get_eastmoney_session()
            headers, cookie = session.get_headers()
            req = urllib.request.Request(url, headers=headers)
            if cookie:
                req.add_header("Cookie", cookie)
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            last_exc = exc
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_SLEEP_SECONDS)
    raise RuntimeError(f"{label}请求失败 (已重试{MAX_RETRIES}次): {last_exc}") from last_exc


class EastmoneyAshareProvider(BaseAshareProvider):
    """直接调用东方财富 Push API 获取日线数据，字段最全、延迟最低。"""

    provider_name = "eastmoney"
    provider_version = "push2his_eastmoney_kline"

    _INTERVAL_TO_KLT = {"1m": "1", "5m": "5", "15m": "15", "30m": "30", "60m": "60"}

    def fetch_daily_bars(self, symbols: list[str], start_date: str, end_date: str, adjust_flag: str = "qfq") -> list[dict]:
        rows: list[dict] = []
        for raw_symbol in symbols:
            try:
                rows.extend(self._fetch_one_symbol(raw_symbol, start_date, end_date, adjust_flag))
            except Exception as exc:
                logger.warning(
                    "eastmoney_symbol_failed symbol=%s err=%s", raw_symbol, exc,
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
        # fail-fast：指数在东方财富分时接口持续断连/限流，直接跳过避免重试
        filtered_symbols = [s for s in (symbols or []) if not is_minute_bar_skip_symbol(s)]
        skipped = [s for s in (symbols or []) if is_minute_bar_skip_symbol(s)]
        if skipped:
            logger.info(
                "eastmoney_minute_skip_index symbols=%s reason=minute_bar_skiplist",
                ",".join(skipped),
            )
        if not filtered_symbols:
            return []

        rows: list[dict] = []
        for raw_symbol in filtered_symbols:
            try:
                rows.extend(self._fetch_one_symbol_minute(raw_symbol, interval, start_dt, end_dt, adjust_flag))
            except Exception as exc:
                logger.warning(
                    "eastmoney_minute_symbol_failed symbol=%s err=%s", raw_symbol, exc,
                )
                continue
        return rows

    def _fetch_one_symbol(self, raw_symbol: str, start_date: str, end_date: str, adjust_flag: str) -> list[dict]:
        market = resolve_market_info(raw_symbol)
        code = market.code
        exchange = market.exchange
        secid = _get_secid(code, exchange)

        fqt_map = {"qfq": "1", "hfq": "2", "raw": "0", "": "1"}
        fqt = fqt_map.get(adjust_flag, "1")

        start_dt = parse_trade_date(start_date)
        end_dt = parse_trade_date(end_date)
        total_days = (end_dt - start_dt).days + 1
        request_limit = max(total_days * 3, 60)

        params = {
            "secid": secid,
            "ut": EASTMONEY_UT,
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
            "klt": "101",
            "fqt": fqt,
            "beg": start_date.replace("-", ""),
            "end": end_date.replace("-", ""),
            "smplmt": str(request_limit),
            "lmt": str(request_limit),
        }
        url = f"{EASTMONEY_KLINE_URL}?{urllib.parse.urlencode(params)}"
        payload = _request_kline(url, "东方财富日线")

        data = payload.get("data") or {}
        stock_name = str(data.get("name") or code)
        klines = data.get("klines") or []
        if not klines:
            raise RuntimeError(f"东方财富未返回 {code} 的日线数据")

        parsed = []
        for row in klines:
            fields = row.split(",")
            trade_date_raw, open_, close, high, low, volume, amount, amplitude, pct_change, change, turnover = fields
            trade_dt = parse_trade_date(trade_date_raw)
            if trade_dt < start_dt or trade_dt > end_dt:
                continue

            close_price = to_float(close)
            preclose_price = to_float(close) - to_float(change) if to_float(change) is not None and close_price is not None else None

            parsed.append(
                {
                    "symbol": normalize_symbol(code),
                    "code": code,
                    "exchange": exchange,
                    "trade_date": trade_dt.isoformat(),
                    "adjust_flag": adjust_flag or "qfq",
                    "open_price": to_float(open_),
                    "high_price": to_float(high),
                    "low_price": to_float(low),
                    "close_price": close_price,
                    "preclose_price": preclose_price,
                    "volume": to_float(volume),
                    "amount": to_float(amount),
                    "turnover_rate": to_float(turnover),
                    "pct_change": to_float(pct_change),
                    "change": to_float(change),
                    "amplitude_pct": to_float(amplitude),
                    "name": stock_name,
                    "source": self.provider_name,
                    "data_source_version": self.provider_version,
                }
            )

        if not parsed:
            raise RuntimeError(f"东方财富未返回 {code} 在 {start_date}~{end_date} 期间的日线数据")
        return parsed

    def _fetch_one_symbol_minute(
        self,
        raw_symbol: str,
        interval: str,
        start_dt: str,
        end_dt: str,
        adjust_flag: str,
    ) -> list[dict]:
        market = resolve_market_info(raw_symbol)
        code = market.code
        exchange = market.exchange
        secid = _get_secid(code, exchange)

        klt = self._INTERVAL_TO_KLT.get(interval)
        if not klt:
            raise ValueError(f"东方财富不支持的 interval: {interval}")

        fqt_map = {"qfq": "1", "hfq": "2", "raw": "0", "": "1"}
        fqt = fqt_map.get(adjust_flag, "1")

        start_date_text = (start_dt or "")[:10]
        end_date_text = (end_dt or "")[:10]
        if not start_date_text or not end_date_text:
            raise ValueError("东方财富分时必须提供 start_dt / end_dt")

        # 东财分时一次请求最多 ~1000 根；按区间天数算 5min 一天 48 根，7 天约 336 根足够
        days = max(1, (parse_trade_date(end_date_text) - parse_trade_date(start_date_text)).days + 1)
        request_limit = max(480 * days, 600)

        params = {
            "secid": secid,
            "ut": EASTMONEY_UT,
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
            "klt": klt,
            "fqt": fqt,
            "beg": start_date_text.replace("-", ""),
            "end": end_date_text.replace("-", ""),
            "smplmt": str(request_limit),
            "lmt": str(request_limit),
        }
        url = f"{EASTMONEY_KLINE_URL}?{urllib.parse.urlencode(params)}"
        payload = _request_kline(url, "东方财富分时")

        data = payload.get("data") or {}
        klines = data.get("klines") or []
        if not klines:
            raise RuntimeError(f"东方财富未返回 {code} 的分时数据")

        start_bound = parse_trade_datetime(f"{start_date_text} 00:00:00")
        end_bound = parse_trade_datetime(f"{end_date_text} 23:59:59")

        parsed = []
        for row in klines:
            fields = row.split(",")
            trade_dt_raw, open_, close, high, low, volume, amount, amplitude, pct_change, change, turnover = fields
            try:
                trade_dt = parse_trade_datetime(trade_dt_raw.strip())
            except ValueError:
                continue
            if trade_dt < start_bound or trade_dt > end_bound:
                continue

            parsed.append(
                {
                    "symbol": normalize_symbol(code),
                    "code": code,
                    "exchange": exchange,
                    "trade_datetime": trade_dt.isoformat(),
                    "trade_date": trade_dt.date().isoformat(),
                    "interval": interval,
                    "adjust_flag": adjust_flag or "qfq",
                    "open_price": to_float(open_),
                    "high_price": to_float(high),
                    "low_price": to_float(low),
                    "close_price": to_float(close),
                    "volume": to_float(volume),
                    "amount": to_float(amount),
                    "turnover_rate": to_float(turnover),
                    "pct_change": to_float(pct_change),
                    "change": to_float(change),
                    "amplitude_pct": to_float(amplitude),
                    "source": self.provider_name,
                    "data_source_version": self.provider_version,
                }
            )

        if not parsed:
            raise RuntimeError(f"东方财富未返回 {code} 在 {start_date_text}~{end_date_text} 期间的分时数据")
        return parsed
