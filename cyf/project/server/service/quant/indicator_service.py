from __future__ import annotations

import copy
import json
import math
from datetime import datetime
from typing import Iterable, Optional

from quant.db import quant_db
from quant.entities import QuantDailyBar, QuantDailyIndicator
from service.quant import indicator_registry as ireg


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

TOP_STRUCTURE_PARAMS = {
    "lookback": 30,
    "min_consecutive": 2,
}

SUPPORTED_INDICATOR_GROUPS = (
    "ma", "boll", "macd", "kdj", "td_sequential", "bottom_structure", "top_structure",
)

# 各指标在请求周期下的最少前置 K 线根数。
# 调用方自行按 interval 换算成日历天 / 分钟数再去拉数据；这里只表达"算这个指标至少需要多少根 bar"。
INDICATOR_BASE_LOOKBACK = {
    "ma": 60,              # 默认含 MA60；自定义 params["ma_windows"] 走 max()
    "boll": 20,
    "macd": 26,            # slow 默认 26
    "kdj": 9,              # n 默认 9
    "td_sequential": 9,    # max_setup=9
    "bottom_structure": 30,
    "top_structure": 30,
}


def max_lookback_bars(indicator_names=None, params=None) -> int:
    """根据请求的指标名 + 自定义参数，算出"为这次指标计算所需的最少 K 线根数"。

    返回的是 K 线根数（按请求周期的单位计），不是日历天也不是分钟。
    调用方负责按 interval 把根数换算成具体的 extended_start / start_dt 再 fetch bars。

    关键决策：
    - indicator_names 为 None → 当作"全开"，按全部指标取 max（最保险）
    - indicator_names 为 [] 显式空 → 返回最小值 1（无需前置 bar）
    - params 自定义时（如 ma_windows）按 registry 的 params 解析
    - 至少返回 1

    数值与历史完全一致：INDICATOR_BASE_LOOKBACK 的语义迁到 indicator_registry，
    老的"ma 默认 60"靠 ma 注册时的 base_lookback=60 保证。
    """
    if indicator_names is None:
        names = set(ireg.all_keys())
    else:
        names = set(indicator_names)
    params = params or {}
    base = 0
    for name in names:
        try:
            spec = ireg.get_spec(name)
        except KeyError:
            continue
        if name == "ma":
            windows = params.get("ma_windows") or list(spec.params[0].default)
            base = max(base, max(windows) if windows else 1)
        else:
            base = max(base, spec.base_lookback)
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
        if token == "top_structure" and lowered == "top_divergence":
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


def compute_vol_ratio(bars: list, window: int = 5) -> dict[str, list]:
    """量比：当前成交量 / 前 N 根平均成交量。bars 任意顺序，返回与 bars 对齐。

    返回 {f"vol_ratio_{window}": list[float|None]}。
    语义与 rule_engine._evaluate_one_rule 的 volume_ratio 分支对齐：
    - 平均分母用清洗 None 后的有效值个数，与 v1 `_avg` 行为一致；
    - 当前 bar 自身为 None 或 0 → 返回 None。
    """
    n = len(bars)
    result: list[Optional[float]] = [None] * n
    for i in range(n):
        if i + window >= n:
            break
        vols = [getattr(bars[i + j + 1], "volume", None) for j in range(window)]
        clean = [v for v in vols if v is not None]
        cur = getattr(bars[i], "volume", None)
        if not clean or cur is None or cur == 0:
            continue
        avg = sum(clean) / len(clean)
        if avg > 0:
            result[i] = cur / avg
    return {f"vol_ratio_{window}": result}


def compute_period_return(bars: list, lookback: int = 5) -> dict[str, list]:
    """区间收益率（百分比）：(close[i] / close[i+lookback] - 1) * 100。

    返回 {f"period_return_{lookback}": list[float|None]}。i + lookback 越界时为 None。
    """
    n = len(bars)
    result: list[Optional[float]] = [None] * n
    for i in range(n):
        if i + lookback >= n:
            break
        cur = getattr(bars[i], "close_price", None)
        past = getattr(bars[i + lookback], "close_price", None)
        if cur is None or past in (None, 0):
            continue
        result[i] = (cur - past) / past * 100
    return {f"period_return_{lookback}": result}


def compute_rolling_high_low(bars: list, window: int = 20) -> dict[str, list]:
    """N 根前最高/最低（**排除当前 bar**，与 v1 _breakout_high 语义对齐）。

    返回 {"rolling_high_{w}": [...], "rolling_low_{w}": [...]}。
    语义与 rule_engine._breakout_high 对齐：忽略 None，按实际有效值取 max/min。
    """
    n = len(bars)
    highs: list[Optional[float]] = [None] * n
    lows: list[Optional[float]] = [None] * n
    for i in range(n):
        if i + window >= n:
            break
        prior_h = [getattr(bars[i + j + 1], "high_price", None) for j in range(window)]
        prior_h = [v for v in prior_h if v is not None]
        if prior_h:
            highs[i] = max(prior_h)
        prior_l = [getattr(bars[i + j + 1], "low_price", None) for j in range(window)]
        prior_l = [v for v in prior_l if v is not None]
        if prior_l:
            lows[i] = min(prior_l)
    return {f"rolling_high_{window}": highs, f"rolling_low_{window}": lows}


def compute_rsi(bars: list, window: int = 14) -> dict[str, list]:
    """RSI 相对强弱指标（N 日，Wilder 平滑）。

    返回 {f"rsi_{window}": list[float|None]}，长度 = len(bars)，顺序与 bars 对齐。
    bars 数不足 window+1 → 全 None；窗口内 avg_loss == 0 → 100.0。
    方向语义：bars[i] 与 bars[i+1] 的差；引擎统一按调用方传入的顺序消费。
    第一个能算 RSI 的位置是 first_valid = n - window - 1（最旧先出窗口，
    从该位置向最新方向递推：每次滑入更靠近 i=0 的"更新"数据）。
    """
    n = len(bars)
    out: list[Optional[float]] = [None] * n
    if n <= window:
        return {f"rsi_{window}": out}

    diffs: list[Optional[float]] = [None] * n
    for i in range(n - 1):
        cur = getattr(bars[i], "close_price", None)
        prev = getattr(bars[i + 1], "close_price", None)
        if cur is None or prev in (None, 0):
            continue
        diffs[i] = cur - prev

    gains = [(d if d > 0 else 0.0) if d is not None else None for d in diffs]
    losses = [(-d if d < 0 else 0.0) if d is not None else None for d in diffs]

    # 第一个能算 RSI 的位置：i 位置需要 diffs[i..i+window-1] 全存在
    first_valid = n - window - 1
    if first_valid < 0:
        return {f"rsi_{window}": out}

    init_gains = [gains[j] for j in range(first_valid, first_valid + window) if gains[j] is not None]
    init_losses = [losses[j] for j in range(first_valid, first_valid + window) if losses[j] is not None]
    if not init_gains and not init_losses:
        return {f"rsi_{window}": out}
    # 首次均值按有效值数量作分母（兼容 None 边界）；
    # 之后递推保持 window 不变（Wilder 标准语义）。
    init_count = max(len(init_gains), len(init_losses), 1)
    avg_gain = sum(init_gains) / init_count if init_gains else 0.0
    avg_loss = sum(init_losses) / init_count if init_losses else 0.0

    out[first_valid] = (
        100.0 if avg_loss == 0 else round(100 - 100 / (1 + avg_gain / avg_loss), 6)
    )

    # 从 first_valid - 1 向 0 递推（Wilder 平滑：滑入 gains[i]）
    for i in range(first_valid - 1, -1, -1):
        g = gains[i] or 0.0
        l = losses[i] or 0.0
        avg_gain = (avg_gain * (window - 1) + g) / window
        avg_loss = (avg_loss * (window - 1) + l) / window
        out[i] = (
            100.0 if avg_loss == 0 else round(100 - 100 / (1 + avg_gain / avg_loss), 6)
        )
    return {f"rsi_{window}": out}


def compute_atr(bars: list, window: int = 14) -> dict[str, list]:
    """ATR 平均真实波幅（N 日，Wilder 平滑）。

    True Range = max(high-low, |high-prev_close|, |low-prev_close|)。
    最后一根（最旧）没有 prev_close → 退化为 |high-low|。
    返回 {f"atr_{window}": list[float|None]}，长度 = len(bars)。
    第一个能算 ATR 的位置 first_valid = n - window - 1（最旧先出窗口，向最新递推）。
    """
    n = len(bars)
    out: list[Optional[float]] = [None] * n
    if n < window + 1:
        return {f"atr_{window}": out}

    tr: list[Optional[float]] = [None] * n
    for i in range(n - 1):
        high = getattr(bars[i], "high_price", None)
        low = getattr(bars[i], "low_price", None)
        prev_close = getattr(bars[i + 1], "close_price", None)
        if high is None or low is None:
            continue
        hl = high - low
        candidates: list[float] = [abs(hl)]
        if prev_close is not None:
            candidates.append(abs(high - prev_close))
            candidates.append(abs(low - prev_close))
        tr[i] = max(candidates)
    # 最后一根（最旧）退化为 |high-low|
    if n > 0:
        last_high = getattr(bars[n - 1], "high_price", None)
        last_low = getattr(bars[n - 1], "low_price", None)
        if last_high is not None and last_low is not None:
            tr[n - 1] = abs(last_high - last_low)

    first_valid = n - window - 1
    if first_valid < 0:
        return {f"atr_{window}": out}
    init_tr = [tr[j] for j in range(first_valid, first_valid + window) if tr[j] is not None]
    if len(init_tr) < window:
        return {f"atr_{window}": out}
    avg = sum(init_tr) / window
    out[first_valid] = round(avg, 6)

    for i in range(first_valid - 1, -1, -1):
        prev = tr[i]
        if prev is None:
            continue
        avg = (avg * (window - 1) + prev) / window
        out[i] = round(avg, 6)
    return {f"atr_{window}": out}


def compute_obv(bars: list) -> dict[str, list]:
    """OBV 能量潮（无窗口参数）。

    bars[i].close > bars[i+1].close → volume[i 全量累加；反之扣减；相等不加。
    返回 {"obv": list[float|None]}，长度 = len(bars)；
    第 0 根（最早）没有 prev_close → None。后续为滚动累计值。
    """
    n = len(bars)
    out: list[Optional[float]] = [None] * n
    if n < 2:
        return {"obv": out}

    running = 0.0
    started = False
    for i in range(n - 1):
        cur_close = getattr(bars[i], "close_price", None)
        prev_close = getattr(bars[i + 1], "close_price", None)
        vol = getattr(bars[i], "volume", None)
        if cur_close is None or prev_close is None or vol is None:
            continue
        if cur_close > prev_close:
            running += vol
        elif cur_close < prev_close:
            running -= vol
        out[i] = round(running, 6) if started or running != 0.0 else 0.0
        started = True
    return {"obv": out}


def compute_indicators(bars: list, indicator_names: Optional[Iterable[str]] = None, params: Optional[dict] = None) -> dict:
    """无状态纯计算：输入 bars 序列（duck type），返回 {date_str: {indicator_name: value}}。

    indicator_names: None 表示返回全部默认指标（MA/BOLL/MACD/KDJ/TD/底部结构/顶部结构）；
                     可传组名（"ma"/"macd"/"kdj"/"boll"/"td_sequential"/"bottom_structure"/"top_structure"）
                     或具体字段名（"ma_5"/"macd_dif"/...）混合过滤
    params: 可覆盖默认窗口（ma_windows / boll_window / macd / kdj）

    返回值的每个 row 包含**所有匹配 name_filter 的指标键**：能算的位置是数值，
    不能算的位置是 None（例如历史不足 lookback 时 ma_60 = None）。这样前端可以
    直接拿到完整指标 schema，不用根据 key 缺失推断"没算出来"。
    """
    if not bars:
        return {}
    bars = _ordered_bars(bars)
    snapshots = _compute_indicator_snapshot(bars, params=params)
    # 复用 snapshots 已算出的 DIF 序列给底/顶结构函数，避免它们各自再跑一次
    # _compute_indicator_snapshot 引起的 O(N²) 重复计算。
    dif_series = [snap["value"].get("macd_dif") for snap in snapshots]
    td_snapshot = compute_td_sequential(bars)
    bottom_snapshot = compute_bottom_structure(bars, macd_dif_series=dif_series)
    top_snapshot = compute_top_structure(bars, macd_dif_series=dif_series)

    name_filter = [str(n).lower() for n in indicator_names] if indicator_names else None
    result: dict = {}
    for snap in snapshots:
        date_key = _date_key(snap["bar"].trade_date)
        row: dict = {}
        # 主指标快照：保留 None，让请求方能看到完整 schema
        for k, v in snap["value"].items():
            if name_filter is not None and not _name_matches_group(k, name_filter):
                continue
            row[k] = v
        # TD 序列：None / False 都不写入（TD 信号是 bool 事件型指标，不是连续序列）
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
        top_row = top_snapshot.get(date_key, {})
        if top_row.get("top_divergence"):
            if name_filter is None or "top_structure" in name_filter or "top_divergence" in name_filter:
                row["top_divergence"] = True
                if not row.get("td_signal") and top_row.get("td_signal"):
                    row["td_signal"] = top_row["td_signal"]
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

        # Buy setup：条件不满足时只重置当前 setup 计数；setup 一旦完成就锁定，
        # 避免后续「条件不满足」的 bar 把已完成状态错误回退（countdown 会乱）。
        if i < lookback_setup or bar_close is None or ref_close is None or bar_close >= ref_close:
            buy_setup = 0
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
                buy_countdown = 0

        row["td_buy_setup"] = buy_setup if buy_setup > 0 and (not buy_setup_completed or buy_setup_just_completed) else None
        row["td_buy_countdown"] = buy_countdown if buy_countdown > 0 else None

        # Sell setup：与 buy setup 对称（已完成则锁定，不被后续条件不满足的 bar 重置）。
        if i < lookback_setup or bar_close is None or ref_close is None or bar_close <= ref_close:
            sell_setup = 0
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
                sell_countdown = 0

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
                    # 只在连续段的「第一根」标 True：上一根已标则跳过，避免前端画重复三角。
                    if consecutive >= min_consecutive:
                        prev_key = _date_key(bars[i - 1].trade_date) if i > 0 else None
                        prev_flagged = bool(prev_key and result.get(prev_key, {}).get("bottom_divergence"))
                        if not prev_flagged:
                            row["bottom_divergence"] = True
                            row["td_signal"] = "bottom_divergence"
                else:
                    consecutive = 0

        result[_date_key(bar.trade_date)] = row

    return result


def compute_top_structure(
    bars: list,
    macd_dif_series: Optional[list] = None,
    lookback: int = TOP_STRUCTURE_PARAMS["lookback"],
    min_consecutive: int = TOP_STRUCTURE_PARAMS["min_consecutive"],
) -> dict:
    """顶部结构（最简实现：MACD 顶背离）。

    与 compute_bottom_structure 对称：
    - 价格创新高：bars[i].high_price 是 [i-lookback, i) 区间的最高
    - DIF 未创新高：macd_dif_series[i] 低于该区间最高
    - 连续 >= min_consecutive 根，**段首只标一次**

    返回 {date_str: {top_divergence: bool, td_signal: "top_divergence" or None}}
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
        row = {"top_divergence": False, "td_signal": None}
        bar_high = getattr(bar, "high_price", None)
        if i >= lookback and bar_high is not None:
            price_window = [bars[j].high_price for j in range(i - lookback, i) if bars[j].high_price is not None]
            dif_window = [dif_map.get(_date_key(bars[j].trade_date)) for j in range(i - lookback, i)]
            dif_window = [v for v in dif_window if v is not None]
            if price_window and dif_window:
                price_high = max(price_window)
                dif_high = max(dif_window)
                dif_now = dif_map.get(_date_key(bar.trade_date))
                if dif_now is not None and bar_high >= price_high and dif_now < dif_high:
                    consecutive += 1
                    # 段首只标一次：上一根已标则跳过，避免前端画重复三角。
                    if consecutive >= min_consecutive:
                        prev_key = _date_key(bars[i - 1].trade_date) if i > 0 else None
                        prev_flagged = bool(prev_key and result.get(prev_key, {}).get("top_divergence"))
                        if not prev_flagged:
                            row["top_divergence"] = True
                            row["td_signal"] = "top_divergence"
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


def _top_records_for_symbol(symbol: str, adjust_flag: str, bars: list[QuantDailyBar]) -> list[dict]:
    top_results = compute_top_structure(bars)
    if not top_results:
        return []
    bar_index = {id(bar): idx + 1 for idx, bar in enumerate(bars)}
    records = []
    for bar in bars:
        date_key = _date_key(bar.trade_date)
        row = top_results.get(date_key)
        if not row or not row.get("top_divergence"):
            continue
        records.append(
            {
                "symbol": bar.symbol,
                "code": bar.code,
                "exchange": bar.exchange,
                "trade_date": bar.trade_date,
                "adjust_flag": adjust_flag,
                "indicator_name": "top_divergence",
                "indicator_version": INDICATOR_SET_VERSION,
                "params_json": json.dumps(TOP_STRUCTURE_PARAMS, ensure_ascii=False),
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

    indicator_names: 可选过滤（白名单）；None = 全部指标组（MA/BOLL/MACD/KDJ/TD/底部结构/顶部结构）
    """
    if not symbols:
        return {"symbols": [], "records": 0}
    target_date = trade_date or datetime.now().date()
    group_filter = list(indicator_names) if indicator_names else None
    wants_basic = group_filter is None or bool({"ma", "boll", "macd", "kdj"} & {g.lower() for g in group_filter})
    wants_td = group_filter is None or "td_sequential" in {g.lower() for g in group_filter}
    wants_bottom = group_filter is None or "bottom_structure" in {g.lower() for g in group_filter}
    wants_top = group_filter is None or "top_structure" in {g.lower() for g in group_filter}

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
        if wants_top:
            all_records.extend(_top_records_for_symbol(symbol, adjust_flag, bars))

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


# ===========================================================================
# 指标注册表绑定
# ===========================================================================
DEFAULT_INDICATOR_WINDOWS = {
    "ma": [5, 10, 20, 60],
    "boll": [20],
    "macd": {"fast": 12, "slow": 26, "signal": 9},
    "kdj": {"n": 9, "k": 3, "d": 3},
}


def _bind_registry() -> None:
    """把 compute 函数注入 registry。必须在 compute_* 定义后才能调用。

    ParamSpec.help 字段：前端 hover 显示，给用户写表达式时参考。
    """
    ireg.register(ireg.IndicatorSpec(
        key="ma", label="均线", category="trend", base_lookback=60,
        params=(ireg.ParamSpec(
            "windows", "窗口(天)", "int_list", [5, 10, 20, 60], min=2, max=250,
            help="用逗号分隔的整数列表，如 5,10,20,60；会同时输出 ma_5/ma_10/ma_20/ma_60"
        ),),
        outputs=(ireg.OutputSpec("ma_{window}", "MA{window}", "numeric"),),
        compute=None,
    ))
    ireg.register(ireg.IndicatorSpec(
        key="boll", label="布林线", category="trend", base_lookback=20,
        params=(ireg.ParamSpec(
            "window", "周期(天)", "int", 20, min=5, max=120,
            help="布林线中轨的 SMA 周期；上下轨 = 中轨 ± 2 倍标准差"
        ),),
        outputs=(
            ireg.OutputSpec("boll_mid", "中轨", "numeric"),
            ireg.OutputSpec("boll_upper", "上轨", "numeric"),
            ireg.OutputSpec("boll_lower", "下轨", "numeric"),
        ),
        compute=None,
    ))
    ireg.register(ireg.IndicatorSpec(
        key="macd", label="MACD", category="momentum", base_lookback=26,
        params=(
            ireg.ParamSpec("fast", "快线 EMA 周期", "int", 12, min=2, max=60,
                           help="DIF = EMA(close, fast) - EMA(close, slow)"),
            ireg.ParamSpec("slow", "慢线 EMA 周期", "int", 26, min=2, max=120),
            ireg.ParamSpec("signal", "信号线 EMA 周期", "int", 9, min=2, max=60,
                           help="DEA = EMA(DIF, signal)；柱状图 = (DIF-DEA)*2"),
        ),
        outputs=(
            ireg.OutputSpec("macd_dif", "DIF（快慢差）", "numeric"),
            ireg.OutputSpec("macd_dea", "DEA（信号线）", "numeric"),
            ireg.OutputSpec("macd_bar", "BAR（柱）", "numeric"),
        ),
        compute=None,
    ))
    ireg.register(ireg.IndicatorSpec(
        key="kdj", label="KDJ", category="momentum", base_lookback=9,
        params=(
            ireg.ParamSpec("n", "RSV 周期", "int", 9, min=2, max=60,
                           help="RSV = (close - n日最低) / (n日最高 - n日最低) * 100"),
            ireg.ParamSpec("k", "K 平滑", "int", 3, min=1, max=10,
                           help="K = (k-1)/k * 旧K + 1/k * RSV"),
            ireg.ParamSpec("d", "D 平滑", "int", 3, min=1, max=10,
                           help="D = (d-1)/d * 旧D + 1/d * K；J = 3K - 2D"),
        ),
        outputs=(
            ireg.OutputSpec("kdj_k", "K 值", "numeric"),
            ireg.OutputSpec("kdj_d", "D 值", "numeric"),
            ireg.OutputSpec("kdj_j", "J 值", "numeric"),
        ),
        compute=None,
    ))
    ireg.register(ireg.IndicatorSpec(
        key="td_sequential", label="神奇九转", category="structure",
        base_lookback=9,
        params=(),
        outputs=(
            ireg.OutputSpec("td_buy_setup", "买入 Setup 计数", "numeric"),
            ireg.OutputSpec("td_buy_countdown", "买入 Countdown 计数", "numeric"),
            ireg.OutputSpec("td_sell_setup", "卖出 Setup 计数", "numeric"),
            ireg.OutputSpec("td_sell_countdown", "卖出 Countdown 计数", "numeric"),
            ireg.OutputSpec("td_signal", "TD 信号", "enum"),
        ),
        compute=None,
    ))
    ireg.register(ireg.IndicatorSpec(
        key="bottom_structure", label="MACD 底背离", category="structure",
        base_lookback=30,
        params=(),
        outputs=(ireg.OutputSpec("bottom_divergence", "底背离信号", "bool"),),
        compute=None,
    ))
    ireg.register(ireg.IndicatorSpec(
        key="top_structure", label="MACD 顶背离", category="structure",
        base_lookback=30,
        params=(),
        outputs=(ireg.OutputSpec("top_divergence", "顶背离信号", "bool"),),
        compute=compute_top_structure,
    ))
    # ----- 以下为策略 IDE 新增指标：从 rule_engine 私算的逻辑升格而来 -----
    ireg.register(ireg.IndicatorSpec(
        key="vol_ratio", label="量比", category="volume", base_lookback=6,
        params=(ireg.ParamSpec(
            "window", "回看窗口(天)", "int", 5, min=2, max=120,
            help="量比 = 当日成交量 / 前 N 日平均成交量"
        ),),
        outputs=(ireg.OutputSpec("vol_ratio_{window}", "量比{window}", "numeric"),),
        compute=compute_vol_ratio,
    ))
    ireg.register(ireg.IndicatorSpec(
        key="period_return", label="区间收益率", category="trend", base_lookback=6,
        params=(ireg.ParamSpec(
            "lookback", "回看天数", "int", 5, min=2, max=120,
            help="N 日涨幅：(close / N日前close - 1) * 100"
        ),),
        outputs=(ireg.OutputSpec("period_return_{lookback}", "N日涨幅(%)", "numeric"),),
        compute=compute_period_return,
    ))
    ireg.register(ireg.IndicatorSpec(
        key="rolling_high_low", label="前 N 根最高/最低", category="trend", base_lookback=2,
        params=(ireg.ParamSpec(
            "window", "回看窗口(天)", "int", 20, min=2, max=250,
            help="返回前 N 日最高/最低；排除当前 bar（避免未来函数）"
        ),),
        outputs=(
            ireg.OutputSpec("rolling_high_{window}", "前{window}日最高", "numeric"),
            ireg.OutputSpec("rolling_low_{window}", "前{window}日最低", "numeric"),
        ),
        compute=compute_rolling_high_low,
    ))
    # ----- 新增指标：RSI / ATR / OBV -----
    ireg.register(ireg.IndicatorSpec(
        key="rsi", label="RSI", category="momentum", base_lookback=14,
        params=(ireg.ParamSpec(
            "window", "周期(天)", "int", 14, min=2, max=120,
            help="N 日相对强弱指标（Wilder 平滑）；>70 超买，<30 超卖"
        ),),
        outputs=(ireg.OutputSpec("rsi_{window}", "RSI{window}", "numeric"),),
        compute=compute_rsi,
    ))
    ireg.register(ireg.IndicatorSpec(
        key="atr", label="ATR", category="volatility", base_lookback=14,
        params=(ireg.ParamSpec(
            "window", "周期(天)", "int", 14, min=2, max=120,
            help="N 日平均真实波幅（Wilder 平滑）；用于止损位/仓位规模"
        ),),
        outputs=(ireg.OutputSpec("atr_{window}", "ATR{window}", "numeric"),),
        compute=compute_atr,
    ))
    ireg.register(ireg.IndicatorSpec(
        key="obv", label="OBV", category="volume", base_lookback=2,
        params=(),
        outputs=(ireg.OutputSpec("obv", "OBV", "numeric"),),
        compute=compute_obv,
    ))


_bind_registry()


# 旧 SUPPORTED_INDICATOR_GROUPS / INDICATOR_BASE_LOOKBACK 已在调用方迁往 registry，
# 这里只保留别名用于向后兼容。必须在 _bind_registry() 之后赋值，否则拿到的是空值。
SUPPORTED_INDICATOR_GROUPS = ireg.all_groups()
INDICATOR_BASE_LOOKBACK = {
    key: ireg.get_spec(key).base_lookback for key in ireg.all_keys()
}
