from datetime import time
from typing import Iterable, Optional

from quant.entities import QuantDailyBar, QuantMinuteBar
from service.quant.common import normalize_symbol, parse_trade_date, parse_trade_datetime, to_float

# A 股交易时段边界，用于分时聚合时切分 am/pm 段避免午休跨段。
_AM_OPEN = time(9, 30)
_AM_CLOSE = time(11, 30)
_PM_OPEN = time(13, 0)
_PM_CLOSE = time(15, 0)


def _resolve_minute_5m_count(bucket_minutes: int) -> int:
    """每个目标桶由多少根 5m 组成。"""
    return max(1, bucket_minutes // 5)


def _classify_minute_session(t: time) -> Optional[tuple[str, int]]:
    """把 5m bar 的时间归类到 (session, bucket_idx)；非交易时段返回 None 跳过。

    bucket_idx 是从该 session 开盘算起的整桶索引（按 bucket_minutes 划分）。
    这样 30m 时 am 段得到 4 个桶（9:30/10:00/10:30/11:00），pm 段同理，
    跨午休 11:30-13:00 不会被错误合并。
    """
    if _AM_OPEN <= t < _AM_CLOSE:
        minutes_from_open = (t.hour - 9) * 60 + (t.minute - 30)
        return ("am", minutes_from_open // _classify_minute_session._bucket_minutes)
    if _PM_OPEN <= t < _PM_CLOSE:
        minutes_from_open = (t.hour - 13) * 60 + t.minute
        return ("pm", minutes_from_open // _classify_minute_session._bucket_minutes)
    return None


def _resample_5m_to_buckets(rows_asc: list[dict], bucket_minutes: int, target_interval: str, limit: int) -> list[dict]:
    """把升序 5m bars 聚合成 15m/30m bars（OHLC 规则：open=首, high=max, low=min, close=末, volume/amount=求和）。

    跳过午休/盘前/盘后时段；桶内 5m 数量不足（数据缺失）时整桶跳过。
    返回按 trade_datetime 倒序的前 limit 桶。
    """
    if not rows_asc:
        return []
    bucket_count = _resolve_minute_5m_count(bucket_minutes)
    # 用闭包变量注入 bucket_minutes，避免重写 _classify_minute_session 签名
    _classify_minute_session._bucket_minutes = bucket_minutes  # type: ignore[attr-defined]

    buckets: dict[tuple[str, str, int], list[dict]] = {}
    for row in rows_asc:
        td = row["trade_datetime"]
        if hasattr(td, "date") and hasattr(td, "time"):
            d = td.date()
            t = td.time()
        else:
            parsed = parse_trade_datetime(td)
            d = parsed.date()
            t = parsed.time()
        sb = _classify_minute_session(t)
        if sb is None:
            continue
        session, bucket_idx = sb
        key = (d.isoformat(), session, bucket_idx)
        buckets.setdefault(key, []).append(row)

    aggregated: list[dict] = []
    for key in sorted(buckets.keys()):
        bucket_rows = buckets[key]
        if len(bucket_rows) < bucket_count:
            continue  # 桶内 5m 不完整（缺失或边界被切），整桶跳过
        first = bucket_rows[0]
        last = bucket_rows[-1]
        high_candidates = [to_float(r.get("high_price")) for r in bucket_rows]
        low_candidates = [to_float(r.get("low_price")) for r in bucket_rows]
        high = max((v for v in high_candidates if v is not None), default=None)
        low = min((v for v in low_candidates if v is not None), default=None)
        volume = sum((to_float(r.get("volume")) or 0.0) for r in bucket_rows)
        amount = sum((to_float(r.get("amount")) or 0.0) for r in bucket_rows)
        aggregated.append({
            "symbol": first.get("symbol"),
            "code": first.get("code"),
            "exchange": first.get("exchange"),
            "trade_datetime": first["trade_datetime"],
            "interval": target_interval,
            "adjust_flag": first.get("adjust_flag", "qfq"),
            "open_price": to_float(first.get("open_price")),
            "high_price": high,
            "low_price": low,
            "close_price": to_float(last.get("close_price")),
            "volume": volume or None,
            "amount": amount or None,
            "source": first.get("source"),
            "source_run_id": first.get("source_run_id"),
            "data_source_version": first.get("data_source_version"),
        })

    aggregated.sort(key=lambda r: r["trade_datetime"], reverse=True)
    return aggregated[:limit]


def fetch_daily_bars(
    symbol: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 500,
    adjust_flag: Optional[str] = None,
    include_deleted: bool = False,
):
    """日线查询。

    - adjust_flag：可选过滤（None = 不过滤，返回该 symbol 在区间内的所有 adjust_flag 行）。
    - include_deleted：默认 False（过滤 status='deleted'）。运维排查时可设 True 看全量。
    """
    query = QuantDailyBar.select().where(QuantDailyBar.symbol == normalize_symbol(symbol))
    if not include_deleted:
        query = query.where(QuantDailyBar.status == "active")
    if start_date:
        query = query.where(QuantDailyBar.trade_date >= parse_trade_date(start_date))
    if end_date:
        query = query.where(QuantDailyBar.trade_date <= parse_trade_date(end_date))
    if adjust_flag:
        query = query.where(QuantDailyBar.adjust_flag == adjust_flag)
    query = query.order_by(QuantDailyBar.trade_date.desc()).limit(limit)
    return [item.to_dict() for item in query.iterator()]


def fetch_minute_bars(
    symbol: str,
    interval: str = "5m",
    start_dt: Optional[str] = None,
    end_dt: Optional[str] = None,
    limit: int = 500,
    adjust_flag: str = "qfq",
    include_deleted: bool = False,
):
    """分时 K 线查询。limit 上限 5000，避免一次返回过多 bar。

    - interval="5m"：直接查入库的 5m 数据
    - interval="15m"/"30m"：从入库的 5m 端上聚合（OHLC 规则），不写库；
      按 (date, am/pm) 切片避开午休跨段，桶内 5m 不足时整桶跳过
    - include_deleted：默认 False（过滤 status='deleted'）。
    """
    bounded_limit = max(1, min(limit, 5000))

    if interval in ("15m", "30m"):
        bucket_minutes = 15 if interval == "15m" else 30
        # 每桶需要 bucket_minutes/5 根 5m，再放大到天级 + buffer；上限 5000 兜底
        raw_limit = min(bounded_limit * _resolve_minute_5m_count(bucket_minutes) * 4, 5000)
        five_m_query = QuantMinuteBar.select().where(
            (QuantMinuteBar.symbol == normalize_symbol(symbol))
            & (QuantMinuteBar.interval == "5m")
            & (QuantMinuteBar.adjust_flag == adjust_flag)
            & (QuantMinuteBar.status == "active" if not include_deleted else (QuantMinuteBar.status != "deleted"))
        )
        if start_dt:
            five_m_query = five_m_query.where(QuantMinuteBar.trade_datetime >= parse_trade_datetime(start_dt))
        if end_dt:
            five_m_query = five_m_query.where(QuantMinuteBar.trade_datetime <= parse_trade_datetime(end_dt))
        rows_desc = [
            item.to_dict()
            for item in five_m_query.order_by(QuantMinuteBar.trade_datetime.desc()).limit(raw_limit).iterator()
        ]
        rows_asc = list(reversed(rows_desc))
        return _resample_5m_to_buckets(rows_asc, bucket_minutes, interval, bounded_limit)

    query = QuantMinuteBar.select().where(
        (QuantMinuteBar.symbol == normalize_symbol(symbol))
        & (QuantMinuteBar.interval == interval)
        & (QuantMinuteBar.adjust_flag == adjust_flag)
    )
    if not include_deleted:
        query = query.where(QuantMinuteBar.status == "active")
    if start_dt:
        query = query.where(QuantMinuteBar.trade_datetime >= parse_trade_datetime(start_dt))
    if end_dt:
        query = query.where(QuantMinuteBar.trade_datetime <= parse_trade_datetime(end_dt))
    query = query.order_by(QuantMinuteBar.trade_datetime.desc()).limit(bounded_limit)
    return [item.to_dict() for item in query.iterator()]


def fetch_weekly_bars(
    symbol: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 500,
    include_deleted: bool = False,
):
    """基于入库日线按 ISO 周聚合为周线，避开 provider 改造。

    实现思路：
    1. 把日期范围内的日线全拉出来（数据量上限 limit × 7 估算足矣）
    2. 按 ISO 周 (year, week) 分组
    3. 每组聚合成一根周线：open=周一 open, close=周末 close, high/low 取最值, volume/amount 累加
    4. trade_date 用本周代表日（见 _pick_week_representative）
    - include_deleted：默认 False（过滤 status='deleted'）。
    """
    normalized = normalize_symbol(symbol)
    query = QuantDailyBar.select().where(QuantDailyBar.symbol == normalized)
    if not include_deleted:
        query = query.where(QuantDailyBar.status == "active")
    if start_date:
        query = query.where(QuantDailyBar.trade_date >= parse_trade_date(start_date))
    if end_date:
        query = query.where(QuantDailyBar.trade_date <= parse_trade_date(end_date))
    # limit 字段语义：返回"最近的"多少根周线 → 多查 7 倍日线再聚合
    daily_limit = max(limit * 7, 50)
    rows = [item.to_dict() for item in query.order_by(QuantDailyBar.trade_date.desc()).limit(daily_limit).iterator()]
    weekly = _aggregate_weekly_bars(rows)  # 输出 ASC
    # 取最近的 N 根并以 DESC 返回，与 fetch_daily_bars / fetch_minute_bars 保持一致
    return list(reversed(weekly[-limit:]))


def _aggregate_weekly_bars(daily_rows: list[dict]) -> list[dict]:
    """把同一 symbol 的日线按 ISO 周聚合。输入按 trade_date 倒序；输出按 trade_date 升序。"""
    if not daily_rows:
        return []

    groups: dict[tuple[int, int], list[dict]] = {}
    for row in daily_rows:
        td = row.get("trade_date")
        if td is None:
            continue
        if hasattr(td, "isocalendar"):
            iso_year, iso_week, _ = td.isocalendar()
        else:
            parsed = parse_trade_date(td)
            iso_year, iso_week, _ = parsed.isocalendar()
        groups.setdefault((iso_year, iso_week), []).append(row)

    weekly = []
    for (iso_year, iso_week), rows in groups.items():
        # rows 已经是 trade_date 倒序；asc 用于聚合判定
        asc = sorted(rows, key=lambda r: r["trade_date"])
        first = asc[0]
        last = asc[-1]
        high_candidates = [to_float(r.get("high_price")) for r in asc]
        low_candidates = [to_float(r.get("low_price")) for r in asc]
        high = max((v for v in high_candidates if v is not None), default=None)
        low = min((v for v in low_candidates if v is not None), default=None)
        volume = sum((to_float(r.get("volume")) or 0.0) for r in asc)
        amount = sum((to_float(r.get("amount")) or 0.0) for r in asc)
        rep = _pick_week_representative(asc, iso_week)
        weekly.append({
            "symbol": first.get("symbol"),
            "code": first.get("code"),
            "exchange": first.get("exchange"),
            "trade_date": rep.isoformat(),
            "adjust_flag": first.get("adjust_flag", "qfq"),
            "open_price": to_float(first.get("open_price")),
            "high_price": high,
            "low_price": low,
            "close_price": to_float(last.get("close_price")),
            "preclose_price": _preclose_of_previous_week(weekly, last, asc[0]),
            "volume": volume or None,
            "amount": amount or None,
            "turnover_rate": None,
            "pct_change": None,
            "source": first.get("source"),
            "data_source_version": first.get("data_source_version"),
        })

    weekly.sort(key=lambda r: r["trade_date"])
    # 回填 pct_change / preclose_price（依赖前一周收盘）
    prev_close = None
    for bar in weekly:
        first_open = bar["open_price"]
        last_close = bar["close_price"]
        if prev_close not in (None, 0) and last_close is not None:
            bar["preclose_price"] = prev_close
            bar["pct_change"] = (last_close - prev_close) / prev_close * 100
        elif bar.get("preclose_price") is None and first_open is not None:
            # 第一个周没有上一周收盘，用本周 open 作为 preclose（仅占位，下一轮会被覆盖）
            bar["preclose_price"] = first_open
        prev_close = last_close
    return weekly


def _preclose_of_previous_week(weekly_so_far: list[dict], last_daily_row: dict, first_daily_row: dict):
    """占位函数：正式 preclose 在回填阶段根据上一周 close 计算，这里先放本周首个 open。"""
    return to_float(first_daily_row.get("open_price"))


def _pick_week_representative(week_asc_rows: list[dict], iso_week: int):
    """从同一 ISO 周的日线里挑一个日期作为周线代表日。

    设计依据：周线展示中 X 轴的 label 需要既是 ISO 周内的一个具体日期，又能反映"这一周结束"。
    输入：本周所有交易日（按日期升序），含 trade_date 字段。
    返回：date 对象。
    """
    # 方案 A：本周最后一个交易日。和 A 股习惯一致——周五或节前最后一天。
    td = week_asc_rows[-1]["trade_date"]
    if hasattr(td, "isoformat"):
        return td
    return parse_trade_date(td)
