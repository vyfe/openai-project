"""飞书「加入股票池」指令 + 股票池写入 service 测试。"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from quant.entities import QuantInstrument
from service.quant.im_pool_service import handle_pool_command, strip_pool_prefix
from service.quant.instrument_pool_service import add_instruments_by_keywords, upsert_instrument


def _remote(code, name, market="SH"):
    return {
        "code": code,
        "name": name,
        "market": market,
        "symbol": f"{code}.{market}",
        "type": "沪A",
        "exchange": market,
    }


class TestStripPoolPrefix:
    """命令前缀识别。"""

    @pytest.mark.parametrize("text,expected", [
        ("加入,600519", "600519"),
        ("加池 贵州茅台", "贵州茅台"),
        ("添加,600519,000001", "600519,000001"),
        ("加自选，宁德时代", "宁德时代"),
        ("/加入,600519", "600519"),
        ("加入", ""),
    ])
    def test_matched(self, text, expected):
        assert strip_pool_prefix(text) == expected

    @pytest.mark.parametrize("text", [
        "加入茅台",          # 紧跟中文名，无分隔符 → 不认
        "买入,600519,100,10",
        "持仓",
        "",
    ])
    def test_not_matched(self, text):
        assert strip_pool_prefix(text) is None


class TestUpsertInstrument:
    def test_creates_new(self):
        saved = upsert_instrument("600519", name="贵州茅台", source="feishu:admin")
        assert saved["symbol"] == "600519.SH"
        assert saved["code"] == "600519"
        assert saved["name"] == "贵州茅台"
        assert saved["status"] == "active"
        assert saved["source"] == "feishu:admin"

    def test_idempotent_update_name(self):
        upsert_instrument("600519", name="旧名")
        saved = upsert_instrument("600519.SH", name="新名")
        assert saved["name"] == "新名"
        assert QuantInstrument.select().where(QuantInstrument.symbol == "600519.SH").count() == 1


class TestAddInstrumentsByKeywords:
    def test_adds_by_code_via_local_lookup(self):
        # 6 位裸代码在本地不存在时走远端搜索
        with patch(
            "service.quant.symbol_search_service.search_symbols_fallback",
            return_value=[_remote("600519", "贵州茅台")],
        ):
            result = add_instruments_by_keywords(["600519"], source="feishu:admin")
        assert len(result["added"]) == 1
        assert result["added"][0]["symbol"] == "600519.SH"
        assert result["failed"] == []

    def test_adds_by_chinese_name(self):
        with patch(
            "service.quant.symbol_search_service.search_symbols_fallback",
            return_value=[_remote("600519", "贵州茅台")],
        ):
            result = add_instruments_by_keywords(["贵州茅台"])
        assert result["added"][0]["code"] == "600519"

    def test_idempotent_reports_existing(self):
        upsert_instrument("600519", name="贵州茅台")
        with patch(
            "service.quant.symbol_search_service.search_symbols_fallback",
            return_value=[_remote("600519", "贵州茅台")],
        ) as spy:
            result = add_instruments_by_keywords(["600519"])
        assert result["added"] == []
        assert len(result["existing"]) == 1
        # 已在池中不该再打远端搜索
        assert spy.call_count == 0

    def test_ambiguous_returns_candidates(self):
        with patch(
            "service.quant.symbol_search_service.search_symbols_fallback",
            return_value=[_remote("600519", "贵州茅台"), _remote("600519", "贵州茅台B")],
        ):
            result = add_instruments_by_keywords(["茅台"])
        assert result["added"] == []
        assert len(result["failed"]) == 1
        assert "多只" in result["failed"][0]["reason"]
        assert result["failed"][0]["candidates"]

    def test_not_found_reports_reason(self):
        with patch(
            "service.quant.symbol_search_service.search_symbols_fallback",
            return_value=[],
        ):
            result = add_instruments_by_keywords(["不存在的票"])
        assert result["failed"][0]["keyword"] == "不存在的票"
        assert "未搜索到" in result["failed"][0]["reason"]

    def test_multiple_keywords_partial_failure(self):
        upsert_instrument("600519", name="贵州茅台")
        with patch(
            "service.quant.symbol_search_service.search_symbols_fallback",
            return_value=[],
        ):
            result = add_instruments_by_keywords(["600519", "000001"])
        assert len(result["existing"]) == 1
        assert len(result["failed"]) == 1

    def test_dedup_same_symbol_in_one_batch(self):
        with patch(
            "service.quant.symbol_search_service.search_symbols_fallback",
            return_value=[_remote("600519", "贵州茅台")],
        ):
            result = add_instruments_by_keywords(["600519", "600519.SH", "贵州茅台"])
        assert len(result["added"]) + len(result["existing"]) == 1


class TestHandlePoolCommand:
    def _parsed(self, sender_id="ou_test"):
        return {"sender_id": sender_id}

    def test_returns_none_for_non_pool_command(self):
        assert handle_pool_command("买入,600519,100,10", self._parsed()) is None

    def test_empty_arg_returns_usage(self, seed_admin_user):
        with patch("service.quant.im_operation_service.get_username_by_feishu", return_value="test_admin"):
            command, text = handle_pool_command("加入", self._parsed())
        assert command == "pool_usage"
        assert "用法" in text

    def test_requires_binding(self):
        with patch("service.quant.im_operation_service.get_username_by_feishu", return_value=None):
            with pytest.raises(ValueError, match="尚未绑定"):
                handle_pool_command("加入,600519", self._parsed())

    def test_adds_and_enqueues_backfill(self, seed_admin_user):
        with patch("service.quant.im_operation_service.get_username_by_feishu", return_value="test_admin"), patch(
            "service.quant.symbol_search_service.search_symbols_fallback",
            return_value=[_remote("600519", "贵州茅台")],
        ), patch(
            "service.quant.im_pool_service._enqueue_backfill"
        ) as spy_backfill:
            command, text = handle_pool_command("加入,600519", self._parsed())

        assert command == "pool_added"
        assert "600519" in text
        assert "已加入股票池" in text
        # 加入成功应排日线回补
        assert spy_backfill.call_count == 1
        assert spy_backfill.call_args.args[0] == ["600519.SH"]

    def test_backfill_failure_does_not_break_reply(self, seed_admin_user):
        """回补任务创建失败只记日志，加入成功的回复照常返回。"""
        with patch("service.quant.im_operation_service.get_username_by_feishu", return_value="test_admin"), patch(
            "service.quant.symbol_search_service.search_symbols_fallback",
            return_value=[_remote("600519", "贵州茅台")],
        ), patch(
            "service.quant.position_service.enqueue_position_backfill_task",
            side_effect=RuntimeError("队列挂了"),
        ):
            command, text = handle_pool_command("加入,600519", self._parsed())
        assert command == "pool_added"
        assert "已加入股票池" in text
        assert QuantInstrument.select().where(QuantInstrument.symbol == "600519.SH").count() == 1
