from typing import Iterable, Optional

from quant.entities import QuantDailyBar
from service.quant.common import normalize_symbol, parse_trade_date, to_float


def fetch_daily_bars(symbol: str, start_date: Optional[str] = None, end_date: Optional[str] = None, limit: int = 500):
    query = QuantDailyBar.select().where(QuantDailyBar.symbol == normalize_symbol(symbol))
    if start_date:
        query = query.where(QuantDailyBar.trade_date >= parse_trade_date(start_date))
    if end_date:
        query = query.where(QuantDailyBar.trade_date <= parse_trade_date(end_date))
    query = query.order_by(QuantDailyBar.trade_date.desc()).limit(limit)
    return [item.to_dict() for item in query.iterator()]


def fetch_weekly_bars(symbol: str, start_date: Optional[str] = None, end_date: Optional[str] = None, limit: int = 500):
    """基于入库日线按 ISO 周聚合为周线，避开 provider 改造。

    实现思路：
    1. 把日期范围内的日线全拉出来（数据量上限 limit × 7 估算足矣）
    2. 按 ISO 周 (year, week) 分组
    3. 每组聚合成一根周线：open=周一 open, close=周末 close, high/low 取最值, volume/amount 累加
    4. trade_date 用本周代表日（见 _pick_week_representative）
    """
    normalized = normalize_symbol(symbol)
    query = QuantDailyBar.select().where(QuantDailyBar.symbol == normalized)
    if start_date:
        query = query.where(QuantDailyBar.trade_date >= parse_trade_date(start_date))
    if end_date:
        query = query.where(QuantDailyBar.trade_date <= parse_trade_date(end_date))
    # limit 字段语义：返回多少根周线 → 多查 7 倍日线再聚合
    daily_limit = max(limit * 7, 50)
    rows = [item.to_dict() for item in query.order_by(QuantDailyBar.trade_date.desc()).limit(daily_limit).iterator()]
    weekly = _aggregate_weekly_bars(rows)
    return weekly[:limit]


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
    return week_asc_rows[-1]["trade_date"]
