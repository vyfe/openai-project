"""Yahoo Finance 数据源 — 国际可访问，对沪深指数 + ETF 覆盖完整。

相比 baostock/tencent/sina，Yahoo 在指数（000001.SH / 000300.SH / 000688.SH）支持上
更稳；劣势是字段集较小（无 turnover_rate / amount），但 OHLCV + adjusted close 都有。

Yahoo Finance 命名规则：
  - 沪市股票 / 指数 → .SS（Shanghai Stock Exchange）
  - 深市股票 / 指数 → .SZ
  - 北交所 → 也用 .SS（Yahoo 不严格区分）

与本项目格式（.SH / .SZ / .BJ）的转换：用户输入 `000300.SH` → Yahoo `000300.SS`。
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Optional

from quant_client.common import resolve_market_info, to_float
from quant_client.provider_base import BaseAshareProvider

MAX_RETRIES = 3
RETRY_SLEEP_SECONDS = int(os.environ.get("QUANT_RETRY_SLEEP_SECONDS", "60"))

logger = logging.getLogger("quant.client.yahoo")

YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"


def _to_yahoo_symbol(raw_symbol: str) -> str:
    """Convert our `000300.SH` format to Yahoo's `000300.SS` format."""
    market = resolve_market_info(raw_symbol)
    if market.exchange == "SZ":
        return f"{market.code}.SZ"
    # SH 和 BJ 都映射为 .SS（Yahoo 不严格区分北交所）
    return f"{market.code}.SS"


class YfinanceAshareProvider(BaseAshareProvider):
    """Yahoo Finance 数据源：股票 + 指数 + ETF，国际可访问。"""

    provider_name = "yahoo"
    provider_version = "yahoo_chart_v8"

    def fetch_daily_bars(
        self,
        symbols: list[str],
        start_date: str,
        end_date: str,
        adjust_flag: str = "qfq",
    ) -> list[dict]:
        # Yahoo Chart API 用 Unix 时间戳（秒）
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
            end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError as exc:
            raise ValueError(f"日期格式错误，需 YYYY-MM-DD: {exc}") from exc
        period1 = int(time.mktime(start_dt.timetuple()))
        # +1 day 让 end_date 当天也包含
        period2 = int(time.mktime(end_dt.timetuple())) + 86400

        rows: list[dict] = []
        for raw_symbol in symbols:
            try:
                rows.extend(
                    self._fetch_one_symbol(raw_symbol, period1, period2, adjust_flag)
                )
            except Exception as exc:
                logger.warning(
                    "yahoo_symbol_failed symbol=%s err=%s", raw_symbol, exc,
                )
                continue
        return rows

    def _fetch_one_symbol(
        self,
        raw_symbol: str,
        period1: int,
        period2: int,
        adjust_flag: str,
    ) -> list[dict]:
        market = resolve_market_info(raw_symbol)
        code = market.code
        exchange = market.exchange
        yahoo_symbol = _to_yahoo_symbol(raw_symbol)

        params = {
            "period1": str(period1),
            "period2": str(period2),
            "interval": "1d",
            "events": "history",
        }
        url = f"{YAHOO_CHART_URL.format(ticker=yahoo_symbol)}?{urllib.parse.urlencode(params)}"

        payload = None
        last_exc: Optional[Exception] = None
        for attempt in range(MAX_RETRIES):
            try:
                req = urllib.request.Request(
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
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
                    raise RuntimeError(
                        f"Yahoo Finance 请求失败 (已重试{MAX_RETRIES}次): {last_exc}"
                    ) from last_exc

        if not payload:
            raise RuntimeError(f"Yahoo 返回空响应: {raw_symbol}")
        chart = payload.get("chart") or {}
        if chart.get("error"):
            err = chart["error"]
            raise RuntimeError(
                f"Yahoo 返回错误: {err.get('code', 'unknown')} - {err.get('description', '')}"
            )
        results = chart.get("result") or []
        if not results:
            raise RuntimeError(f"Yahoo 未返回 {raw_symbol} 的数据")
        result = results[0]
        meta = result.get("meta") or {}
        timestamps = result.get("timestamp") or []
        indicators = result.get("indicators") or {}
        quote = (indicators.get("quote") or [{}])[0]
        adj_block = (indicators.get("adjclose") or [{}])[0]
        adjclose_arr = adj_block.get("adjclose") or []

        # 优先用 adjclose 处理复权（Yahoo 的图表 API 默认同时给 raw 和 adjclose）
        use_adj = bool(adjclose_arr) and adjust_flag in ("qfq", "hfq")

        # Yahoo 原生 symbol（如 000300.SS），向前端/DB 透传时还原为我们的格式
        symbol = f"{code}.{exchange}"

        parsed = []
        prev_close = None
        for i, ts in enumerate(timestamps):
            trade_dt = datetime.fromtimestamp(int(ts)).date()
            open_price = self._pick(quote.get("open"), i)
            high_price = self._pick(quote.get("high"), i)
            low_price = self._pick(quote.get("low"), i)
            close_price = self._pick(quote.get("close"), i)
            volume = self._pick(quote.get("volume"), i)
            adj_close = self._pick(adjclose_arr, i)

            effective_close = adj_close if use_adj and adj_close is not None else close_price

            pct_change = None
            if prev_close not in (None, 0) and effective_close is not None:
                pct_change = (effective_close - prev_close) / prev_close * 100

            change = None
            if effective_close is not None and prev_close is not None:
                change = effective_close - prev_close

            adjust_flag_out = "qfq" if use_adj else "raw"
            if adjust_flag == "raw":
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
                "close_price": effective_close,
                "preclose_price": prev_close,
                "volume": volume,
                "amount": None,         # Yahoo 不提供
                "turnover_rate": None,  # Yahoo 不提供
                "pct_change": pct_change,
                "change": change,
                "source": self.provider_name,
                "data_source_version": self.provider_version,
            })
            prev_close = effective_close
        return parsed

    @staticmethod
    def _pick(arr, idx):
        """从 Yahoo 数组里安全取某下标值；Yahoo 用 null 填充缺失。"""
        if not arr or idx >= len(arr):
            return None
        return to_float(arr[idx])