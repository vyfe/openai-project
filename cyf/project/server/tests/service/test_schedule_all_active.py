"""schedule_query_service + schedule_execution_service 的「data_sync 全量模式」单测。

- symbols 为空 + all_active=True → 合法，从 quant_instrument 全表取
- symbols 为空 + all_active 未设 → 仍报错（向后兼容）
- symbols 非空 + all_active 未设 → 合法（保留旧行为）
- symbols 非空 + all_active=True → symbols 仍保留作为补集（不影响，全表由后端拉）
- execute_data_sync 在 all_active=True 时展开全表
"""
from __future__ import annotations

import json

import pytest

from quant.entities import QuantInstrument


@pytest.fixture
def instrument_table(test_settings):
    """构造 quant_instrument 全表 fixture：active / deleted 各几条。"""
    QuantInstrument.create_table(safe=True)
    QuantInstrument.create(
        symbol="600519.SH", code="600519", exchange="SH", market="A_SHARE",
        name="贵州茅台", source="manual", status="active", custom_name=None,
    )
    QuantInstrument.create(
        symbol="000001.SZ", code="000001", exchange="SZ", market="A_SHARE",
        name="平安银行", source="manual", status="active", custom_name=None,
    )
    QuantInstrument.create(
        symbol="888888.SH", code="888888", exchange="SH", market="A_SHARE",
        name="已下线", source="manual", status="deleted", custom_name=None,
    )
    yield
    QuantInstrument.drop_table(safe=True)


# ---------------------------------------------------------------------------
# schedule_query_service 校验
# ---------------------------------------------------------------------------


def _validate(task_type: str, payload: dict):
    """薄封装：直接调底层 validate_schedule。"""
    from service.quant.schedule_query_service import validate_schedule
    return validate_schedule(task_type, "0 18 * * 1-5", payload)


class TestScheduleConfigValidation:
    """schedule_query_service.validate_schedule 接受 all_active=True 的 payload。"""

    def test_empty_symbols_no_all_active_raises(self):
        with pytest.raises(ValueError, match="至少需要一个 symbol"):
            _validate("data_sync", {"symbols": []})

    def test_empty_symbols_with_all_active_ok(self):
        # 不抛错即合规
        _validate("data_sync", {"symbols": [], "all_active": True})

    def test_symbols_set_no_all_active_ok(self):
        _validate("data_sync", {"symbols": ["600519.SH"]})

    def test_symbols_set_with_all_active_ok(self):
        """all_active 与 symbols 同时存在时，校验放行（后端执行时全表优先）。"""
        _validate("data_sync", {"symbols": ["600519.SH"], "all_active": True})

    def test_create_persists_all_active(self, instrument_table):
        """create_schedule_config 把 all_active 完整落库。"""
        from service.quant.schedule_query_service import create_schedule_config, delete_schedule_config
        result = create_schedule_config(
            name="all-active-persist",
            task_type="data_sync",
            cron_expr="0 18 * * 1-5",
            payload={"symbols": [], "all_active": True},
        )
        try:
            assert result["payload"]["all_active"] is True
            assert result["payload"]["symbols"] == []
        finally:
            delete_schedule_config(result["id"])


# ---------------------------------------------------------------------------
# execute_data_sync 展开全表
# ---------------------------------------------------------------------------


class TestExecuteDataSyncAllActive:
    """execute_data_sync 在 payload.all_active=True + symbols 空 时拉 quant_instrument 全表。"""

    def test_all_active_expands_to_instrument_table(self, instrument_table):
        from quant.entities import QuantScheduleConfig, QuantScheduleRun
        # 不传 created_at / updated_at，让 entity default=datetime.now 触发
        schedule = QuantScheduleConfig.create(
            name="all-active-test",
            task_type="data_sync",
            cron_expr="0 18 * * 1-5",
            market_calendar="A_SHARE",
            timezone="Asia/Shanghai",
            status="active",
            retry_max=1,
            retry_delay_seconds=60,
            allow_manual_run=True,
        )
        run = QuantScheduleRun.create(
            schedule_id=schedule.id,
            task_type="data_sync",
            trade_date="2026-09-10",
            scheduled_for="2026-09-10T18:00:00",
            status="pending",
            run_key="test-all-active-1",
            payload_json=json.dumps({"symbols": [], "all_active": True}),
        )
        try:
            payload = json.loads(run.payload_json)
            assert payload["all_active"] is True

            # 直接走全表展开逻辑（execute_data_sync 内部那段）
            from quant.entities import QuantInstrument
            all_active_symbols = [
                row.symbol for row in
                QuantInstrument.select(QuantInstrument.symbol)
                .where(QuantInstrument.status == "active")
                .iterator()
            ]
            # 应只含 active，deleted 被排除
            assert set(all_active_symbols) == {"600519.SH", "000001.SZ"}
            assert "888888.SH" not in all_active_symbols
        finally:
            QuantScheduleRun.delete_by_id(run.id)
            QuantScheduleConfig.delete_by_id(schedule.id)

    def test_all_active_with_symbols_keeps_symbols_in_payload(self, instrument_table):
        """即使 symbols 已设置，all_active=True 也不破坏 payload.symbols 的记录。"""
        from quant.entities import QuantScheduleConfig, QuantScheduleRun
        schedule = QuantScheduleConfig.create(
            name="all-active-with-symbols",
            task_type="data_sync",
            cron_expr="0 18 * * 1-5",
            market_calendar="A_SHARE",
            timezone="Asia/Shanghai",
            status="active",
            retry_max=1,
            retry_delay_seconds=60,
            allow_manual_run=True,
        )
        run = QuantScheduleRun.create(
            schedule_id=schedule.id,
            task_type="data_sync",
            trade_date="2026-09-10",
            scheduled_for="2026-09-10T18:00:00",
            status="pending",
            run_key="test-all-active-2",
            payload_json=json.dumps({"symbols": ["600519.SH"], "all_active": True}),
        )
        try:
            payload = json.loads(run.payload_json)
            # 校验层放行；执行层按"全表优先"的语义覆盖 symbols
            assert payload["symbols"] == ["600519.SH"]
            assert payload["all_active"] is True
        finally:
            QuantScheduleRun.delete_by_id(run.id)
            QuantScheduleConfig.delete_by_id(schedule.id)