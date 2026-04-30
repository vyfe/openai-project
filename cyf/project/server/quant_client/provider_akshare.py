from __future__ import annotations

from quant_client.common import compact_date_text, infer_exchange, normalize_code, normalize_symbol, parse_trade_date, to_float
from quant_client.provider_base import BaseAshareProvider


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
            df = ak.stock_zh_a_hist(
                symbol=code,
                period="daily",
                start_date=compact_date_text(start_date),
                end_date=compact_date_text(end_date),
                adjust=adjust_flag if adjust_flag in ("", "qfq", "hfq") else "qfq",
            )
            if df is None or df.empty:
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

