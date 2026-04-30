from __future__ import annotations

from datetime import date, datetime, timedelta


try:
    import exchange_calendars as xcals
except Exception:  # pragma: no cover - fallback for environments without dependency
    xcals = None


DEFAULT_CALENDAR = "A_SHARE"
_CALENDAR_ALIAS = {
    "A_SHARE": "XSHG",
    "SH": "XSHG",
    "SZ": "XSHG",
    "CN": "XSHG",
}


def _normalize_calendar_name(calendar_name: str) -> str:
    text = str(calendar_name or DEFAULT_CALENDAR).strip().upper()
    return _CALENDAR_ALIAS.get(text, text)


def _is_weekday(day: date) -> bool:
    return day.weekday() < 5


def _fallback_is_trade_day(day: date) -> bool:
    return _is_weekday(day)


def is_trade_day(day: date, calendar_name: str = DEFAULT_CALENDAR) -> bool:
    if xcals is None:
        return _fallback_is_trade_day(day)
    calendar = xcals.get_calendar(_normalize_calendar_name(calendar_name))
    return calendar.is_session(day)


def previous_trade_day(day: date, calendar_name: str = DEFAULT_CALENDAR) -> date:
    current = day
    while not is_trade_day(current, calendar_name):
        current -= timedelta(days=1)
    return current


def shift_trade_day(day: date, offset: int, calendar_name: str = DEFAULT_CALENDAR) -> date:
    current = previous_trade_day(day, calendar_name) if offset <= 0 else day
    step = 1 if offset >= 0 else -1
    remaining = abs(offset)
    while remaining > 0:
        current += timedelta(days=step)
        if is_trade_day(current, calendar_name):
            remaining -= 1
    if offset == 0 and not is_trade_day(current, calendar_name):
        current = previous_trade_day(current, calendar_name)
    return current


def resolve_trade_date_for_schedule(now_dt: datetime, calendar_name: str = DEFAULT_CALENDAR) -> date:
    return previous_trade_day(now_dt.date(), calendar_name)
