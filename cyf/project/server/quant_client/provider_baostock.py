from __future__ import annotations

import os
import time

from quant_client.common import infer_exchange, normalize_code, normalize_symbol, parse_trade_date, to_baostock_symbol, to_float
from quant_client.provider_base import BaseAshareProvider

MAX_RETRIES = 3
RETRY_SLEEP_SECONDS = int(os.environ.get("QUANT_RETRY_SLEEP_SECONDS", "60"))


class BaostockAshareProvider(BaseAshareProvider):
    provider_name = "baostock"
    provider_version = "query_history_k_data_plus"

    _ADJUST_MAP = {
        "hfq": "1",
        "qfq": "2",
        "raw": "3",
        "": "3",
    }

    def fetch_daily_bars(self, symbols: list[str], start_date: str, end_date: str, adjust_flag: str = "qfq") -> list[dict]:
        try:
            import baostock as bs
        except ImportError as exc:
            raise RuntimeError("未安装 baostock，请先安装依赖") from exc

        adjust_code = self._ADJUST_MAP.get(adjust_flag, "2")

        last_exc = None
        for attempt in range(MAX_RETRIES):
            try:
                login_result = bs.login()
                if getattr(login_result, "error_code", "0") != "0":
                    last_exc = RuntimeError(f"baostock 登录失败: {login_result.error_msg}")
                    if attempt < MAX_RETRIES - 1:
                        time.sleep(RETRY_SLEEP_SECONDS)
                        continue
                    raise last_exc
                break
            except Exception as exc:
                last_exc = exc
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_SLEEP_SECONDS)
                else:
                    raise RuntimeError(f"baostock 登录失败 (已重试{MAX_RETRIES}次): {last_exc}") from last_exc

        try:
            rows: list[dict] = []
            for raw_symbol in symbols:
                code = normalize_code(raw_symbol)
                exchange = infer_exchange(code)
                rows.extend(self._fetch_one_symbol(bs, code, exchange, start_date, end_date, adjust_flag, adjust_code))
            return rows
        finally:
            bs.logout()

    def _fetch_one_symbol(self, bs, code: str, exchange: str, start_date: str, end_date: str, adjust_flag: str, adjust_code: str) -> list[dict]:
        full_symbol = to_baostock_symbol(code)
        field_sets = [
            "date,code,open,high,low,close,preclose,volume,amount,pctChg,turn",
            "date,code,open,high,low,close,preclose,volume,amount",
        ]

        last_error = ""
        records = []
        for fields in field_sets:
            last_exc = None
            for attempt in range(MAX_RETRIES):
                try:
                    rs = bs.query_history_k_data_plus(
                        full_symbol,
                        fields,
                        start_date=start_date,
                        end_date=end_date,
                        frequency="d",
                        adjustflag=adjust_code,
                    )
                    if getattr(rs, "error_code", "0") != "0":
                        last_exc = RuntimeError(getattr(rs, "error_msg", ""))
                        if attempt < MAX_RETRIES - 1:
                            time.sleep(RETRY_SLEEP_SECONDS)
                            continue
                    else:
                        while rs.next():
                            records.append(rs.get_row_data())
                        if records:
                            columns = rs.fields
                            return self._map_rows(code, exchange, columns, records, adjust_flag)
                        last_exc = RuntimeError(f"baostock 返回空数据: {full_symbol}")
                except Exception as exc:
                    last_exc = exc
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_SLEEP_SECONDS)

            last_error = str(last_exc)

        raise RuntimeError(f"baostock 查询失败 (已重试{MAX_RETRIES}次): {last_error or full_symbol}")

    def _map_rows(self, code: str, exchange: str, columns: list[str], records: list[list[str]], adjust_flag: str) -> list[dict]:
        mapped = []
        prev_close = None
        for row in records:
            item = dict(zip(columns, row))
            close_price = to_float(item.get("close"))
            preclose_price = to_float(item.get("preclose")) or prev_close
            pct_change = to_float(item.get("pctChg"))
            if pct_change is None and close_price is not None and preclose_price not in (None, 0):
                pct_change = (close_price - preclose_price) / preclose_price * 100
            mapped.append(
                {
                    "symbol": normalize_symbol(code),
                    "code": code,
                    "exchange": exchange,
                    "trade_date": parse_trade_date(item.get("date")).isoformat(),
                    "adjust_flag": adjust_flag or "raw",
                    "open_price": to_float(item.get("open")),
                    "high_price": to_float(item.get("high")),
                    "low_price": to_float(item.get("low")),
                    "close_price": close_price,
                    "preclose_price": preclose_price,
                    "volume": to_float(item.get("volume")),
                    "amount": to_float(item.get("amount")),
                    "turnover_rate": to_float(item.get("turn")),
                    "pct_change": pct_change,
                    "source": self.provider_name,
                    "data_source_version": self.provider_version,
                }
            )
            prev_close = close_price
        return mapped
