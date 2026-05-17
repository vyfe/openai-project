from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request

from quant_client.common import infer_exchange, normalize_code, normalize_symbol, parse_trade_date, to_float
from quant_client.provider_base import BaseAshareProvider


EASTMONEY_KLINE_URL = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
EASTMONEY_UT = "fa5fd1943c7b386f172d6893dbfba10b"
MAX_RETRIES = 3
RETRY_SLEEP_SECONDS = 60


def _get_secid(code: str) -> str:
    return f"1.{code}" if code.startswith("6") else f"0.{code}"


class EastmoneyAshareProvider(BaseAshareProvider):
    """直接调用东方财富 Push API 获取日线数据，字段最全、延迟最低。"""

    provider_name = "eastmoney"
    provider_version = "push2his_eastmoney_kline"

    def fetch_daily_bars(self, symbols: list[str], start_date: str, end_date: str, adjust_flag: str = "qfq") -> list[dict]:
        rows: list[dict] = []
        for raw_symbol in symbols:
            rows.extend(self._fetch_one_symbol(raw_symbol, start_date, end_date, adjust_flag))
        return rows

    def _fetch_one_symbol(self, raw_symbol: str, start_date: str, end_date: str, adjust_flag: str) -> list[dict]:
        code = normalize_code(raw_symbol)
        exchange = infer_exchange(code)
        secid = _get_secid(code)

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

        last_exc = None
        for attempt in range(MAX_RETRIES):
            try:
                req = urllib.request.Request(
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
                        "Referer": "https://quote.eastmoney.com/",
                        "Accept": "application/json,text/plain,*/*",
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
                    raise RuntimeError(f"东方财富日线请求失败 (已重试{MAX_RETRIES}次): {last_exc}") from last_exc

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
