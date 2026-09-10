"""report_prompt_service.normalize_extra_sections 单元测试。

extra_sections 接受 list / JSON 字符串 / None；每项必须有 title；
最多保留 3 段；title 去空、去重；instruction 缺省视为 ""。
"""
from __future__ import annotations

from service.quant.report_prompt_service import (
    MAX_EXTRA_SECTIONS,
    normalize_extra_sections,
)


class TestNormalizeExtraSections:
    """规整逻辑容错性。"""

    def test_none_returns_empty(self):
        assert normalize_extra_sections(None) == []

    def test_empty_string_returns_empty(self):
        assert normalize_extra_sections("") == []

    def test_garbage_string_returns_empty(self):
        assert normalize_extra_sections("{not a json}") == []

    def test_valid_json_string(self):
        assert normalize_extra_sections('[{"title": "A", "instruction": "x"}]') == [
            {"title": "A", "instruction": "x"}
        ]

    def test_list_input(self):
        assert normalize_extra_sections([{"title": "A", "instruction": "x"}]) == [
            {"title": "A", "instruction": "x"}
        ]

    def test_non_list_non_string_returns_empty(self):
        assert normalize_extra_sections({"title": "A"}) == []
        assert normalize_extra_sections(42) == []

    def test_instruction_defaults_to_empty_string(self):
        assert normalize_extra_sections([{"title": "A"}]) == [
            {"title": "A", "instruction": ""}
        ]

    def test_empty_title_dropped(self):
        assert normalize_extra_sections([{"title": "", "instruction": "x"}]) == []
        assert normalize_extra_sections([{"title": "  ", "instruction": "x"}]) == []

    def test_non_dict_items_dropped(self):
        assert normalize_extra_sections([{"title": "A"}, "not a dict", None, 42]) == [
            {"title": "A", "instruction": ""}
        ]

    def test_duplicate_titles_dedup_keep_first(self):
        result = normalize_extra_sections([
            {"title": "A", "instruction": "first"},
            {"title": "A", "instruction": "second"},
        ])
        assert result == [{"title": "A", "instruction": "first"}]

    def test_max_three_sections_enforced(self):
        items = [{"title": f"t{i}", "instruction": str(i)} for i in range(5)]
        result = normalize_extra_sections(items)
        assert len(result) == MAX_EXTRA_SECTIONS == 3
        assert [r["title"] for r in result] == ["t0", "t1", "t2"]

    def test_trims_whitespace_in_title(self):
        result = normalize_extra_sections([{"title": "  风险矩阵  ", "instruction": "x"}])
        assert result == [{"title": "风险矩阵", "instruction": "x"}]

    def test_trims_whitespace_in_instruction(self):
        result = normalize_extra_sections([{"title": "A", "instruction": "  hello  "}])
        assert result == [{"title": "A", "instruction": "hello"}]

    def test_unicode_round_trip(self):
        result = normalize_extra_sections([
            {"title": "风险矩阵", "instruction": "以表格列出强度/概率/影响"}
        ])
        assert result == [{"title": "风险矩阵", "instruction": "以表格列出强度/概率/影响"}]