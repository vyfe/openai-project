"""quant_client.cli.cmd_run_once 行为测试（mock 掉外部依赖）。

覆盖点：
1. task_type=fetch_a_share_minute_bars 不再被白名单拦下
2. payload 里的 frequency / interval 透传给 build_fetch_bundle
3. task_type 与 payload.frequency 一致时按 frequency 透传
4. payload 没带 frequency 但 task_type 是 minute 时，回退到 5m
"""

import json
from unittest.mock import patch

import pytest

from quant_client import cli


def _make_namespace(**kwargs):
    """构造 argparse.Namespace 子类，覆盖默认值。"""
    defaults = dict(
        server_url="http://localhost:39997",
        client_id="test-client",
        token="",
        user="admin",
        password="admin123",
        timeout=60,
    )
    defaults.update(kwargs)
    # argparse.Namespace 不允许 __init__ kwargs 之外的写法；用 SimpleNamespace 替代
    from types import SimpleNamespace
    return SimpleNamespace(**defaults)


def _build_mock_client(claim_task_result, *, success_result=None, failure_result=None):
    """构造一个 QuantTaskClient mock 实例。"""

    class _MockClient:
        def __init__(self, *args, **kwargs):
            pass

        def claim_task(self, client_id, capabilities=None):
            return claim_task_result

        def report_task_success(self, client_id, task_id, bundle, message=""):
            return success_result or {"success": True, "task_id": task_id}

        def report_task_failure(self, client_id, task_id, message):
            return failure_result or {"success": False, "task_id": task_id, "message": message}

    return _MockClient()


class TestCmdRunOnceFrequencyDispatch:
    def test_daily_task_passes_frequency_1d(self, capsys):
        """1d 任务：build_fetch_bundle 应被以 frequency=1d 调用。"""
        captured = {}

        def fake_build_fetch_bundle(**kwargs):
            captured.update(kwargs)
            return {"records": [{"x": 1}], "dataset": "a_share_daily_bars_v1"}

        mock_client = _build_mock_client(
            claim_task_result={
                "success": True,
                "data": {
                    "task_id": "t1",
                    "task_type": "fetch_a_share_daily_bars",
                    "payload": {
                        "provider": "auto",
                        "symbols": ["600519.SH"],
                        "start_date": "2024-01-02",
                        "end_date": "2024-01-03",
                        "adjust_flag": "qfq",
                    },
                },
            }
        )
        with patch.object(cli, "_build_client", return_value=mock_client), \
             patch.object(cli, "build_fetch_bundle", side_effect=fake_build_fetch_bundle):
            cli.cmd_run_once(_make_namespace())
        assert captured["frequency"] == "1d"
        assert captured["interval"] == "5m"  # 默认值
        assert captured["provider_name"] == "auto"
        assert captured["symbols"] == ["600519.SH"]

    def test_minute_task_passes_frequency_5m(self, capsys):
        """minute 任务：build_fetch_bundle 应被以 frequency=5m 调用（不再是旧白名单拒绝）。"""
        captured = {}

        def fake_build_fetch_bundle(**kwargs):
            captured.update(kwargs)
            return {"records": [], "dataset": "a_share_5min_bars_v1"}

        mock_client = _build_mock_client(
            claim_task_result={
                "success": True,
                "data": {
                    "task_id": "t2",
                    "task_type": "fetch_a_share_minute_bars",
                    "payload": {
                        "provider": "auto",
                        "symbols": ["600519.SH"],
                        "start_date": "2024-01-02 14:00",
                        "end_date": "2024-01-02 15:00",
                        "adjust_flag": "qfq",
                        "frequency": "5m",
                        "interval": "5m",
                    },
                },
            }
        )
        with patch.object(cli, "_build_client", return_value=mock_client), \
             patch.object(cli, "build_fetch_bundle", side_effect=fake_build_fetch_bundle):
            cli.cmd_run_once(_make_namespace())
        # 关键：frequency 被透传为 5m（不再被白名单拦下）
        assert captured["frequency"] == "5m"
        assert captured["interval"] == "5m"

    def test_minute_task_inferred_from_task_type_when_payload_missing_frequency(self, capsys):
        """payload 没带 frequency 但 task_type 是 minute 时，回退到 5m（向后兼容旧任务记录）。"""
        captured = {}

        def fake_build_fetch_bundle(**kwargs):
            captured.update(kwargs)
            return {"records": [], "dataset": "a_share_5min_bars_v1"}

        mock_client = _build_mock_client(
            claim_task_result={
                "success": True,
                "data": {
                    "task_id": "t3",
                    "task_type": "fetch_a_share_minute_bars",
                    "payload": {
                        "provider": "auto",
                        "symbols": ["600519.SH"],
                        "start_date": "2024-01-02 14:00",
                        "end_date": "2024-01-02 15:00",
                        "adjust_flag": "qfq",
                        # 注意：故意不带 frequency
                    },
                },
            }
        )
        with patch.object(cli, "_build_client", return_value=mock_client), \
             patch.object(cli, "build_fetch_bundle", side_effect=fake_build_fetch_bundle):
            cli.cmd_run_once(_make_namespace())
        # task_type → frequency 反查应得到 "5m"
        assert captured["frequency"] == "5m"

    def test_unsupported_task_type_reports_failure(self, capsys):
        """未知 task_type 仍然要被拒绝并上报失败。"""
        captured = {}

        def fake_build_fetch_bundle(**kwargs):
            captured["called"] = True
            return {"records": []}

        captured_fail = {}

        class _MockClient:
            def __init__(self, *args, **kwargs):
                pass

            def claim_task(self, *a, **kw):
                return {"success": True, "data": {"task_id": "t-bad", "task_type": "fetch_unknown_type", "payload": {}}}

            def report_task_failure(self, client_id, task_id, message):
                captured_fail["task_id"] = task_id
                captured_fail["message"] = message
                return {"success": True}

        with patch.object(cli, "_build_client", return_value=_MockClient()), \
             patch.object(cli, "build_fetch_bundle", side_effect=fake_build_fetch_bundle):
            cli.cmd_run_once(_make_namespace())
        assert "called" not in captured  # 没调过 build_fetch_bundle
        assert captured_fail["task_id"] == "t-bad"
        assert "不支持的任务类型" in captured_fail["message"]