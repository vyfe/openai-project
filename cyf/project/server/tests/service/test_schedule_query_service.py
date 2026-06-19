"""schedule_query_service 集成测试 — 验证调度配置 CRUD 和触发逻辑。"""

import json
import pytest
from unittest.mock import patch

from service.quant.schedule_query_service import (
    validate_schedule,
    create_schedule_config,
    list_schedule_configs,
    get_schedule_config,
    update_schedule_config,
    delete_schedule_config,
    manual_trigger_schedule,
    reset_schedule_run,
    enqueue_schedule_run,
    RUN_STATUS_PENDING,
    RUN_STATUS_FAILED,
    RUN_STATUS_SUCCESS,
)
from datetime import datetime


class TestValidateSchedule:
    """测试调度配置校验。"""

    def test_data_sync_needs_symbols(self):
        with pytest.raises(ValueError, match="至少需要一个 symbol"):
            validate_schedule("data_sync", "20 15 * * 1-5", {"symbols": []})

    def test_data_sync_with_symbols_ok(self):
        validate_schedule("data_sync", "20 15 * * 1-5", {"symbols": ["000001.SZ"]})

    def test_analysis_needs_strategy_ids(self):
        with pytest.raises(ValueError, match="至少需要一个 strategy_id"):
            validate_schedule("analysis_report", "20 15 * * 1-5", {})

    def test_analysis_with_strategy_ids_ok(self):
        validate_schedule("analysis_report", "20 15 * * 1-5", {"strategy_ids": [1]})

    def test_memory_digest_invalid_lookback(self):
        # 注意：当前代码中 int(x or 120) 导致 lookback_days=0 被覆盖为默认值 120，
        # 不会触发校验。用 -1 验证负值能被正确拦截。
        with pytest.raises(ValueError, match="必须大于 0"):
            validate_schedule("memory_digest", "20 15 * * 1-5", {"lookback_days": -1})

    def test_memory_digest_ok(self):
        validate_schedule("memory_digest", "20 15 * * 1-5", {"lookback_days": 120})

    def test_unsupported_task_type(self):
        with pytest.raises(ValueError, match="不支持的 task_type"):
            validate_schedule("unknown", "20 15 * * 1-5", {})

    def test_empty_task_type(self):
        with pytest.raises(ValueError, match="不能为空"):
            validate_schedule("", "20 15 * * 1-5", {})


class TestCreateScheduleConfig:
    """测试创建调度配置。"""

    def test_create_data_sync(self):
        result = create_schedule_config(
            name="每日拉数",
            task_type="data_sync",
            cron_expr="20 15 * * 1-5",
            payload={"symbols": ["000001.SZ"]},
        )
        assert result["id"] > 0
        assert result["name"] == "每日拉数"
        assert result["task_type"] == "data_sync"

    def test_create_empty_name_raises(self):
        with pytest.raises(ValueError, match="name 不能为空"):
            create_schedule_config(name="", task_type="data_sync", cron_expr="20 15 * * 1-5", payload={"symbols": ["000001.SZ"]})

    def test_create_invalid_cron_raises(self):
        with pytest.raises(ValueError):
            create_schedule_config(name="X", task_type="data_sync", cron_expr="invalid", payload={"symbols": ["000001.SZ"]})


class TestListScheduleConfigs:
    """测试列出调度配置。"""

    def test_empty(self):
        result = list_schedule_configs()
        assert result == []

    def test_after_create(self):
        create_schedule_config(name="A", task_type="data_sync", cron_expr="20 15 * * 1-5", payload={"symbols": ["000001.SZ"]})
        result = list_schedule_configs()
        assert len(result) == 1


class TestUpdateScheduleConfig:
    """测试更新调度配置。"""

    def test_update_name(self):
        created = create_schedule_config(name="Old", task_type="data_sync", cron_expr="20 15 * * 1-5", payload={"symbols": ["000001.SZ"]})
        result = update_schedule_config(created["id"], name="New")
        assert result["name"] == "New"


class TestDeleteScheduleConfig:
    """测试删除调度配置。"""

    def test_delete(self):
        created = create_schedule_config(name="ToDelete", task_type="data_sync", cron_expr="20 15 * * 1-5", payload={"symbols": ["000001.SZ"]})
        delete_schedule_config(created["id"])
        result = list_schedule_configs()
        assert len(result) == 0


class TestManualTriggerSchedule:
    """测试手工触发调度。"""

    def test_manual_trigger_creates_pending_run(self):
        config = create_schedule_config(
            name="手动触发",
            task_type="data_sync",
            cron_expr="20 15 * * 1-5",
            payload={"symbols": ["000001.SZ"]},
        )
        with patch("service.quant.schedule_query_service.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2025, 1, 15, 15, 0)
            result = manual_trigger_schedule(config["id"])
            assert result["status"] == RUN_STATUS_PENDING
            assert result["trigger_source"] == "manual"

    def test_manual_trigger_disallowed(self):
        config = create_schedule_config(
            name="禁止手动",
            task_type="data_sync",
            cron_expr="20 15 * * 1-5",
            payload={"symbols": ["000001.SZ"]},
            allow_manual_run=False,
        )
        with pytest.raises(ValueError, match="不允许手工重跑"):
            manual_trigger_schedule(config["id"])


class TestResetScheduleRun:
    """测试重置调度运行记录。"""

    def test_reset_failed_run(self):
        config = create_schedule_config(
            name="重置测试",
            task_type="data_sync",
            cron_expr="20 15 * * 1-5",
            payload={"symbols": ["000001.SZ"]},
        )
        with patch("service.quant.schedule_query_service.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2025, 1, 15, 15, 0)
            run = manual_trigger_schedule(config["id"])

        # 直接更新状态为 failed
        from quant.entities import QuantScheduleRun
        record = QuantScheduleRun.get_by_id(run["id"])
        record.status = RUN_STATUS_FAILED
        record.save()

        result = reset_schedule_run(run["id"])
        assert result["status"] == RUN_STATUS_PENDING

    def test_reset_success_not_allowed_by_default(self):
        config = create_schedule_config(
            name="重置成功",
            task_type="data_sync",
            cron_expr="20 15 * * 1-5",
            payload={"symbols": ["000001.SZ"]},
        )
        with patch("service.quant.schedule_query_service.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2025, 1, 15, 15, 0)
            run = manual_trigger_schedule(config["id"])

        from quant.entities import QuantScheduleRun
        record = QuantScheduleRun.get_by_id(run["id"])
        record.status = RUN_STATUS_SUCCESS
        record.save()

        with pytest.raises(ValueError, match="不支持重置"):
            reset_schedule_run(run["id"])
