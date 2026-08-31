from __future__ import annotations

import copy
import json
import math
from datetime import datetime
from typing import Iterable, Optional

from quant.db import quant_db
from quant.entities import QuantDailyBar, QuantDailyIndicator


INDICATOR_SET_VERSION = "v2"
DEFAULT_INDICATOR_WINDOWS = {
    "ma": [5, 10, 20, 60],
    "boll": [20],
    "macd": {"fast": 12, "slow": 26, "signal": 9},
    "kdj": {"n": 9, "k": 3, "d": 3},
}

TD_SEQUENTIAL_PARAMS = {
    "lookback_setup": 4,
    "lookback_countdown": 2,
    "max_setup": 9,
    "max_countdown": 13,
}

BOTTOM_STRUCTURE_PARAMS = {
    "lookback": 30,
    "min_consecutive": 2,
}

SUPPORTED_INDICATOR_GROUPS = ("ma", "boll", "macd", "kdj", "td_sequential", "bottom_structure")

# 各指标在请求周期下的最少前置 K 线根数。
# 调用方自行按 interval 换算成日历天 / 分钟数再去拉数据；这里只表达"算这个指标至少需要多少根 bar"。
INDICATOR_BASE_LOOKBACK = {
    "ma": 60,              # 默认含 MA60；自定义 params["ma_windows"] 走 max()
    "boll": 20,
    "macd": 26,            # slow 默认 26
    "kdj": 9,              # n 默认 9
    "td_sequential": 9,    # max_setup=9
    "bottom_structure": 30,
}


def max_lookback_bars(indicator_names=None, params=None) -> int:
    """根据请求的指标名 + 自定义参数，算出"为这次指标计算所需的最少 K 线根数"。

    返回的是 K 线根数（按请求周期的单位计），不是日历天也不是分钟。
    调用方负责按 interval 把根数换算成具体的 extended_start / start_dt 再 fetch bars。

    关键决策：
    - indicator_names 为 None → 当作"全开"，按全部指标取 max（最保险）
    - indicator_names 为 [] 显式空 → 返回最小值 1（无需前置 bar）
    - params["ma_windows"] 自定义时覆盖默认 [5, 10, 20, 60]
    - 至少返回 1
    """
    if indicator_names is None:
        names = set(INDICATOR_BASE_LOOKBACK.keys())
    else:
        names = set(indicator_names)
    params = params or {}
    base = 0
    for name in names:
        if name == "ma":
            windows = params.get("ma_windows") or DEFAULT_INDICATOR_WINDOWS["ma"]
            base = max(base, max(windows) if windows else 1)
        else:
            base = max(base, INDICATOR_BASE_LOOKBACK.get(name, 0))
    return max(base, 1)


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


def _resolve_indicator_params(params: Optional[dict]) -> dict:
    """Merge user params over DEFAULT_INDICATOR_WINDOWS (deep copy)."""
    merged = copy.deepcopy(DEFAULT_INDICATOR_WINDOWS)
    if not params:
        return merged
    if "ma_windows" in params:
        merged["ma"] = [int(item) for item in params["ma_windows"]]
    if "boll_window" in params:
        merged["boll"] = [int(params["boll_window"])]
    if "macd" in params and isinstance(params["macd"], dict):
        merged["macd"].update({k: int(v) for k, v in params["macd"].items()})
    if "kdj" in params and isinstance(params["kdj"], dict):
        merged["kdj"].update({k: int(v) for k, v in params["kdj"].items()})
    return merged


def _name_matches_group(name: str, groups: Iterable[str]) -> bool:
    lowered = name.lower()
    for group in groups:
        token = str(group).lower()
        if token == "ma" and lowered.startswith("ma_"):
            return True
        if token == "boll" and lowered.startswith("boll_"):
            return True
        if token == "macd" and lowered.startswith("macd_"):
            return True
        if token == "kdj" and lowered.startswith("kdj_"):
            return True
        if token == "td_sequential" and lowered.startswith("td_"):
            return True
        if token == "bottom_structure" and lowered == "bottom_divergence":
            return True
        if token == lowered:
            return True
    return False


def _date_key(date_value) -> str:
    if hasattr(date_value, "isoformat"):
        return date_value.isoformat()
    return str(date_value)


def _bar_sort_key(bar) -> str:
    """返回可比较的 bar 时间键；指标计算统一按旧到新排列。"""
    value = getattr(bar, "trade_datetime", None) or getattr(bar, "trade_date", None)
    return _date_key(value) if value is not None else ""


def _ordered_bars(bars: list) -> list:
    """复制并按时间升序排列 bars，兼容接口按新到旧返回的数据。"""
    ordered = list(bars or [])
    if len(ordered) < 2:
        return ordered
    keys = [_bar_sort_key(bar) for bar in ordered]
    if all(left <= right for left, right in zip(keys, keys[1:])):
        return ordered
    return sorted(ordered, key=_bar_sort_key)


def _compute_indicator_snapshot(bars: list[QuantDailyBar], params: Optional[dict] = None) -> list[dict]:
    bars = _ordered_bars(bars)
    windows = _resolve_indicator_params(params)
    ma_windows = windows["ma"] or []
    boll_window = windows["boll"][0] if windows.get("boll") else 20
    fast = windows["macd"]["fast"]
    slow = windows["macd"]["slow"]
    signal = windows["macd"]["signal"]
    kdj_n = windows["kdj"]["n"]
    kdj_k = windows["kdj"]["k"]
    kdj_d = windows["kdj"]["d"]

    snapshots = []
    for idx, bar in enumerate(bars):
        if bar.close_price is None:
            continue
        history_closes = [float(item.close_price) for item in bars[: idx + 1] if item.close_price is not None]
        ma_values = {}
        for window in ma_windows:
            ma_value = _sma(history_closes, window)
            ma_values[f"ma_{window}"] = round(ma_value, 6) if ma_value is not None else None
        boll_mid = _sma(history_closes, boll_window)
        boll_std = _std(history_closes, boll_window)
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


def compute_indicators(bars: list, indicator_names: Optional[Iterable[str]] = None, params: Optional[dict] = None) -> dict:
    """无状态纯计算：输入 bars 序列（duck type），返回 {date_str: {indicator_name: value}}。

    indicator_names: None 表示返回全部默认指标（MA/BOLL/MACD/KDJ/TD/底部结构）；
                     可传组名（"ma"/"macd"/"kdj"/"boll"/"td_sequential"/"bottom_structure"）
                     或具体字段名（"ma_5"/"macd_dif"/...）混合过滤
    params: 可覆盖默认窗口（ma_windows / boll_window / macd / kdj）
    """
    if not bars:
        return {}
    bars = _ordered_bars(bars)
    snapshots = _compute_indicator_snapshot(bars, params=params)
    td_snapshot = compute_td_sequential(bars)
    bottom_snapshot = compute_bottom_structure(bars)

    name_filter = [str(n).lower() for n in indicator_names] if indicator_names else None
    result: dict = {}
    for snap in snapshots:
        date_key = _date_key(snap["bar"].trade_date)
        row: dict = {}
        for k, v in snap["value"].items():
            if v is None:
                continue
            if name_filter is not None and not _name_matches_group(k, name_filter):
                continue
            row[k] = v
        td_row = td_snapshot.get(date_key, {})
        for tk, tv in td_row.items():
            if tv is None or tv is False:
                continue
            if name_filter is not None and not _name_matches_group(tk, name_filter):
                continue
            row[tk] = tv
        bot_row = bottom_snapshot.get(date_key, {})
        if bot_row.get("bottom_divergence"):
            if name_filter is None or "bottom_structure" in name_filter or "bottom_divergence" in name_filter:
                row["bottom_divergence"] = True
                if not row.get("td_signal") and bot_row.get("td_signal"):
                    row["td_signal"] = bot_row["td_signal"]
        result[date_key] = row
    return result


def compute_td_sequential(
    bars: list,
    lookback_setup: int = TD_SEQUENTIAL_PARAMS["lookback_setup"],
    lookback_countdown: int = TD_SEQUENTIAL_PARAMS["lookback_countdown"],
    max_setup: int = TD_SEQUENTIAL_PARAMS["max_setup"],
    max_countdown: int = TD_SEQUENTIAL_PARAMS["max_countdown"],
) -> dict:
    """神奇九转（TD Sequential）的日线 9-13 基础实现。

    返回 {date_str: {td_buy_setup, td_buy_countdown, td_sell_setup, td_sell_countdown, td_signal}}
    其中 td_signal ∈ {None, "buy_setup_complete", "buy_countdown_complete", "sell_setup_complete", "sell_countdown_complete"}

    Setup 使用收盘价与 4 根前收盘价比较，连续满足 9 根完成 Setup；
    Countdown 从 Setup 完成后的下一根开始，买入 Countdown 使用
    close <= low[i-2]，卖出 Countdown 使用 close >= high[i-2]，允许不连续计数。
    这比把接口返回的新到旧顺序直接当作时间序列更接近常见 TD Sequential 定义。
    """
    if not bars:
        return {}

    bars = _ordered_bars(bars)
    result: dict = {}
    buy_setup = 0
    sell_setup = 0
    buy_setup_completed = False
    sell_setup_completed = False
    buy_setup_index = -1
    sell_setup_index = -1
    buy_countdown_active = False
    sell_countdown_active = False
    buy_countdown = 0
    sell_countdown = 0

    for i, bar in enumerate(bars):
        row: dict = {"td_signal": None}
        signal = None

        bar_close = getattr(bar, "close_price", None)
        ref_close = bars[i - lookback_setup].close_price if i >= lookback_setup else None
        buy_setup_just_completed = False
        sell_setup_just_completed = False

        # Buy setup：条件不满足时只重置当前 setup，已开始的 countdown 不回退。
        if i < lookback_setup or bar_close is None or ref_close is None or bar_close >= ref_close:
            buy_setup = 0
            buy_setup_completed = False
        elif not buy_setup_completed:
            buy_setup = min(buy_setup + 1, max_setup)
            if buy_setup == max_setup:
                buy_setup_completed = True
                buy_setup_just_completed = True
                buy_setup_index = i
                buy_countdown_active = True
                buy_countdown = 0
                signal = "buy_setup_complete"

        # Buy countdown：比较 2 根前的最低价，失败时跳过该根而不是清零。
        if (
            buy_countdown_active
            and i > buy_setup_index
            and i >= lookback_countdown
            and bar_close is not None
            and bars[i - lookback_countdown].low_price is not None
            and bar_close <= bars[i - lookback_countdown].low_price
        ):
            buy_countdown = min(buy_countdown + 1, max_countdown)
            if buy_countdown == max_countdown:
                signal = signal or "buy_countdown_complete"
                buy_countdown_active = False

        row["td_buy_setup"] = buy_setup if buy_setup > 0 and (not buy_setup_completed or buy_setup_just_completed) else None
        row["td_buy_countdown"] = buy_countdown if buy_countdown > 0 else None

        # Sell setup：与 buy setup 对称。
        if i < lookback_setup or bar_close is None or ref_close is None or bar_close <= ref_close:
            sell_setup = 0
            sell_setup_completed = False
        elif not sell_setup_completed:
            sell_setup = min(sell_setup + 1, max_setup)
            if sell_setup == max_setup:
                sell_setup_completed = True
                sell_setup_just_completed = True
                sell_setup_index = i
                sell_countdown_active = True
                sell_countdown = 0
                signal = signal or "sell_setup_complete"

        # Sell countdown：比较 2 根前的最高价，允许不连续计数。
        if (
            sell_countdown_active
            and i > sell_setup_index
            and i >= lookback_countdown
            and bar_close is not None
            and bars[i - lookback_countdown].high_price is not None
            and bar_close >= bars[i - lookback_countdown].high_price
        ):
            sell_countdown = min(sell_countdown + 1, max_countdown)
            if sell_countdown == max_countdown:
                signal = signal or "sell_countdown_complete"
                sell_countdown_active = False

        row["td_sell_setup"] = sell_setup if sell_setup > 0 and (not sell_setup_completed or sell_setup_just_completed) else None
        row["td_sell_countdown"] = sell_countdown if sell_countdown > 0 else None
        row["td_signal"] = signal

        result[_date_key(bar.trade_date)] = row

    return result


def compute_bottom_structure(
    bars: list,
    macd_dif_series: Optional[list] = None,
    lookback: int = BOTTOM_STRUCTURE_PARAMS["lookback"],
    min_consecutive: int = BOTTOM_STRUCTURE_PARAMS["min_consecutive"],
) -> dict:
    """底部结构（最简实现：底背离）。

    判定条件：
    - 价格创新低：bars[i].low_price 是 [i-lookback, i) 区间的最低
    - DIF 未创新低：macd_dif_series[i] 高于该区间最低
    - 连续 >= min_consecutive 根

    返回 {date_str: {bottom_divergence: bool, td_signal: "bottom_divergence" or None}}
    """
    if not bars:
        return {}

    bars = _ordered_bars(bars)
    dif_map: dict = {}
    if macd_dif_series is None:
        snapshot = _compute_indicator_snapshot(bars, params={"ma_windows": [], "boll_window": 20})
        dif_map = {_date_key(item["bar"].trade_date): item["value"].get("macd_dif") for item in snapshot}
    else:
        for bar, val in zip(bars, macd_dif_series):
            dif_map[_date_key(bar.trade_date)] = val

    result: dict = {}
    consecutive = 0
    for i, bar in enumerate(bars):
        row = {"bottom_divergence": False, "td_signal": None}
        bar_low = getattr(bar, "low_price", None)
        if i >= lookback and bar_low is not None:
            price_window = [bars[j].low_price for j in range(i - lookback, i) if bars[j].low_price is not None]
            dif_window = [dif_map.get(_date_key(bars[j].trade_date)) for j in range(i - lookback, i)]
            dif_window = [v for v in dif_window if v is not None]
            if price_window and dif_window:
                price_low = min(price_window)
                dif_low = min(dif_window)
                dif_now = dif_map.get(_date_key(bar.trade_date))
                if dif_now is not None and bar_low <= price_low and dif_now > dif_low:
                    consecutive += 1
                    if consecutive >= min_consecutive:
                        row["bottom_divergence"] = True
                        row["td_signal"] = "bottom_divergence"
                else:
                    consecutive = 0

        result[_date_key(bar.trade_date)] = row

    return result


def compute_all_indicators(bars: list, indicator_names: Optional[Iterable[str]] = None, params: Optional[dict] = None) -> dict:
    """聚合入口（已弃用，请直接使用 compute_indicators）。"""
    return compute_indicators(bars, indicator_names=indicator_names, params=params)


def _indicator_records_for_symbol(
    symbol: str,
    adjust_flag: str,
    bars: list[QuantDailyBar],
    indicator_groups: Optional[Iterable[str]] = None,
) -> list[dict]:
    if not bars:
        return []
    snapshots = _compute_indicator_snapshot(bars)
    records = []
    bar_index = {id(bar): idx + 1 for idx, bar in enumerate(bars)}
    for snapshot in snapshots:
        bar = snapshot["bar"]
        value = snapshot["value"]
        for name, payload in value.items():
            if payload is None:
                continue
            if indicator_groups and not _name_matches_group(name, indicator_groups):
                continue
            records.append(
                {
                    "symbol": bar.symbol,
                    "code": bar.code,
                    "exchange": bar.exchange,
                    "trade_date": bar.trade_date,
                    "adjust_flag": adjust_flag,
                    "indicator_name": name,
                    "indicator_version": INDICATOR_SET_VERSION,
                    "params_json": json.dumps(DEFAULT_INDICATOR_WINDOWS, ensure_ascii=False),
                    "value_json": json.dumps({"value": payload}, ensure_ascii=False),
                    "source_bar_count": bar_index.get(id(bar), 0),
                    "source_run_id": bar.source_run_id or "",
                    "data_source_version": bar.data_source_version or "",
                    "created_at": datetime.now(),
                    "updated_at": datetime.now(),
                }
            )
    return records


def _td_records_for_symbol(symbol: str, adjust_flag: str, bars: list[QuantDailyBar]) -> list[dict]:
    td_results = compute_td_sequential(bars)
    if not td_results:
        return []
    bar_index = {id(bar): idx + 1 for idx, bar in enumerate(bars)}
    records = []
    td_counters = ("td_buy_setup", "td_buy_countdown", "td_sell_setup", "td_sell_countdown")
    for bar in bars:
        date_key = _date_key(bar.trade_date)
        td = td_results.get(date_key)
        if not td:
            continue
        for name in td_counters:
            value = td.get(name)
            if value is None:
                continue
            records.append(
                {
                    "symbol": bar.symbol,
                    "code": bar.code,
                    "exchange": bar.exchange,
                    "trade_date": bar.trade_date,
                    "adjust_flag": adjust_flag,
                    "indicator_name": name,
                    "indicator_version": INDICATOR_SET_VERSION,
                    "params_json": json.dumps(TD_SEQUENTIAL_PARAMS, ensure_ascii=False),
                    "value_json": json.dumps({"value": value}, ensure_ascii=False),
                    "source_bar_count": bar_index.get(id(bar), 0),
                    "source_run_id": bar.source_run_id or "",
                    "data_source_version": bar.data_source_version or "",
                    "created_at": datetime.now(),
                    "updated_at": datetime.now(),
                }
            )
        signal = td.get("td_signal")
        if signal:
            records.append(
                {
                    "symbol": bar.symbol,
                    "code": bar.code,
                    "exchange": bar.exchange,
                    "trade_date": bar.trade_date,
                    "adjust_flag": adjust_flag,
                    "indicator_name": "td_signal",
                    "indicator_version": INDICATOR_SET_VERSION,
                    "params_json": json.dumps(TD_SEQUENTIAL_PARAMS, ensure_ascii=False),
                    "value_json": json.dumps({"value": signal}, ensure_ascii=False),
                    "source_bar_count": bar_index.get(id(bar), 0),
                    "source_run_id": bar.source_run_id or "",
                    "data_source_version": bar.data_source_version or "",
                    "created_at": datetime.now(),
                    "updated_at": datetime.now(),
                }
            )
    return records


def _bottom_records_for_symbol(symbol: str, adjust_flag: str, bars: list[QuantDailyBar]) -> list[dict]:
    bottom_results = compute_bottom_structure(bars)
    if not bottom_results:
        return []
    bar_index = {id(bar): idx + 1 for idx, bar in enumerate(bars)}
    records = []
    for bar in bars:
        date_key = _date_key(bar.trade_date)
        row = bottom_results.get(date_key)
        if not row or not row.get("bottom_divergence"):
            continue
        records.append(
            {
                "symbol": bar.symbol,
                "code": bar.code,
                "exchange": bar.exchange,
                "trade_date": bar.trade_date,
                "adjust_flag": adjust_flag,
                "indicator_name": "bottom_divergence",
                "indicator_version": INDICATOR_SET_VERSION,
                "params_json": json.dumps(BOTTOM_STRUCTURE_PARAMS, ensure_ascii=False),
                "value_json": json.dumps({"value": True}, ensure_ascii=False),
                "source_bar_count": bar_index.get(id(bar), 0),
                "source_run_id": bar.source_run_id or "",
                "data_source_version": bar.data_source_version or "",
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
            }
        )
    return records


def upsert_daily_indicators(
    symbols: list[str],
    adjust_flag: str = "qfq",
    trade_date=None,
    indicator_names: Optional[Iterable[str]] = None,
) -> dict:
    """批量写入 QuantDailyIndicator 表。

    indicator_names: 可选过滤（白名单）；None = 全部指标组（MA/BOLL/MACD/KDJ/TD/底部结构）
    """
    if not symbols:
        return {"symbols": [], "records": 0}
    target_date = trade_date or datetime.now().date()
    group_filter = list(indicator_names) if indicator_names else None
    wants_basic = group_filter is None or bool({"ma", "boll", "macd", "kdj"} & {g.lower() for g in group_filter})
    wants_td = group_filter is None or "td_sequential" in {g.lower() for g in group_filter}
    wants_bottom = group_filter is None or "bottom_structure" in {g.lower() for g in group_filter}

    all_records: list[dict] = []
    for symbol in symbols:
        bars = _load_bars(symbol, adjust_flag, target_date)
        if not bars:
            continue
        if wants_basic:
            all_records.extend(_indicator_records_for_symbol(symbol, adjust_flag, bars, group_filter))
        if wants_td:
            all_records.extend(_td_records_for_symbol(symbol, adjust_flag, bars))
        if wants_bottom:
            all_records.extend(_bottom_records_for_symbol(symbol, adjust_flag, bars))

    if not all_records:
        return {"symbols": symbols, "records": 0}

    with quant_db.atomic():
        for chunk_start in range(0, len(all_records), 500):
            chunk = all_records[chunk_start: chunk_start + 500]
            QuantDailyIndicator.insert_many(chunk).on_conflict_replace().execute()
    return {"symbols": symbols, "records": len(all_records)}


def list_daily_indicators(
    symbol: Optional[str] = None,
    trade_date=None,
    indicator_name: Optional[str] = None,
    limit: int = 500,
    indicator_version: Optional[str] = None,
) -> list[dict]:
    query = QuantDailyIndicator.select().order_by(QuantDailyIndicator.trade_date.desc(), QuantDailyIndicator.id.desc())
    if symbol:
        query = query.where(QuantDailyIndicator.symbol == symbol)
    if trade_date:
        query = query.where(QuantDailyIndicator.trade_date == trade_date)
    if indicator_name:
        query = query.where(QuantDailyIndicator.indicator_name == indicator_name)
    if indicator_version:
        query = query.where(QuantDailyIndicator.indicator_version == indicator_version)
    query = query.limit(limit)
    return [item.to_dict() for item in query.iterator()]
