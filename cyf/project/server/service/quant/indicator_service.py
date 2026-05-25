from __future__ import annotations

import json
import math
from datetime import datetime
from typing import Iterable, Optional

from quant.db import quant_db
from quant.entities import QuantDailyBar, QuantDailyIndicator


INDICATOR_SET_VERSION = "v1"
DEFAULT_INDICATOR_WINDOWS = {
    "ma": [5, 10, 20, 60],
    "boll": [20],
    "macd": {"fast": 12, "slow": 26, "signal": 9},
    "kdj": {"n": 9, "k": 3, "d": 3},
}


def _rows_to_dicts(rows) -> list[dict]:
    return [item.to_dict() for item in rows]


def _load_bars(symbol: str, adjust_flag: str, end_date, limit: int = 5000) -> list[QuantDailyBar]:
    query = (
        QuantDailyBar.select()
        .where(
            (QuantDailyBar.symbol == symbol)
            & (QuantDailyBar.adjust_flag == adjust_flag)
            & (QuantDailyBar.trade_date <= end_date)
        )
        .order_by(QuantDailyBar.trade_date.asc(), QuantDailyBar.id.asc())
        .limit(limit)
    )
    return list(query.iterator())


def _sma(values: list[float], window: int) -> Optional[float]:
    if len(values) < window:
        return None
    sample = values[-window:]
    return sum(sample) / window


def _std(values: list[float], window: int) -> Optional[float]:
    if len(values) < window:
        return None
    sample = values[-window:]
    mean = sum(sample) / window
    variance = sum((item - mean) ** 2 for item in sample) / window
    return math.sqrt(variance)


def _ema_series(values: list[float], span: int) -> list[float]:
    if not values:
        return []
    alpha = 2 / (span + 1)
    series = [values[0]]
    for value in values[1:]:
        series.append(series[-1] * (1 - alpha) + value * alpha)
    return series


def _macd(values: list[float], fast: int, slow: int, signal: int) -> tuple[Optional[float], Optional[float], Optional[float]]:
    if len(values) < slow:
        return None, None, None
    ema_fast = _ema_series(values, fast)
    ema_slow = _ema_series(values, slow)
    offset = len(ema_fast) - len(ema_slow)
    if offset > 0:
        ema_fast = ema_fast[offset:]
    elif offset < 0:
        ema_slow = ema_slow[-offset:]
    diffs = [a - b for a, b in zip(ema_fast, ema_slow)]
    dea_series = _ema_series(diffs, signal)
    if not diffs or not dea_series:
        return None, None, None
    diff = diffs[-1]
    dea = dea_series[-1]
    macd = (diff - dea) * 2
    return diff, dea, macd


def _kdj(bars: list[QuantDailyBar], n: int, k_period: int, d_period: int) -> tuple[Optional[float], Optional[float], Optional[float]]:
    if len(bars) < n:
        return None, None, None
    k_value = 50.0
    d_value = 50.0
    for idx in range(len(bars)):
        window = bars[max(0, idx - n + 1): idx + 1]
        closes = [item.close_price for item in window if item.close_price is not None]
        highs = [item.high_price for item in window if item.high_price is not None]
        lows = [item.low_price for item in window if item.low_price is not None]
        if not closes or not highs or not lows:
            continue
        high_max = max(highs)
        low_min = min(lows)
        close = closes[-1]
        rsv = 50.0 if high_max == low_min else (close - low_min) / (high_max - low_min) * 100
        k_value = (k_period - 1) / k_period * k_value + 1 / k_period * rsv
        d_value = (d_period - 1) / d_period * d_value + 1 / d_period * k_value
    j_value = 3 * k_value - 2 * d_value
    return round(k_value, 4), round(d_value, 4), round(j_value, 4)


def _compute_indicator_snapshot(bars: list[QuantDailyBar]) -> list[dict]:
    closes = [float(item.close_price) for item in bars if item.close_price is not None]
    snapshots = []
    fast = DEFAULT_INDICATOR_WINDOWS["macd"]["fast"]
    slow = DEFAULT_INDICATOR_WINDOWS["macd"]["slow"]
    signal = DEFAULT_INDICATOR_WINDOWS["macd"]["signal"]
    kdj_n = DEFAULT_INDICATOR_WINDOWS["kdj"]["n"]
    kdj_k = DEFAULT_INDICATOR_WINDOWS["kdj"]["k"]
    kdj_d = DEFAULT_INDICATOR_WINDOWS["kdj"]["d"]

    for idx, bar in enumerate(bars):
        if bar.close_price is None:
            continue
        history_closes = [float(item.close_price) for item in bars[: idx + 1] if item.close_price is not None]
        ma_values = {f"ma_{window}": round(_sma(history_closes, window), 6) if _sma(history_closes, window) is not None else None for window in DEFAULT_INDICATOR_WINDOWS["ma"]}
        boll_mid = _sma(history_closes, 20)
        boll_std = _std(history_closes, 20)
        diff, dea, macd = _macd(history_closes, fast, slow, signal)
        k_value, d_value, j_value = _kdj(bars[: idx + 1], kdj_n, kdj_k, kdj_d)

        snapshots.append(
            {
                "bar": bar,
                "value": {
                    **ma_values,
                    "boll_mid": round(boll_mid, 6) if boll_mid is not None else None,
                    "boll_upper": round(boll_mid + 2 * boll_std, 6) if boll_mid is not None and boll_std is not None else None,
                    "boll_lower": round(boll_mid - 2 * boll_std, 6) if boll_mid is not None and boll_std is not None else None,
                    "macd_dif": round(diff, 6) if diff is not None else None,
                    "macd_dea": round(dea, 6) if dea is not None else None,
                    "macd_bar": round(macd, 6) if macd is not None else None,
                    "kdj_k": k_value,
                    "kdj_d": d_value,
                    "kdj_j": j_value,
                },
            }
        )
    return snapshots


def _indicator_records_for_symbol(symbol: str, adjust_flag: str, trade_date=None) -> list[dict]:
    bars = _load_bars(symbol, adjust_flag, trade_date or datetime.now().date())
    if not bars:
        return []
    snapshots = _compute_indicator_snapshot(bars)
    records = []
    for snapshot in snapshots:
        bar = snapshot["bar"]
        value = snapshot["value"]
        for name, payload in value.items():
            if payload is None:
                continue
            records.append(
                {
                    "symbol": bar.symbol,
                    "code": bar.code,
                    "exchange": bar.exchange,
                    "trade_date": bar.trade_date,
                    "adjust_flag": bar.adjust_flag,
                    "indicator_name": name,
                    "indicator_version": INDICATOR_SET_VERSION,
                    "params_json": json.dumps(DEFAULT_INDICATOR_WINDOWS, ensure_ascii=False),
                    "value_json": json.dumps({"value": payload}, ensure_ascii=False),
                    "source_bar_count": len(bars[: bars.index(bar) + 1]),
                    "source_run_id": bar.source_run_id or "",
                    "data_source_version": bar.data_source_version or "",
                    "created_at": datetime.now(),
                    "updated_at": datetime.now(),
                }
            )
    return records


def upsert_daily_indicators(symbols: list[str], adjust_flag: str = "qfq", trade_date=None) -> dict:
    if not symbols:
        return {"symbols": [], "records": 0}
    target_date = trade_date or datetime.now().date()
    all_records = []
    for symbol in symbols:
        all_records.extend(_indicator_records_for_symbol(symbol, adjust_flag, target_date))

    if not all_records:
        return {"symbols": symbols, "records": 0}

    with quant_db.atomic():
        for chunk_start in range(0, len(all_records), 500):
            chunk = all_records[chunk_start: chunk_start + 500]
            QuantDailyIndicator.insert_many(chunk).on_conflict_replace().execute()
    return {"symbols": symbols, "records": len(all_records)}


def list_daily_indicators(symbol: Optional[str] = None, trade_date=None, indicator_name: Optional[str] = None, limit: int = 500) -> list[dict]:
    query = QuantDailyIndicator.select().order_by(QuantDailyIndicator.trade_date.desc(), QuantDailyIndicator.id.desc())
    if symbol:
        query = query.where(QuantDailyIndicator.symbol == symbol)
    if trade_date:
        query = query.where(QuantDailyIndicator.trade_date == trade_date)
    if indicator_name:
        query = query.where(QuantDailyIndicator.indicator_name == indicator_name)
    query = query.limit(limit)
    return [item.to_dict() for item in query.iterator()]
