from datetime import datetime, timedelta

import requests

from conf.runtime import runtime_state
from model.repositories.user_repository import get_user_api_key


def get_usage_summary(user: str):
    api_key = get_user_api_key(user)
    api_host = runtime_state.settings.api_hosts[0]
    now = datetime.now()
    headers = {"Authorization": f"Bearer {api_key}"}
    api_param_mode = runtime_state.settings.api_param_mode

    if api_param_mode == "timestamp":
        today_start = datetime.combine(now.date(), datetime.min.time())
        week_start = datetime.combine((now - timedelta(days=now.weekday())).date(), datetime.min.time())
        now_timestamp_ms = int(now.timestamp() * 1000)
        today_timestamp_ms = int(today_start.timestamp() * 1000)
        week_timestamp_ms = int(week_start.timestamp() * 1000)
        one_year_ago_timestamp_ms = int((datetime.now() - timedelta(days=365)).timestamp() * 1000)

        today_usage = requests.get(
            f"{api_host}/dashboard/billing/usage?start_date={today_timestamp_ms}&end_date={now_timestamp_ms}",
            headers=headers,
            timeout=30,
        ).json().get("total_usage", 0)
        week_usage = requests.get(
            f"{api_host}/dashboard/billing/usage?start_date={week_timestamp_ms}&end_date={now_timestamp_ms}",
            headers=headers,
            timeout=30,
        ).json().get("total_usage", 0)
        total_usage = requests.get(
            f"{api_host}/dashboard/billing/usage?start_date={one_year_ago_timestamp_ms}&end_date={now_timestamp_ms}",
            headers=headers,
            timeout=30,
        ).json().get("total_usage", 0)
    else:
        today_str = datetime.combine(now.date(), datetime.min.time()).strftime("%Y-%m-%d")
        week_str = datetime.combine((now - timedelta(days=now.weekday())).date(), datetime.min.time()).strftime("%Y-%m-%d")
        now_str = now.strftime("%Y-%m-%d")
        today_usage = requests.get(
            f"{api_host}/dashboard/billing/usage?start_date={today_str}&end_date={now_str}",
            headers=headers,
            timeout=30,
        ).json().get("total_usage", 0)
        week_usage = requests.get(
            f"{api_host}/dashboard/billing/usage?start_date={week_str}&end_date={now_str}",
            headers=headers,
            timeout=30,
        ).json().get("total_usage", 0)
        total_usage = requests.get(
            f"{api_host}/dashboard/billing/usage?start_date={week_str}&end_date={now_str}",
            headers=headers,
            timeout=30,
        ).json().get("total_usage", 0)

    subscription_data = requests.get(f"{api_host}/dashboard/billing/subscription", headers=headers, timeout=30).json()
    quota = subscription_data.get("hard_limit_usd", 0)
    rate = runtime_state.settings.usd_to_cny_rate
    today_usage_cny = (today_usage / 100) * rate
    week_usage_cny = (week_usage / 100) * rate
    total_usage_cny = (total_usage / 100) * rate
    quota_cny = quota * rate
    remaining_cny = quota_cny - total_usage_cny

    return {
        "success": True,
        "data": {
            "today_usage": round(today_usage_cny, 2),
            "week_usage": round(week_usage_cny, 2),
            "total_usage": round(total_usage_cny, 2),
            "quota": round(quota_cny, 2),
            "remaining": round(remaining_cny, 2),
            "currency": "CNY",
        },
    }
