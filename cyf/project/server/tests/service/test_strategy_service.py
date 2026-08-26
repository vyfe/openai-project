"""strategy_service 集成测试 — 验证策略 CRUD 和执行逻辑。"""

import json
import pytest

from service.quant.strategy_service import (
    batch_soft_delete_instruments,
    count_available_symbols,
    create_strategy,
    delete_strategy,
    get_strategy,
    list_available_symbols,
    list_strategies,
    run_strategy,
    soft_delete_instrument,
    update_strategy,
)


class TestCreateStrategy:
    """测试创建策略。"""

    def test_create_basic(self):
        result = create_strategy(name="MA突破", symbols=["000001.SZ"], rule_config={"logic": "all", "rules": []})
        assert result["id"] > 0
        assert result["name"] == "MA突破"
        assert result["status"] == "active"

    def test_create_with_description(self):
        result = create_strategy(name="测试策略", description="描述文本")
        assert result["description"] == "描述文本"

    def test_create_normalizes_symbols(self):
        result = create_strategy(name="S", symbols=["000001"])
        assert result["symbols"] == ["000001.SZ"]


class TestListStrategies:
    """测试列出策略。"""

    def test_empty_list(self):
        result = list_strategies()
        assert result == []

    def test_list_after_create(self):
        create_strategy(name="A")
        create_strategy(name="B")
        result = list_strategies()
        assert len(result) == 2

    def test_filter_by_status(self):
        create_strategy(name="Active", status="active")
        create_strategy(name="Inactive", status="inactive")
        result = list_strategies(status="active")
        assert len(result) == 1
        assert result[0]["name"] == "Active"


class TestGetStrategy:
    """测试获取单个策略。"""

    def test_get_existing(self):
        created = create_strategy(name="G")
        result = get_strategy(created["id"])
        assert result["name"] == "G"

    def test_get_nonexistent_raises(self):
        with pytest.raises(Exception):
            get_strategy(99999)


class TestUpdateStrategy:
    """测试更新策略。"""

    def test_update_name(self):
        created = create_strategy(name="Old")
        result = update_strategy(created["id"], name="New")
        assert result["name"] == "New"

    def test_update_status(self):
        created = create_strategy(name="S")
        result = update_strategy(created["id"], status="inactive")
        assert result["status"] == "inactive"

    def test_update_rule_config(self):
        created = create_strategy(name="S")
        new_rules = {"logic": "any", "rules": [{"rule_type": "field_compare"}]}
        result = update_strategy(created["id"], rule_config=new_rules)
        assert result["rule_config"]["logic"] == "any"


class TestDeleteStrategy:
    """测试删除策略。"""

    def test_delete_removes_strategy(self):
        created = create_strategy(name="ToDelete")
        delete_strategy(created["id"])
        result = list_strategies()
        assert len(result) == 0


class TestRunStrategy:
    """测试策略执行。"""

    def test_run_without_data_raises(self):
        """无行情数据时应抛出异常。"""
        strategy = create_strategy(
            name="NoData",
            symbols=["000001.SZ"],
            rule_config={"logic": "all", "rules": [{"rule_type": "field_compare", "field": "pct_change", "operator": ">=", "value": 2.0}]},
        )
        with pytest.raises(ValueError, match="无可用行情数据"):
            run_strategy(strategy["id"])

    def test_run_inactive_strategy_raises(self):
        """未启用策略应抛出异常。"""
        strategy = create_strategy(name="Inactive", status="inactive")
        with pytest.raises(ValueError, match="策略未启用"):
            run_strategy(strategy["id"])

    def test_run_with_seed_data(self, seed_daily_bars):
        """有行情数据时策略执行成功。"""
        strategy = create_strategy(
            name="MABreak",
            symbols=["000001.SZ", "600519.SH"],
            rule_config={"logic": "any", "rules": [
                {"rule_type": "field_compare", "field": "pct_change", "operator": ">=", "value": 0.0},
            ]},
        )
        result = run_strategy(strategy["id"])
        assert result["status"] == "success"
        assert result["id"] > 0


# ---------------------------------------------------------------------------
# 股票池管理
# ---------------------------------------------------------------------------


def _seed_symbol(symbol: str, name: str = "", source: str = "test"):
    """在 quant_instrument 表里塞一条 active 记录，返回 db 行。"""
    from datetime import datetime
    from quant.entities import QuantInstrument

    code, exchange = symbol.split(".", 1)
    now = datetime.now()
    QuantInstrument.insert(
        symbol=symbol,
        code=code,
        exchange=exchange,
        market="A_SHARE",
        name=name,
        source=source,
        status="active",
        created_at=now,
        updated_at=now,
    ).on_conflict_ignore().execute()
    return QuantInstrument.get(QuantInstrument.symbol == symbol)


class TestStockPoolList:
    """list_available_symbols / count_available_symbols 的过滤与分页行为。"""

    def test_lists_only_active_symbols(self):
        _seed_symbol("600000.SH", "浦发")
        _seed_symbol("600001.SH", "邯钢")
        rows = list_available_symbols()
        symbols = {row["symbol"] for row in rows}
        assert "600000.SH" in symbols
        assert "600001.SH" in symbols

    def test_keyword_matches_symbol_code_and_name(self):
        _seed_symbol("600000.SH", "浦发银行")
        _seed_symbol("000001.SZ", "平安银行")
        # symbol 模糊
        assert any(r["symbol"] == "600000.SH" for r in list_available_symbols(keyword="600"))
        # code 模糊
        assert any(r["symbol"] == "000001.SZ" for r in list_available_symbols(keyword="000001"))
        # name 模糊
        assert any(r["symbol"] == "600000.SH" for r in list_available_symbols(keyword="浦发"))

    def test_count_matches_list_total(self):
        _seed_symbol("600010.SH", "A")
        _seed_symbol("600020.SH", "B")
        _seed_symbol("600030.SH", "C")
        total = count_available_symbols()
        rows = list_available_symbols(limit=100, offset=0)
        assert total == len(rows) >= 3

    def test_offset_paginates(self):
        _seed_symbol("600100.SH", "X1")
        _seed_symbol("600101.SH", "X2")
        _seed_symbol("600102.SH", "X3")
        page1 = list_available_symbols(limit=2, offset=0)
        page2 = list_available_symbols(limit=2, offset=2)
        assert len(page1) == 2
        assert len(page2) >= 1
        # 不可重叠
        symbols1 = {r["symbol"] for r in page1}
        symbols2 = {r["symbol"] for r in page2}
        assert symbols1.isdisjoint(symbols2)


class TestStockPoolDelete:
    """soft_delete_instrument / batch_soft_delete_instruments 的语义。"""

    def test_single_delete_returns_true(self):
        _seed_symbol("600200.SH", "待删")
        assert soft_delete_instrument("600200.SH") is True
        # 重复删返回 False（已经是 deleted）
        assert soft_delete_instrument("600200.SH") is False

    def test_single_delete_missing_returns_false(self):
        assert soft_delete_instrument("999999.SH") is False

    def test_batch_delete_partitions_deleted_vs_missing(self):
        _seed_symbol("600300.SH", "活")
        _seed_symbol("600301.SH", "活")
        # 600302 不存在
        result = batch_soft_delete_instruments(["600300.SH", "600301.SH", "600302.SH", ""])
        assert set(result["deleted"]) == {"600300.SH", "600301.SH"}
        assert "600302.SH" in result["missing"]
        # 空字符串不应出现在 deleted 里
        assert "" not in result["deleted"]

    def test_batch_delete_empty_returns_empty(self):
        assert batch_soft_delete_instruments([]) == {"deleted": [], "missing": []}
        assert batch_soft_delete_instruments(None) == {"deleted": [], "missing": []}
