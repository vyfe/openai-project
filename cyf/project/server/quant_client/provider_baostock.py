from __future__ import annotations

import os
import time
from datetime import datetime

import logging

from quant_client.common import normalize_symbol, parse_trade_date, resolve_market_info, to_baostock_symbol, to_float
from quant_client.provider_base import BaseAshareProvider

MAX_RETRIES = 3
RETRY_SLEEP_SECONDS = int(os.environ.get("QUANT_RETRY_SLEEP_SECONDS", "60"))

logger = logging.getLogger("quant.client.baostock")


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
                try:
                    market = resolve_market_info(raw_symbol)
                    rows.extend(
                        self._fetch_one_symbol(
                            bs, market.code, market.exchange, start_date, end_date, adjust_flag, adjust_code
                        )
                    )
                except Exception as exc:
                    logger.warning(
                        "baostock_symbol_failed symbol=%s err=%s", raw_symbol, exc,
                    )
                    continue
            return rows
        finally:
            bs.logout()

    def _fetch_one_symbol(self, bs, code: str, exchange: str, start_date: str, end_date: str, adjust_flag: str, adjust_code: str) -> list[dict]:
        # 注意：必须用上游已经解析过的 exchange 去拼 baostock 代码，而不是再调 to_baostock_symbol(code)——
        # 那样会因为 code 被 strip 过 suffix 重新推断错（000001 又被推断成 SZ）。
        full_symbol = f"{exchange.lower()}.{code}"
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
        # 用上游已解析的 exchange 拼 symbol，避免 normalize_symbol(code) 强行按 code 前缀推断
        #（000001.SH / 000300.SH 这种以 0 开头的指数，normalize_symbol 推断会变成 SZ）
        symbol = f"{code}.{exchange}"
        for row in records:
            item = dict(zip(columns, row))
            close_price = to_float(item.get("close"))
            preclose_price = to_float(item.get("preclose")) or prev_close
            pct_change = to_float(item.get("pctChg"))
            if pct_change is None and close_price is not None and preclose_price not in (None, 0):
                pct_change = (close_price - preclose_price) / preclose_price * 100
            mapped.append(
                {
                    "symbol": symbol,
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

    # ----- 分时 K 线（frequency="5"/"15"/"30"/"60"） -----

    _INTERVAL_TO_FREQ = {"5m": "5", "15m": "15", "30m": "30", "60m": "60"}

    def fetch_minute_bars(
        self,
        symbols: list[str],
        interval: str,
        start_dt: str,
        end_dt: str,
        adjust_flag: str = "qfq",
    ) -> list[dict]:
        try:
            import baostock as bs
        except ImportError as exc:
            raise RuntimeError("未安装 baostock，请先安装依赖") from exc

        bs_freq = self._INTERVAL_TO_FREQ.get(interval, "5")
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
                try:
                    market = resolve_market_info(raw_symbol)
                    rows.extend(
                        self._fetch_one_symbol_minute(
                            bs,
                            market.code,
                            market.exchange,
                            start_dt,
                            end_dt,
                            bs_freq,
                            interval,
                            adjust_flag,
                            adjust_code,
                        )
                    )
                except Exception as exc:
                    logger.warning(
                        "baostock_minute_symbol_failed symbol=%s err=%s", raw_symbol, exc,
                    )
                    continue
            return rows
        finally:
            bs.logout()

    def _fetch_one_symbol_minute(
        self,
        bs,
        code: str,
        exchange: str,
        start_dt: str,
        end_dt: str,
        bs_freq: str,
        interval: str,
        adjust_flag: str,
        adjust_code: str,
    ) -> list[dict]:
        full_symbol = f"{exchange.lower()}.{code}"
        # baostock 分钟线 fields 末尾必须含 time 字段（频率相关列）
        field_set = "date,time,code,open,high,low,close,volume,amount"
        start_date = (start_dt or "")[:10]
        end_date = (end_dt or "")[:10]

        last_exc = None
        for attempt in range(MAX_RETRIES):
            try:
                rs = bs.query_history_k_data_plus(
                    full_symbol,
                    field_set,
                    start_date=start_date,
                    end_date=end_date,
                    frequency=bs_freq,
                    adjustflag=adjust_code,
                )
                if getattr(rs, "error_code", "0") != "0":
                    last_exc = RuntimeError(getattr(rs, "error_msg", ""))
                    if attempt < MAX_RETRIES - 1:
                        time.sleep(RETRY_SLEEP_SECONDS)
                        continue
                else:
                    records = []
                    while rs.next():
                        records.append(rs.get_row_data())
                    if records:
                        return self._map_minute_rows(
                            code, exchange, rs.fields, records, interval, adjust_flag
                        )
                    last_exc = RuntimeError(f"baostock 分钟线返回空: {full_symbol}")
            except Exception as exc:
                last_exc = exc
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_SLEEP_SECONDS)

        raise RuntimeError(
            f"baostock 分钟线查询失败 (已重试{MAX_RETRIES}次): {last_exc or full_symbol}"
        )

    def _map_minute_rows(
        self,
        code: str,
        exchange: str,
        columns: list[str],
        records: list[list[str]],
        interval: str,
        adjust_flag: str,
    ) -> list[dict]:
        mapped = []
        symbol = f"{code}.{exchange}"
        for row in records:
            item = dict(zip(columns, row))
            trade_datetime = _compose_baostock_minute_datetime(
                item.get("date"), item.get("time")
            )
            if trade_datetime is None:
                continue
            mapped.append(
                {
                    "symbol": symbol,
                    "code": code,
                    "exchange": exchange,
                    "trade_datetime": trade_datetime.isoformat(),
                    "trade_date": trade_datetime.date().isoformat(),
                    "interval": interval,
                    "adjust_flag": adjust_flag or "raw",
                    "open_price": to_float(item.get("open")),
                    "high_price": to_float(item.get("high")),
                    "low_price": to_float(item.get("low")),
                    "close_price": to_float(item.get("close")),
                    "volume": to_float(item.get("volume")),
                    "amount": to_float(item.get("amount")),
                    "source": self.provider_name,
                    "data_source_version": self.provider_version,
                }
            )
        return mapped


def _compose_baostock_minute_datetime(date_value, time_value) -> datetime | None:
    """baostock 分钟线 time 字段可能是 14 位紧凑格式（yyyymmddHHMMSS）或 HH:MM:SS。

    返回带本地时区无关的 datetime（naive）；上层序列化为 ISO 8601 字符串。
    """
    text = str(time_value or "").strip()
    if not text:
        return None
    if len(text) >= 14 and text[:14].isdigit():
        try:
            return datetime.strptime(text[:14], "%Y%m%d%H%M%S")
        except ValueError:
            pass
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            t = datetime.strptime(text, fmt).time()
            d = parse_trade_date(date_value)
            return datetime.combine(d, t)
        except ValueError:
            continue
    return None
