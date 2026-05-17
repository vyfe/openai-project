from __future__ import annotations

import time

from quant_client.common import compact_date_text, infer_exchange, normalize_code, normalize_symbol, parse_trade_date, to_float
from quant_client.provider_base import BaseAshareProvider

MAX_RETRIES = 3
RETRY_SLEEP_SECONDS = 60


class AkshareAshareProvider(BaseAshareProvider):
    provider_name = "akshare"
    provider_version = "stock_zh_a_hist"

    def fetch_daily_bars(self, symbols: list[str], start_date: str, end_date: str, adjust_flag: str = "qfq") -> list[dict]:
        try:
            import akshare as ak
        except ImportError as exc:
            raise RuntimeError("未安装 akshare，请先安装依赖") from exc

        try:
            import pandas as pd  # noqa: F401
        except ImportError as exc:
            raise RuntimeError("未安装 pandas，请先安装依赖") from exc

        rows: list[dict] = []
        for raw_symbol in symbols:
            code = normalize_code(raw_symbol)
            exchange = infer_exchange(code)

            last_exc = None
            df = None
            for attempt in range(MAX_RETRIES):
                try:
                    df = ak.stock_zh_a_hist(
                        symbol=code,
                        period="daily",
                        start_date=compact_date_text(start_date),
                        end_date=compact_date_text(end_date),
                        adjust=adjust_flag if adjust_flag in ("", "qfq", "hfq") else "qfq",
                    )
                    if df is not None and not df.empty:
                        break
                    last_exc = RuntimeError(f"akshare 返回空数据: {code}")
                except Exception as exc:
                    last_exc = exc
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_SLEEP_SECONDS)

            if df is None or df.empty:
                if last_exc:
                    raise RuntimeError(f"akshare 请求失败 (已重试{MAX_RETRIES}次, symbol={code}): {last_exc}") from last_exc
                continue

            prev_close = None
            for item in df.to_dict(orient="records"):
                close_price = to_float(item.get("收盘"))
                preclose_price = to_float(item.get("昨收")) or prev_close
                raw_volume = to_float(item.get("成交量"))
                rows.append(
                    {
                        "symbol": normalize_symbol(code),
                        "code": code,
                        "exchange": exchange,
                        "trade_date": parse_trade_date(item.get("日期")).isoformat(),
                        "adjust_flag": adjust_flag or "raw",
                        "open_price": to_float(item.get("开盘")),
                        "high_price": to_float(item.get("最高")),
                        "low_price": to_float(item.get("最低")),
                        "close_price": close_price,
                        "preclose_price": preclose_price,
                        "volume": raw_volume * 100 if raw_volume is not None else None,
                        "amount": to_float(item.get("成交额")),
                        "turnover_rate": to_float(item.get("换手率")),
                        "pct_change": to_float(item.get("涨跌幅")),
                        "source": self.provider_name,
                        "data_source_version": self.provider_version,
                    }
                )
                prev_close = close_price
        return rows
