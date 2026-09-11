"""Client Agent 路由集成测试 — /quant/client/tasks/*。

核心回归：import_bundle 失败时 task 必须标记为 failed，
否则会卡 leased 被 _recycle_expired_leases 反复 recycle，
新 agent 拿到同一个 task_id 又跑，无限循环。

线上 2026-09-11 真实故障：import_bundle 因 `database disk image is malformed`
抛 sqlite3.DatabaseError，原代码 silent return error_response 不更新 task 状态，
导致 28 个 batch 全 failed、对应 task 永远卡 leased、8-9 分钟 lease 过期后被新
agent claim 重跑。
"""

import gzip
import json
import uuid as _uuid
from datetime import datetime
from unittest.mock import patch

import pytest

from quant.entities import QuantClientTask, QuantImportBatch
from service.quant.task_dispatch_service import create_fetch_bars_task


def _build_bundle_gz(records: list[dict]) -> bytes:
    bundle = {
        "dataset": "a_share_5min_bars_v1",
        "bundle_version": 1,
        "batch_id": _uuid.uuid4().hex,
        "source": "baostock",
        "source_run_id": _uuid.uuid4().hex,
        "generated_at": datetime.now().isoformat(),
        "market": "A_SHARE",
        "provider_meta": {"provider_name": "baostock", "frequency": "5m", "interval": "5m"},
        "records": records,
    }
    return gzip.compress(json.dumps(bundle, ensure_ascii=False).encode("utf-8"))


def _make_minute_records():
    return [
        {
            "symbol": "600519.SH",
            "code": "600519",
            "exchange": "SH",
            "trade_datetime": "2025-01-02 09:35:00",
            "trade_date": "2025-01-02",
            "interval": "5m",
            "adjust_flag": "qfq",
            "open_price": 1700.0,
            "high_price": 1702.0,
            "low_price": 1699.0,
            "close_price": 1701.0,
            "volume": 1000.0,
            "amount": 1701000.0,
            "source": "baostock",
            "source_run_id": "test",
        }
    ]


class TestClientTaskReport:
    """POST /client/tasks/report：agent 上报任务结果。"""

    def _setup_leased_task(self, task_id: str, schedule_id: int = 1) -> None:
        """建好 task + schedule_run，再把 task_id 改成传入值（便于测试断言）。"""
        from quant.entities import QuantScheduleRun
        schedule = QuantScheduleRun.create(
            schedule_id=schedule_id,
            schedule_name="测试配置",
            task_type="data_sync",
            run_key=f"test-{_uuid.uuid4().hex}",
            scheduled_for=datetime(2025, 1, 15, 15, 0),
            trade_date=datetime(2025, 1, 15).date(),
            payload_json="{}",
        )
        created = create_fetch_bars_task(
            symbols=["600519.SH"],
            start_date="2025-01-02 00:00:00",
            end_date="2025-01-02 23:59:59",
            provider="baostock",
            frequency="5m",
            interval="5m",
            schedule_run_id=schedule.id,
        )
        # create_fetch_bars_task 用 uuid4() 生成 task_id，重写为测试期望值便于断言
        row = QuantClientTask.get(QuantClientTask.task_id == created["task_id"])
        row.task_id = task_id
        row.status = "leased"
        row.client_id = "prod-local-client"
        row.save()

    @staticmethod
    def _post_report(auth_client, *, task_id: str, status: str, message: str, bundle_gz=None):
        """用 AuthClient 走 JSON 通道（用户/密码注入由 AuthClient 自动处理）。

        JSON 走第二个分支 (data.get("bundle") → dict → import_bundle)，
        也可以验证失败链路。
        """
        body = {
            "client_id": "prod-local-client",
            "task_id": task_id,
            "status": status,
            "message": message,
        }
        if bundle_gz is not None:
            body["bundle"] = _bundle_dict_for_json(bundle_gz)
        return auth_client.post(
            "/never_guess_my_usage/quant/client/tasks/report",
            json=body,
        )

    def test_import_bundle_failure_marks_task_as_failed(self, auth_client, test_db):
        """核心回归：import_bundle 抛异常时 task 必须从 leased → failed。

        修复前：import_bundle 抛 sqlite3.DatabaseError → error_response 返回，
        task 永远卡 leased → lease 过期后被 recycle → 新 agent 又 claim 同一个 task_id。
        修复后：同一个 except 里调用 mark_task_failed，task 状态终态、不会被反复执行。
        """
        task_id = _uuid.uuid4().hex
        self._setup_leased_task(task_id)

        # 模拟 import_bundle 抛 SQLite 损坏错误（线上 2026-09-11 真实故障场景）
        # patch 路径：路由在 `routes.quant.client_routes` 里 from-import 了 import_bundle，
        # 必须 patch 路由模块的本地绑定才能生效。
        with patch(
            "routes.quant.client_routes.import_bundle",
            side_effect=RuntimeError("database disk image is malformed"),
        ):
            resp = self._post_report(
                auth_client, task_id=task_id, status="success",
                message="采集并上报成功",
                bundle_gz=_build_bundle_gz(_make_minute_records()),
            )

        assert resp.status_code == 200
        body = resp.get_json()
        assert body["success"] is False
        assert "database disk image is malformed" in body["msg"]

        # 关键断言：task 状态必须从 leased 变成 failed
        task = QuantClientTask.get(QuantClientTask.task_id == task_id)
        assert task.status == "failed", (
            f"import_bundle 失败时 task 应被标记为 failed，实际为 {task.status}；"
            f"卡 leased 会被 _recycle_expired_leases 反复 recycle 造成同一 task 无限执行"
        )
        assert "database disk image is malformed" in task.message
        assert "RuntimeError" in task.message  # 异常类型带上，方便排查

    def test_import_bundle_success_marks_task_as_success(self, auth_client, test_db):
        """正常路径：import_bundle 成功时 task 标记为 success 且数据已入库。"""
        task_id = _uuid.uuid4().hex
        self._setup_leased_task(task_id)

        resp = self._post_report(
            auth_client, task_id=task_id, status="success",
            message="采集并上报成功",
            bundle_gz=_build_bundle_gz(_make_minute_records()),
        )

        assert resp.status_code == 200
        body = resp.get_json()
        assert body["success"] is True

        task = QuantClientTask.get(QuantClientTask.task_id == task_id)
        assert task.status == "success"
        assert task.import_batch_json != "{}"

    def test_explicit_failed_status_marks_task_as_failed(self, auth_client, test_db):
        """agent 主动上报失败时（status='failed'），task 立即标 failed。"""
        task_id = _uuid.uuid4().hex
        self._setup_leased_task(task_id)

        resp = self._post_report(
            auth_client, task_id=task_id, status="failed", message="数据源全部失败",
        )

        assert resp.status_code == 200
        assert resp.get_json()["success"] is True
        task = QuantClientTask.get(QuantClientTask.task_id == task_id)
        assert task.status == "failed"
        assert task.message == "数据源全部失败"

    def test_mark_failed_failure_does_not_crash_report(self, auth_client, test_db):
        """双重失败：import_bundle 抛异常 + mark_task_failed 也抛异常时，路由不能 500。"""
        task_id = _uuid.uuid4().hex
        self._setup_leased_task(task_id)

        with patch(
            "routes.quant.client_routes.import_bundle",
            side_effect=RuntimeError("import_bundle failed"),
        ), patch(
            "routes.quant.client_routes.mark_task_failed",
            side_effect=RuntimeError("mark_task_failed also broken"),
        ):
            resp = self._post_report(
                auth_client, task_id=task_id, status="success",
                message="test",
                bundle_gz=_build_bundle_gz(_make_minute_records()),
            )
        # 顶层 except 应该 catch 所有异常，路由返回 error_response
        assert resp.status_code == 200
        assert resp.get_json()["success"] is False
        assert "上报任务结果失败" in resp.get_json()["msg"]


def _bundle_dict_for_json(bundle_gz: bytes) -> dict:
    """把 bundle_gz bytes 解压回 dict，便于通过 JSON 通道走 import_bundle 第二个分支。"""
    import gzip
    raw = gzip.decompress(bundle_gz)
    return json.loads(raw.decode("utf-8"))