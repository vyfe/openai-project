"""task_dispatch_service + schedule_execution_service 的 minute/frequency 透传测试。

覆盖点：
1. create_fetch_bars_task frequency="5m" → task_type="fetch_a_share_minute_bars"
2. payload 注入 frequency / interval / lookback_minutes
3. resolve_fetch_window 按 frequency 分发：
   - 1d 走 lookback_trade_days（保持原行为）
   - 5m 走 lookback_minutes，返回含时分的 ISO 字符串
4. execute_data_sync 把 payload.frequency 透传给 create_fetch_bars_task
"""

from datetime import date

import pytest

from service.quant.task_dispatch_service import create_fetch_bars_task
from service.quant.schedule_execution_service import resolve_fetch_window


class TestCreateFetchBarsTaskFrequency:
    def test_default_frequency_1d_uses_daily_task_type(self):
        task = create_fetch_bars_task(
            symbols=["600519.SH"],
            start_date="2024-01-02",
            end_date="2024-01-02",
        )
        assert task["task_type"] == "fetch_a_share_daily_bars"
        assert task["payload"]["frequency"] == "1d"
        assert task["payload"]["interval"] == "5m"

    def test_frequency_5m_uses_minute_task_type(self):
        task = create_fetch_bars_task(
            symbols=["600519.SH"],
            start_date="2024-01-02 09:30:00",
            end_date="2024-01-02 15:00:00",
            frequency="5m",
            interval="5m",
            lookback_minutes=60,
        )
        assert task["task_type"] == "fetch_a_share_minute_bars"
        assert task["payload"]["frequency"] == "5m"
        assert task["payload"]["interval"] == "5m"
        assert task["payload"]["lookback_minutes"] == 60

    def test_explicit_task_type_overrides_frequency(self):
        task = create_fetch_bars_task(
            symbols=["600519.SH"],
            start_date="2024-01-02",
            end_date="2024-01-02",
            frequency="5m",
            task_type="custom_task_type",
        )
        assert task["task_type"] == "custom_task_type"

    def test_minute_lookback_minutes_writes_both_fields(self):
        """新字段 minute_lookback_minutes 写入 payload 同时也保留旧别名 lookback_minutes（兼容旧消费者）。"""
        task = create_fetch_bars_task(
            symbols=["600519.SH"],
            start_date="2024-01-02 14:00:00",
            end_date="2024-01-02 15:00:00",
            frequency="5m",
            minute_lookback_minutes=120,
        )
        assert task["payload"]["minute_lookback_minutes"] == 120
        # 旧别名也写一份，下游 _resolve_minute_lookback_minutes 的兼容路径能拿到
        assert task["payload"]["lookback_minutes"] == 120

    def test_minute_lookback_takes_precedence_over_legacy_alias(self):
        """同时传两个字段时，新字段 minute_lookback_minutes 生效，旧别名被忽略。"""
        task = create_fetch_bars_task(
            symbols=["600519.SH"],
            start_date="2024-01-02 14:00:00",
            end_date="2024-01-02 15:00:00",
            frequency="5m",
            minute_lookback_minutes=120,
            lookback_minutes=999,  # 应被忽略
        )
        assert task["payload"]["minute_lookback_minutes"] == 120
        assert task["payload"]["lookback_minutes"] == 120

    def test_legacy_lookback_minutes_still_works(self):
        """老调用方只传 lookback_minutes，新签名也应兼容（向后兼容）。"""
        task = create_fetch_bars_task(
            symbols=["600519.SH"],
            start_date="2024-01-02 14:00:00",
            end_date="2024-01-02 15:00:00",
            frequency="5m",
            lookback_minutes=90,
        )
        assert task["payload"]["lookback_minutes"] == 90
        assert "minute_lookback_minutes" not in task["payload"]


class TestResolveFetchWindow:
    def test_1d_uses_trade_days_lookback(self):
        """frequency=1d 走交易日历回推，返回纯日期字符串。"""
        payload = {"frequency": "1d", "lookback_trade_days": 5}
        start, end = resolve_fetch_window(payload, date(2024, 1, 15))
        assert end == "2024-01-15"
        # start 应该是 5 个交易日前（不含当天，所以是 -4 步）
        assert start == "2024-01-09"

    def test_5m_uses_minutes_lookback(self):
        """frequency=5m 走交易日倒推：60 分钟 → 1 天，起点 = 当天开盘 9:30。"""
        payload = {"frequency": "5m", "lookback_minutes": 60}
        start, end = resolve_fetch_window(payload, date(2024, 1, 15))
        assert end == "2024-01-15T15:00"
        # 60 分钟向上取整 = 1 个交易日，9:30 开盘
        assert start == "2024-01-15T09:30"

    def test_5m_one_trade_day_uses_open_to_close(self):
        """240 分钟 = 1 个交易日，起点 = 当天 9:30，终点 = 当天 15:00。"""
        payload = {"frequency": "5m", "lookback_minutes": 240}
        start, end = resolve_fetch_window(payload, date(2024, 1, 15))
        assert end == "2024-01-15T15:00"
        assert start == "2024-01-15T09:30"

    def test_5m_default_lookback_is_5_trade_days(self):
        """默认 1200 分钟 = 5 个交易日：起点 = 5 天前 9:30，终点 = 当天 15:00。
        注意：A 股一天 240 分钟（9:30-11:30 + 13:00-15:00），不再把午休/盘后空档算进去。
        """
        from service.quant.trade_calendar_service import is_trade_day
        payload = {"frequency": "5m", "minute_lookback_minutes": 1200}
        target = date(2024, 1, 15)  # 周一交易日
        start, end = resolve_fetch_window(payload, target)
        assert end == "2024-01-15T15:00"
        # 5 个交易日倒推：1/15 - 4 个交易日 = 1/9（周二）。验证起点是 1/9 9:30
        assert start == "2024-01-09T09:30"
        assert is_trade_day(date(2024, 1, 9))

    def test_5m_window_excludes_lunch_break(self):
        """窗口不跨午休：起点 9:30，终点 15:00，跨度 5.5 小时自然段（不算 11:30-13:00 午休）。"""
        payload = {"frequency": "5m", "minute_lookback_minutes": 240}
        start, end = resolve_fetch_window(payload, date(2024, 1, 15))
        from datetime import datetime
        s = datetime.fromisoformat(start)
        e = datetime.fromisoformat(end)
        # 跨度 = 5.5 小时（9:30-15:00），不是 240 分钟/天连续减
        diff_minutes = (e - s).total_seconds() / 60
        assert diff_minutes == 330  # 5.5 小时 = 330 分钟（开收盘差）

    def test_explicit_start_end_overrides_frequency(self):
        payload = {
            "frequency": "5m",
            "lookback_minutes": 60,
            "start_date": "2024-01-02 09:00:00",
            "end_date": "2024-01-02 10:00:00",
        }
        start, end = resolve_fetch_window(payload, date(2024, 1, 15))
        assert start == "2024-01-02 09:00:00"
        assert end == "2024-01-02 10:00:00"

    def test_unknown_frequency_falls_back_to_daily(self):
        """首期未定义的 frequency 默认走 1d 分支，向后兼容。"""
        payload = {"frequency": "1h", "lookback_trade_days": 3}
        start, end = resolve_fetch_window(payload, date(2024, 1, 15))
        assert end == "2024-01-15"
        assert start == "2024-01-11"

    def test_5m_minute_lookback_minutes_takes_precedence(self):
        """新字段 minute_lookback_minutes 优先于旧别名 lookback_minutes。"""
        from service.quant.schedule_execution_service import (
            DEFAULT_MINUTE_LOOKBACK_MINUTES,
            MAX_MINUTE_LOOKBACK_MINUTES,
            _resolve_minute_lookback_minutes,
        )
        # 新字段生效
        assert _resolve_minute_lookback_minutes({"minute_lookback_minutes": 30, "lookback_minutes": 90}) == 30
        # 旧别名兜底
        assert _resolve_minute_lookback_minutes({"lookback_minutes": 90}) == 90
        # 都没给 → 默认值
        assert _resolve_minute_lookback_minutes({}) == DEFAULT_MINUTE_LOOKBACK_MINUTES
        # 超 MAX → cap（防呆）
        assert _resolve_minute_lookback_minutes({"minute_lookback_minutes": 99999}) == MAX_MINUTE_LOOKBACK_MINUTES
        # 非法值 → 默认值兜底
        assert _resolve_minute_lookback_minutes({"minute_lookback_minutes": "not-int"}) == DEFAULT_MINUTE_LOOKBACK_MINUTES
        # 负数 / 0 → 至少 1 分钟
        assert _resolve_minute_lookback_minutes({"minute_lookback_minutes": 0}) == 1

class TestExecuteDataSyncFrequencies:
    """execute_data_sync 支持 payload.frequencies 列表，下发多个 task。"""

    def _make_run(self, payload):
        import json as _json
        import uuid as _uuid
        from datetime import date as _date
        from datetime import datetime as _datetime
        from quant.entities import QuantScheduleConfig, QuantScheduleRun
        config = QuantScheduleConfig.create(
            name="test-schedule",
            task_type="data_sync",
            cron_expr="*/5 * * * *",
            payload_json=_json.dumps(payload),
            status="active",
            market_calendar="A_SHARE",
            timezone="Asia/Shanghai",
        )
        return QuantScheduleRun.create(
            schedule_id=config.id,
            task_type="data_sync",
            run_key=f"test-{_uuid.uuid4().hex}",
            trade_date=_date(2024, 1, 15),
            scheduled_for=_datetime(2024, 1, 15, 14, 0, 0),
            status="pending",
            payload_json=_json.dumps(payload),
        )

    def test_frequencies_list_creates_two_tasks(self):
        from service.quant.schedule_execution_service import execute_data_sync
        run = self._make_run({
            "frequencies": ["1d", "5m"],
            "symbols": ["600519.SH"],
            "provider": "auto",
            "lookback_trade_days": 5,
            "lookback_minutes": 60,
        })
        result = execute_data_sync(run)
        assert result["frequencies"] == ["1d", "5m"]
        assert len(result["client_tasks"]) == 2
        daily_task = result["client_tasks"][0]
        assert daily_task["task_type"] == "fetch_a_share_daily_bars"
        assert daily_task["payload"]["frequency"] == "1d"
        minute_task = result["client_tasks"][1]
        assert minute_task["task_type"] == "fetch_a_share_minute_bars"
        assert minute_task["payload"]["frequency"] == "5m"
        assert minute_task["payload"]["interval"] == "5m"
        # 旧字段 client_task 仍兼容
        assert result["client_task"] == daily_task

    def test_legacy_single_frequency_still_works(self):
        """旧 payload 只有 frequency 单值，应继续工作（不破坏现有 schedule_config）。"""
        from service.quant.schedule_execution_service import execute_data_sync
        run = self._make_run({
            "frequency": "5m",
            "symbols": ["600519.SH"],
            "provider": "auto",
            "lookback_minutes": 60,
        })
        result = execute_data_sync(run)
        assert result["frequencies"] == ["5m"]
        assert len(result["client_tasks"]) == 1
        assert result["client_tasks"][0]["task_type"] == "fetch_a_share_minute_bars"

    def test_no_frequency_defaults_to_daily(self):
        from service.quant.schedule_execution_service import execute_data_sync
        run = self._make_run({"symbols": ["600519.SH"]})
        result = execute_data_sync(run)
        assert result["frequencies"] == ["1d"]
        assert result["client_tasks"][0]["task_type"] == "fetch_a_share_daily_bars"

    def test_frequencies_window_per_frequency(self):
        """每个 frequency 应独立计算窗口（1d 用日线窗口，5m 用分钟窗口）。"""
        from service.quant.schedule_execution_service import execute_data_sync
        run = self._make_run({
            "frequencies": ["1d", "5m"],
            "symbols": ["600519.SH"],
            "provider": "auto",
            "lookback_trade_days": 3,
            "lookback_minutes": 30,
        })
        result = execute_data_sync(run)
        daily_payload = result["client_tasks"][0]["payload"]
        minute_payload = result["client_tasks"][1]["payload"]
        assert "T" not in daily_payload["start_date"]
        assert "T" not in daily_payload["end_date"]
        assert "T" in minute_payload["start_date"]
        assert "T" in minute_payload["end_date"]
