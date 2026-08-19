import logging
from datetime import datetime, timedelta

import requests

from conf.runtime import runtime_state
from model.repositories.user_repository import get_user_api_key

_log = logging.getLogger("llm.web")


def _fetch_total_usage(headers, start, end):
    """
    查询一段时间窗口内的累计用量（原始数值，单位由上游决定，外部再换算）。

    :param start: start_date，需与 api_param_mode 保持一致的格式（毫秒时间戳或 YYYY-MM-DD）
    :param end: end_date，同上
    :return: 用量数值；响应缺失或异常时按约定降级
    """
    url = (
        f"{runtime_state.settings.api_hosts[0]}"
        f"/dashboard/billing/usage?start_date={start}&end_date={end}"
    )
    _log.info("fetch_usage request start=%r end=%r url=%s", start, end, url)
    try:
        response = requests.get(url, headers=headers, timeout=30)
    except requests.RequestException as exc:
        _log.warning("fetch_usage http_error url=%s err=%s", url, exc)
        return 0
    body_text = (response.text or "")[:4096]
    try:
        payload = response.json()
    except ValueError as exc:
        _log.warning(
            "fetch_usage json_decode_error url=%s status=%s err=%s body=%r",
            url, response.status_code, exc, body_text,
        )
        return 0
    if not isinstance(payload, dict):
        _log.warning(
            "fetch_usage non_dict_payload url=%s status=%s type=%s body=%r",
            url, response.status_code, type(payload).__name__, body_text,
        )
        return 0
    raw_value = payload.get("total_usage", 0)
    value = raw_value if isinstance(raw_value, (int, float)) else 0
    _log.info("fetch_usage ok url=%s status=%s value=%s", url, response.status_code, value)
    return value


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

        today_usage = _fetch_total_usage(headers, today_timestamp_ms, now_timestamp_ms)
        week_usage = _fetch_total_usage(headers, week_timestamp_ms, now_timestamp_ms)
        total_usage = _fetch_total_usage(headers, one_year_ago_timestamp_ms, now_timestamp_ms)
    else:
        today_str = datetime.combine(now.date(), datetime.min.time()).strftime("%Y-%m-%d")
        week_str = datetime.combine((now - timedelta(days=now.weekday())).date(), datetime.min.time()).strftime("%Y-%m-%d")
        one_year_ago_str = (now - timedelta(days=365)).strftime("%Y-%m-%d")
        today_usage = _fetch_total_usage(headers, today_str, today_str)
        week_usage = _fetch_total_usage(headers, week_str, today_str)
        total_usage = _fetch_total_usage(headers, one_year_ago_str, today_str)

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
