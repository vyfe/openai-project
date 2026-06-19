"""strategy_service 集成测试 — 验证策略 CRUD 和执行逻辑。"""

import json
import pytest

from service.quant.strategy_service import (
    create_strategy,
    list_strategies,
    get_strategy,
    update_strategy,
    delete_strategy,
    run_strategy,
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
