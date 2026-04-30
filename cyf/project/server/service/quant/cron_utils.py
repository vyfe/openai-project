from __future__ import annotations

from datetime import datetime


class CronExpression:
    def __init__(self, expression: str):
        text = str(expression or "").strip()
        parts = text.split()
        if len(parts) != 5:
            raise ValueError("cron_expr 需要 5 段，例如 20 9,15 * * 1-5")
        minute_expr, hour_expr, day_expr, month_expr, weekday_expr = parts
        self.expression = text
        self.minutes = _parse_field(minute_expr, 0, 59)
        self.hours = _parse_field(hour_expr, 0, 23)
        self.days = _parse_field(day_expr, 1, 31)
        self.months = _parse_field(month_expr, 1, 12)
        self.weekdays = _parse_field(weekday_expr, 0, 6, allow_seven=True)

    def matches(self, dt: datetime) -> bool:
        return (
            dt.minute in self.minutes
            and dt.hour in self.hours
            and dt.day in self.days
            and dt.month in self.months
            and dt.weekday() in self.weekdays
        )


def _parse_field(expr: str, minimum: int, maximum: int, allow_seven: bool = False) -> set[int]:
    text = str(expr or "").strip()
    if text == "*":
        return set(range(minimum, maximum + 1))

    values: set[int] = set()
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        if "/" in part:
            base, step_text = part.split("/", 1)
            step = int(step_text)
            if step <= 0:
                raise ValueError(f"cron step 非法: {expr}")
            base_values = _parse_field(base if base else "*", minimum, maximum, allow_seven=allow_seven)
            start = min(base_values)
            for value in sorted(base_values):
                if (value - start) % step == 0:
                    values.add(value)
            continue
        if "-" in part:
            start_text, end_text = part.split("-", 1)
            start = _coerce_value(start_text, minimum, maximum, allow_seven=allow_seven)
            end = _coerce_value(end_text, minimum, maximum, allow_seven=allow_seven)
            if end < start:
                raise ValueError(f"cron 范围非法: {expr}")
            values.update(range(start, end + 1))
            continue
        values.add(_coerce_value(part, minimum, maximum, allow_seven=allow_seven))

    if not values:
        raise ValueError(f"cron 字段为空: {expr}")
    return values


def _coerce_value(text: str, minimum: int, maximum: int, allow_seven: bool = False) -> int:
    value = int(text)
    if allow_seven and value == 7:
        value = 0
    if value < minimum or value > maximum:
        raise ValueError(f"cron 值越界: {text}")
    return value


def cron_matches(expression: str, dt: datetime) -> bool:
    return CronExpression(expression).matches(dt)
