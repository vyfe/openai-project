"""定时任务的时间计算。"""
from datetime import datetime, timedelta


def seconds_until_next(hour: int, minute: int = 0) -> int:
    """距离下一个指定时分的秒数；已过则顺延到明天。"""
    now = datetime.now()
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return max(1, int((target - now).total_seconds()))
