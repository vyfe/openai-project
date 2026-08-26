"""query_service 周线聚合回归测试。"""

from datetime import date

from service.quant.query_service import _aggregate_weekly_bars


def _daily(date_str: str, open_, high, low, close, volume=1000.0, amount=1_000_000.0, source="baostock"):
    return {
        "symbol": "600519.SH",
        "code": "600519",
        "exchange": "SH",
        "trade_date": date.fromisoformat(date_str),
        "adjust_flag": "qfq",
        "open_price": open_,
        "high_price": high,
        "low_price": low,
        "close_price": close,
        "preclose_price": None,
        "volume": volume,
        "amount": amount,
        "turnover_rate": None,
        "pct_change": None,
        "source": source,
        "data_source_version": "v1",
    }


class TestWeeklyAggregationBasics:
    """周线聚合基础：单周、跨周、pct 回填。"""

    def test_empty_returns_empty(self):
        assert _aggregate_weekly_bars([]) == []

    def test_single_iso_week_collapses_into_one_bar(self):
        rows = [
            _daily("2025-01-13", 10, 11, 9, 10.5, volume=1000),  # 周一
            _daily("2025-01-14", 10.5, 11.5, 10, 11, volume=1200),
            _daily("2025-01-15", 11, 12, 10.5, 11.8, volume=1500),
            _daily("2025-01-16", 11.8, 12.2, 11.5, 12, volume=1300),
            _daily("2025-01-17", 12, 13, 11.8, 12.5, volume=2000),  # 周五
        ]
        out = _aggregate_weekly_bars(rows)
        assert len(out) == 1
        bar = out[0]
        assert bar["trade_date"] == "2025-01-17"
        assert bar["open_price"] == 10.0
        assert bar["close_price"] == 12.5
        assert bar["high_price"] == 13.0
        assert bar["low_price"] == 9.0
        assert bar["volume"] == 1000 + 1200 + 1500 + 1300 + 2000
        # 首根周线 pct_change 为 None，preclose 是本周 open 占位
        assert bar["pct_change"] is None
        assert bar["preclose_price"] == 10.0

    def test_two_iso_weeks_yield_two_bars_in_ascending_order(self):
        rows = [
            _daily("2025-01-15", 100, 105, 99, 102, volume=1000),
            _daily("2025-01-16", 102, 108, 101, 107, volume=1200),
            _daily("2025-01-17", 107, 110, 106, 109, volume=1500),  # 第一周周五
            _daily("2025-01-20", 109, 112, 108, 111, volume=1300),  # 第二周周一
            _daily("2025-01-21", 111, 115, 110, 114, volume=1400),
            _daily("2025-01-22", 114, 117, 113, 116, volume=1600),
            _daily("2025-01-23", 116, 118, 115, 117, volume=1800),
            _daily("2025-01-24", 117, 120, 116, 119, volume=2000),  # 第二周周五
        ]
        out = _aggregate_weekly_bars(rows)
        assert [b["trade_date"] for b in out] == ["2025-01-17", "2025-01-24"]
        # 第一周
        assert out[0]["open_price"] == 100
        assert out[0]["close_price"] == 109
        assert out[0]["high_price"] == 110
        assert out[0]["low_price"] == 99
        # 第二周
        assert out[1]["open_price"] == 109
        assert out[1]["close_price"] == 119
        # 第二周的 preclose/pct 应回填自第一周 close=109
        assert out[1]["preclose_price"] == 109
        assert abs(out[1]["pct_change"] - (119 - 109) / 109 * 100) < 1e-6

    def test_input_order_does_not_matter(self):
        rows_desc = [
            _daily("2025-01-17", 12, 13, 11.8, 12.5, volume=2000),
            _daily("2025-01-16", 11.8, 12.2, 11.5, 12, volume=1300),
            _daily("2025-01-15", 11, 12, 10.5, 11.8, volume=1500),
            _daily("2025-01-14", 10.5, 11.5, 10, 11, volume=1200),
            _daily("2025-01-13", 10, 11, 9, 10.5, volume=1000),
        ]
        out = _aggregate_weekly_bars(rows_desc)
        assert len(out) == 1
        assert out[0]["trade_date"] == "2025-01-17"
        assert out[0]["open_price"] == 10.0
        assert out[0]["close_price"] == 12.5


class TestWeeklyEdgeCases:
    """周线聚合的边界：跨年周、稀疏交易日、缺失字段。"""

    def test_cross_year_iso_weeks_grouped_by_isocalendar(self):
        # 2024-12-30 (一) ~ 2025-01-03 (五) 同属 ISO 2025-W01
        rows = [
            _daily("2024-12-30", 100, 101, 99, 100.5),
            _daily("2024-12-31", 100.5, 102, 100, 101.5),
            _daily("2025-01-02", 101.5, 103, 101, 102.5),
            _daily("2025-01-03", 102.5, 104, 102, 103.5),
        ]
        out = _aggregate_weekly_bars(rows)
        assert len(out) == 1
        # 方案 A：本周最后一个交易日 = 2025-01-03
        assert out[0]["trade_date"] == "2025-01-03"
        assert out[0]["open_price"] == 100
        assert out[0]["close_price"] == 103.5

    def test_short_week_with_missing_trading_days(self):
        # 本周只有 3 个交易日（节后开市），仍要聚合成 1 根
        rows = [
            _daily("2025-02-05", 50, 51, 49, 50.5),  # 周三
            _daily("2025-02-06", 50.5, 52, 50, 51.5),  # 周四
            _daily("2025-02-07", 51.5, 53, 51, 52.5),  # 周五
        ]
        out = _aggregate_weekly_bars(rows)
        assert len(out) == 1
        assert out[0]["trade_date"] == "2025-02-07"
        assert out[0]["open_price"] == 50
        assert out[0]["close_price"] == 52.5

    def test_handles_missing_high_low_in_some_rows(self):
        rows = [
            _daily("2025-03-10", 10, 11, 9, 10.5, volume=100),
            _daily("2025-03-11", 10.5, None, None, 11),  # 高低缺失
            _daily("2025-03-12", 11, 12, 10.5, 11.8),
            _daily("2025-03-13", 11.8, 12.2, 11.5, 12),
            _daily("2025-03-14", 12, 13, 11.8, 12.5),
        ]
        out = _aggregate_weekly_bars(rows)
        # high 应跳过 None 取 13；low 应跳过 None 仍取到 9（None 不参与 min 比较）
        assert out[0]["high_price"] == 13
        assert out[0]["low_price"] == 9

    def test_preserves_symbol_and_source(self):
        rows = [
            _daily("2025-04-14", 10, 11, 9, 10.5, source="yahoo"),
            _daily("2025-04-15", 10.5, 11.5, 10, 11, source="yahoo"),
            _daily("2025-04-16", 11, 12, 10.5, 11.8, source="yahoo"),
            _daily("2025-04-17", 11.8, 12.2, 11.5, 12, source="yahoo"),
            _daily("2025-04-18", 12, 13, 11.8, 12.5, source="yahoo"),
        ]
        rows[0]["symbol"] = "000300.SH"
        rows[0]["code"] = "000300"
        rows[0]["exchange"] = "SH"
        out = _aggregate_weekly_bars(rows)
        assert out[0]["symbol"] == "000300.SH"
        assert out[0]["code"] == "000300"
        assert out[0]["exchange"] == "SH"
        assert out[0]["source"] == "yahoo"

    def test_handles_string_trade_date_from_db_to_dict(self):
        """模拟 DB 查询：trade_date 经 .to_dict() 后变成字符串。回归 .isoformat() 报错。"""
        rows = [
            {
                "symbol": "600519.SH", "code": "600519", "exchange": "SH",
                "trade_date": "2025-05-12",  # 字符串！
                "adjust_flag": "qfq",
                "open_price": 10, "high_price": 11, "low_price": 9, "close_price": 10.5,
                "volume": 1000, "amount": 1_000_000,
                "source": "baostock", "data_source_version": "v1",
            },
            {
                "symbol": "600519.SH", "code": "600519", "exchange": "SH",
                "trade_date": "2025-05-13",
                "adjust_flag": "qfq",
                "open_price": 10.5, "high_price": 11.5, "low_price": 10, "close_price": 11,
                "volume": 1200, "amount": 1_200_000,
                "source": "baostock", "data_source_version": "v1",
            },
            {
                "symbol": "600519.SH", "code": "600519", "exchange": "SH",
                "trade_date": "2025-05-14",
                "adjust_flag": "qfq",
                "open_price": 11, "high_price": 12, "low_price": 10.5, "close_price": 11.8,
                "volume": 1500, "amount": 1_500_000,
                "source": "baostock", "data_source_version": "v1",
            },
            {
                "symbol": "600519.SH", "code": "600519", "exchange": "SH",
                "trade_date": "2025-05-15",
                "adjust_flag": "qfq",
                "open_price": 11.8, "high_price": 12.2, "low_price": 11.5, "close_price": 12,
                "volume": 1300, "amount": 1_300_000,
                "source": "baostock", "data_source_version": "v1",
            },
            {
                "symbol": "600519.SH", "code": "600519", "exchange": "SH",
                "trade_date": "2025-05-16",
                "adjust_flag": "qfq",
                "open_price": 12, "high_price": 13, "low_price": 11.8, "close_price": 12.5,
                "volume": 2000, "amount": 2_000_000,
                "source": "baostock", "data_source_version": "v1",
            },
        ]
        out = _aggregate_weekly_bars(rows)
        assert len(out) == 1
        # 关键回归断言：trade_date 必须是 ISO 字符串而不是 date 对象
        assert isinstance(out[0]["trade_date"], str)
        assert out[0]["trade_date"] == "2025-05-16"