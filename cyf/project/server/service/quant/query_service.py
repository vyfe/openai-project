from typing import Optional

from quant.entities import QuantDailyBar
from service.quant.common import normalize_symbol, parse_trade_date


def fetch_daily_bars(symbol: str, start_date: Optional[str] = None, end_date: Optional[str] = None, limit: int = 500):
    query = QuantDailyBar.select().where(QuantDailyBar.symbol == normalize_symbol(symbol))
    if start_date:
        query = query.where(QuantDailyBar.trade_date >= parse_trade_date(start_date))
    if end_date:
        query = query.where(QuantDailyBar.trade_date <= parse_trade_date(end_date))
    query = query.order_by(QuantDailyBar.trade_date.desc()).limit(limit)
    return [item.to_dict() for item in query.iterator()]
