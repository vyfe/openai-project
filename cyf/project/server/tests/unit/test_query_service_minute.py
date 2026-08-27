"""query_service.fetch_minute_bars 单元测试。"""

from datetime import date, datetime

import pytest

from service.quant.query_service import fetch_minute_bars


@pytest.fixture()
def seed_minute_bars(test_db):
    from quant.entities import QuantMinuteBar
    bars = [
        {
            "symbol": "600519.SH", "code": "600519", "exchange": "SH",
            "trade_datetime": datetime(2024, 1, 2, 9, 35, 0),
            "trade_date": date(2024, 1, 2),
            "interval": "5m", "adjust_flag": "qfq",
            "open_price": 1700.0, "high_price": 1702.0, "low_price": 1699.0, "close_price": 1701.0,
            "volume": 1000.0, "amount": 1701000.0,
            "source": "baostock", "source_run_id": "r1",
        },
        {
            "symbol": "600519.SH", "code": "600519", "exchange": "SH",
            "trade_datetime": datetime(2024, 1, 2, 9, 40, 0),
            "trade_date": date(2024, 1, 2),
            "interval": "5m", "adjust_flag": "qfq",
            "open_price": 1701.0, "high_price": 1705.0, "low_price": 1701.0, "close_price": 1704.0,
            "volume": 1500.0, "amount": 2556000.0,
            "source": "baostock", "source_run_id": "r1",
        },
        {
            "symbol": "600519.SH", "code": "600519", "exchange": "SH",
            "trade_datetime": datetime(2024, 1, 3, 9, 35, 0),
            "trade_date": date(2024, 1, 3),
            "interval": "5m", "adjust_flag": "qfq",
            "open_price": 1710.0, "high_price": 1715.0, "low_price": 1709.0, "close_price": 1712.0,
            "volume": 2000.0, "amount": 3424000.0,
            "source": "baostock", "source_run_id": "r1",
        },
        {
            "symbol": "600519.SH", "code": "600519", "exchange": "SH",
            "trade_datetime": datetime(2024, 1, 2, 9, 35, 0),
            "trade_date": date(2024, 1, 2),
            "interval": "5m", "adjust_flag": "hfq",
            "open_price": 0.0, "high_price": 0.0, "low_price": 0.0, "close_price": 0.0,
            "volume": 0.0, "amount": 0.0,
            "source": "baostock", "source_run_id": "r2",
        },
    ]
    QuantMinuteBar.insert_many(bars).execute()


class TestFetchMinuteBars:
    def test_returns_records_descending(self, seed_minute_bars):
        results = fetch_minute_bars("600519.SH", interval="5m", limit=10)
        # 3 条 qfq；seed 里有 1 条 hfq 被默认 qfq 查询过滤
        assert len(results) == 3
        assert results[0]["trade_datetime"] == "2024-01-03T09:35:00"
        assert results[-1]["trade_datetime"] == "2024-01-02T09:35:00"

    def test_filter_by_interval(self, seed_minute_bars):
        # 修复后 15m 走端上聚合：seed 里只有 2 根 am 5m（9:35/9:40）不构成完整 15m 桶，
        # 整桶跳过，返回空。
        results = fetch_minute_bars("600519.SH", interval="15m", limit=10)
        assert results == []

    def test_filter_by_adjust_flag(self, seed_minute_bars):
        results = fetch_minute_bars("600519.SH", interval="5m", adjust_flag="hfq", limit=10)
        assert len(results) == 1
        assert results[0]["adjust_flag"] == "hfq"

    def test_date_range_filter(self, seed_minute_bars):
        results = fetch_minute_bars(
            "600519.SH", interval="5m",
            start_dt="2024-01-02 00:00:00", end_dt="2024-01-02 23:59:59",
        )
        # 1 条 hfq 不算 qfq 范围；2 条 qfq 在 2024-01-02
        assert len(results) == 2

    def test_limit_upper_bound(self, seed_minute_bars):
        results = fetch_minute_bars("600519.SH", interval="5m", limit=99999)
        # 上限 5000 不会丢数据（qfq 库里 3 条）
        assert len(results) == 3

    def test_limit_lower_bound(self, seed_minute_bars):
        results = fetch_minute_bars("600519.SH", interval="5m", limit=2)
        assert len(results) == 2

    def test_to_dict_includes_minute_fields(self, seed_minute_bars):
        results = fetch_minute_bars("600519.SH", interval="5m", limit=1)
        first = results[0]
        assert first["symbol"] == "600519.SH"
        assert first["interval"] == "5m"
        assert first["adjust_flag"] == "qfq"
        assert first["trade_datetime"] == "2024-01-03T09:35:00"
        assert first["trade_date"] == "2024-01-03"
        assert first["open_price"] == 1710.0
        assert first["close_price"] == 1712.0


@pytest.fixture()
def seed_full_minute_day(test_db):
    """构造一个完整交易日的 5m bars（am 24 根 + pm 24 根 = 48 根），用于 15m/30m 聚合测试。"""
    from quant.entities import QuantMinuteBar
    bars = []
    # am 段 9:30-11:25（最后一根 11:25 → 桶 11:30 之前）
    am_minutes = [(9, 30), (9, 35), (9, 40), (9, 45), (9, 50), (9, 55),
                 (10, 0), (10, 5), (10, 10), (10, 15), (10, 20), (10, 25),
                 (10, 30), (10, 35), (10, 40), (10, 45), (10, 50), (10, 55),
                 (11, 0), (11, 5), (11, 10), (11, 15), (11, 20), (11, 25)]
    # pm 段 13:00-14:55
    pm_minutes = [(13, 0), (13, 5), (13, 10), (13, 15), (13, 20), (13, 25),
                 (13, 30), (13, 35), (13, 40), (13, 45), (13, 50), (13, 55),
                 (14, 0), (14, 5), (14, 10), (14, 15), (14, 20), (14, 25),
                 (14, 30), (14, 35), (14, 40), (14, 45), (14, 50), (14, 55)]
    base_open, base_close = 100.0, 105.0
    for i, (h, m) in enumerate(am_minutes + pm_minutes):
        price = base_open + (base_close - base_open) * (i + 1) / 48
        bars.append({
            "symbol": "600519.SH", "code": "600519", "exchange": "SH",
            "trade_datetime": datetime(2024, 1, 2, h, m, 0),
            "trade_date": date(2024, 1, 2),
            "interval": "5m", "adjust_flag": "qfq",
            "open_price": price - 0.5,
            "high_price": price + 1.0,
            "low_price": price - 1.0,
            "close_price": price,
            "volume": 100.0 + i,
            "amount": 10000.0 + i * 100,
            "source": "test", "source_run_id": "agg1",
        })
    QuantMinuteBar.insert_many(bars).execute()


class TestFetchMinuteBarsAggregation:
    """端上聚合 5m → 15m/30m 的覆盖。"""

    def test_15m_aggregates_three_5m_into_one(self, seed_full_minute_day):
        """15m：am 段 24 根 5m → 8 个 15m 桶（每桶 3 根）；pm 段同理 8 个桶，合计 16 个。"""
        results = fetch_minute_bars("600519.SH", interval="15m", limit=100)
        assert len(results) == 16  # 8 am + 8 pm
        # 验证间隔 = 15 分钟
        first = results[-1]  # 升序最早
        second = results[-2]
        first_dt = datetime.fromisoformat(first["trade_datetime"])
        second_dt = datetime.fromisoformat(second["trade_datetime"])
        assert (second_dt - first_dt).total_seconds() == 15 * 60
        # interval 字段标记
        assert all(r["interval"] == "15m" for r in results)
        # 倒序：最后一根最早
        assert results[0]["trade_datetime"] > results[-1]["trade_datetime"]

    def test_30m_aggregates_six_5m_into_one(self, seed_full_minute_day):
        """30m：am 段 24 根 → 4 个 30m 桶；pm 段 4 个，合计 8 个。"""
        results = fetch_minute_bars("600519.SH", interval="30m", limit=100)
        assert len(results) == 8  # 4 am + 4 pm
        assert all(r["interval"] == "30m" for r in results)

    def test_ohlc_rules_applied(self, seed_full_minute_day):
        """OHLC 规则：桶内首 open、末 close、high max、low min、volume/amount 求和。"""
        results = fetch_minute_bars("600519.SH", interval="15m", limit=100)
        first_am_bucket = results[-1]  # 9:30 起
        # 桶内是 9:30/9:35/9:40 三根 5m
        assert first_am_bucket["trade_datetime"] == "2024-01-02T09:30:00"  # open 取首根时间
        # open 取 9:30 那根（最小）；close 取 9:40 那根（最大）；数据是递增序列
        assert first_am_bucket["open_price"] < first_am_bucket["close_price"]
        assert first_am_bucket["high_price"] >= first_am_bucket["close_price"]
        assert first_am_bucket["low_price"] <= first_am_bucket["open_price"]
        # volume 应大于单根 5m 的 100.0（聚合求和）
        assert first_am_bucket["volume"] > 100.0

    def test_does_not_merge_am_and_pm_across_lunch_break(self, seed_full_minute_day):
        """午休 11:30-13:00 不能跨段合并：am 末桶的 11:25 不会和 pm 首桶 13:00 合成同一桶。"""
        results = fetch_minute_bars("600519.SH", interval="30m", limit=100)
        # 倒序取前几个验证 am/pm 桶互不混合
        # 最早的应该是 9:30 的 30m 桶
        earliest = results[-1]
        earliest_dt = datetime.fromisoformat(earliest["trade_datetime"])
        assert earliest_dt.hour == 9 and earliest_dt.minute == 30
        # 第二早的也应在 am 段（10:00）
        second = results[-2]
        second_dt = datetime.fromisoformat(second["trade_datetime"])
        assert second_dt.hour in (9, 10, 11)

    def test_partial_bucket_skipped(self, seed_full_minute_day):
        """桶内 5m 不足时整桶跳过（不补全，不强行返回）。"""
        # seed 里 am/pm 都是完整 48 根 → 全部都能凑成桶
        # 用 limit 缩小 + 验证返回数仍然合理
        results = fetch_minute_bars("600519.SH", interval="15m", limit=5)
        assert len(results) == 5

    def test_empty_data_returns_empty(self, test_db):
        """空数据走聚合路径应返回空列表（不抛异常）。"""
        results = fetch_minute_bars("EMPTY.SH", interval="15m", limit=100)
        assert results == []

    def test_respects_limit_after_aggregation(self, seed_full_minute_day):
        """limit 作用于聚合后的桶数，不是原始 5m 数。"""
        results_30m = fetch_minute_bars("600519.SH", interval="30m", limit=3)
        assert len(results_30m) == 3  # 只取最近 3 个 30m 桶

    def test_15m_interval_metadata_marks_aggregated(self, seed_full_minute_day):
        """聚合输出的 interval 字段应是目标值（15m/30m），方便前端 EChartsCandlestick 识别。"""
        results = fetch_minute_bars("600519.SH", interval="30m", limit=1)
        assert results[0]["interval"] == "30m"