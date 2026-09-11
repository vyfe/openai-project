"""Indicators API 路由集成测试（compute + list 端点）。"""

from datetime import date, datetime, timedelta

import pytest

from quant.entities import QuantDailyBar, QuantMinuteBar


def _build_bars(n: int = 30):
    """构造单调上涨的 K 线用于 compute 端点测试。"""
    bars = []
    for i in range(n):
        c = 10.0 + i * 0.1
        bars.append({
            "trade_date": f"2026-{(i // 28) + 1:02d}-{(i % 28) + 1:02d}",
            "open_price": c - 0.05,
            "high_price": c + 0.2,
            "low_price": c - 0.2,
            "close_price": c,
            "volume": 1_000_000 + i * 1000,
        })
    return bars


def _seed_long_history(symbol: str = "WARMUP.SH", n: int = 120, base: date = date(2025, 1, 2)):
    """插入 n 根日线，覆盖 MA60 warmup 测试所需的 60 根前置。"""
    bars = []
    for offset in range(n):
        trade_date = base + timedelta(days=offset)
        bars.append(dict(
            symbol=symbol,
            code=symbol.split(".")[0],
            exchange=symbol.split(".")[1],
            trade_date=trade_date,
            adjust_flag="qfq",
            open_price=10.0 + offset * 0.1,
            high_price=10.0 + offset * 0.2,
            low_price=10.0 - offset * 0.05,
            close_price=10.0 + offset * 0.15,
            preclose_price=10.0 + max(0, offset - 1) * 0.15,
            volume=1_000_000,
            amount=10_000_000,
            turnover_rate=1.5,
            pct_change=0.5 if offset > 0 else 0,
            change=0.1,
            amplitude_pct=2.0,
            source="test",
            source_run_id="warmup-run",
        ))
    QuantDailyBar.insert_many(bars).execute()
    return base, base + timedelta(days=n - 1)


def _seed_long_minute_history(symbol: str = "MINWARM.SH", n: int = 80, base_dt: datetime = datetime(2025, 1, 2, 9, 35, 0)):
    """插入 n 根 5m bar，覆盖 MA60 on 5m 所需的 60 根前置。

    简化版：5m 间隔连续放，跨午夜换天（不模拟真实午休）；保证每天至少 48 根。
    """
    bars = []
    for i in range(n):
        dt = base_dt + timedelta(minutes=i * 5)
        bars.append(dict(
            symbol=symbol,
            code=symbol.split(".")[0],
            exchange=symbol.split(".")[1],
            trade_datetime=dt,
            trade_date=dt.date(),
            interval="5m",
            adjust_flag="qfq",
            open_price=10.0 + i * 0.1,
            high_price=10.0 + i * 0.2,
            low_price=10.0 - i * 0.05,
            close_price=10.0 + i * 0.15,
            volume=1_000.0,
            amount=10_000_000.0,
            source="test",
            source_run_id="warmup-min-run",
        ))
    QuantMinuteBar.insert_many(bars).execute()
    return base_dt, base_dt + timedelta(minutes=(n - 1) * 5)


def _seed_multi_day_minute(symbol: str = "MINWARM.SH", base_dt: datetime = datetime(2025, 1, 2, 9, 35, 0), bars_per_day: int = 48, days: int = 3):
    """插入跨多天的 5m bar；每天 bars_per_day 根（不模拟午休）；最后一天之前都是 warmup。"""
    bars = []
    for d in range(days):
        for i in range(bars_per_day):
            dt = base_dt + timedelta(days=d, minutes=i * 5)
            idx = d * bars_per_day + i
            bars.append(dict(
                symbol=symbol,
                code=symbol.split(".")[0],
                exchange=symbol.split(".")[1],
                trade_datetime=dt,
                trade_date=dt.date(),
                interval="5m",
                adjust_flag="qfq",
                open_price=10.0 + idx * 0.1,
                high_price=10.0 + idx * 0.2,
                low_price=10.0 - idx * 0.05,
                close_price=10.0 + idx * 0.15,
                volume=1_000.0,
                amount=10_000_000.0,
                source="test",
                source_run_id="warmup-multi-day",
            ))
    QuantMinuteBar.insert_many(bars).execute()
    # 第一天为 warmup 起点，最后一天为请求区间终点
    return base_dt, base_dt + timedelta(days=days - 1, minutes=(bars_per_day - 1) * 5)


class TestComputeIndicatorsEndpoint:
    """POST /data/indicators/compute 测试。"""

    def test_compute_all_default_indicators(self, auth_client):
        resp = auth_client.post(
            "/never_guess_my_usage/quant/data/indicators/compute",
            json={"bars": _build_bars(60)},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        results = data["data"]["results"]
        assert len(results) == 60
        last = list(results.values())[-1]
        assert "ma_5" in last
        assert "macd_dif" in last
        assert "kdj_k" in last
        assert data["data"]["meta"]["bars_count"] == 60

    def test_compute_filter_by_group(self, auth_client):
        resp = auth_client.post(
            "/never_guess_my_usage/quant/data/indicators/compute",
            json={"bars": _build_bars(30), "indicator_names": ["ma"]},
        )
        data = resp.get_json()
        assert data["success"] is True
        for row in data["data"]["results"].values():
            keys = set(row.keys())
            assert keys.issubset({"ma_5", "ma_10", "ma_20", "ma_60"})

    def test_compute_filter_by_td_only(self, auth_client):
        resp = auth_client.post(
            "/never_guess_my_usage/quant/data/indicators/compute",
            json={"bars": _build_bars(60), "indicator_names": ["td_sequential"]},
        )
        data = resp.get_json()
        assert data["success"] is True
        non_empty_rows = [row for row in data["data"]["results"].values() if row]
        assert any("td_buy_setup" in row or "td_sell_setup" in row for row in non_empty_rows)

    def test_compute_top_structure_only(self, auth_client):
        """indicator_names=["top_structure"] 时，results 只含 top_divergence 字段。"""
        resp = auth_client.post(
            "/never_guess_my_usage/quant/data/indicators/compute",
            json={"bars": _build_bars(60), "indicator_names": ["top_structure"]},
        )
        data = resp.get_json()
        assert data["success"] is True
        non_empty_rows = [row for row in data["data"]["results"].values() if row]
        for row in non_empty_rows:
            assert set(row.keys()).issubset({"top_divergence", "td_signal"})

    def test_compute_custom_params(self, auth_client):
        resp = auth_client.post(
            "/never_guess_my_usage/quant/data/indicators/compute",
            json={
                "bars": _build_bars(30),
                "indicator_names": ["ma"],
                "params": {"ma_windows": [3, 7]},
            },
        )
        data = resp.get_json()
        assert data["success"] is True
        for row in data["data"]["results"].values():
            keys = set(row.keys())
            assert keys.issubset({"ma_3", "ma_7"})

    def test_compute_empty_bars_returns_error(self, auth_client):
        resp = auth_client.post(
            "/never_guess_my_usage/quant/data/indicators/compute",
            json={"bars": []},
        )
        data = resp.get_json()
        assert data["success"] is False
        assert "bars" in data["msg"]

    def test_compute_too_many_bars_returns_error(self, auth_client):
        resp = auth_client.post(
            "/never_guess_my_usage/quant/data/indicators/compute",
            json={"bars": _build_bars(5001)},
        )
        data = resp.get_json()
        assert data["success"] is False

    def test_compute_unknown_indicator_returns_error(self, auth_client):
        resp = auth_client.post(
            "/never_guess_my_usage/quant/data/indicators/compute",
            json={"bars": _build_bars(20), "indicator_names": ["unknown_xyz"]},
        )
        data = resp.get_json()
        assert data["success"] is False

    def test_compute_requires_auth(self, app):
        client = app.test_client()
        resp = client.post(
            "/never_guess_my_usage/quant/data/indicators/compute",
            json={"bars": _build_bars(20)},
        )
        assert resp.status_code == 401


class TestComputeIndicatorsByRange:
    """POST /data/indicators/compute 新形态（symbol+日期区间）测试。"""

    def test_compute_with_symbol_and_date_range_fetches_warmup(self, auth_client, test_db):
        """关键回归测试：start_date 设定后，MA60 在请求区间首根仍应有值。"""
        _seed_long_history(symbol="WARMUP.SH", n=120)
        base = date(2025, 1, 2)
        # 从第 60 根开始请求（让首根需要 60 根前置历史）
        start = base + timedelta(days=59)
        end = base + timedelta(days=119)

        resp = auth_client.post(
            "/never_guess_my_usage/quant/data/indicators/compute",
            json={
                "symbol": "WARMUP.SH",
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "interval": "daily",
                "indicator_names": ["ma"],
            },
        )
        data = resp.get_json()
        assert data["success"] is True, data
        meta = data["data"]["meta"]
        results = data["data"]["results"]
        # 后端应当回拉到 60 根前置（warmup_count >= 59）
        assert meta["warmup_count"] >= 59
        # 请求区间内的所有日期都应有 ma_60
        first_date = start.isoformat()
        assert first_date in results
        assert results[first_date]["ma_60"] is not None

    def test_compute_trims_results_to_requested_range(self, auth_client, test_db):
        """warmup 部分日期应被裁掉，不出现在 results 里。"""
        _seed_long_history(symbol="WARMUP.SH", n=120)
        base = date(2025, 1, 2)
        start = base + timedelta(days=80)
        end = base + timedelta(days=100)

        resp = auth_client.post(
            "/never_guess_my_usage/quant/data/indicators/compute",
            json={
                "symbol": "WARMUP.SH",
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "interval": "daily",
                "indicator_names": ["ma"],
            },
        )
        data = resp.get_json()
        assert data["success"] is True
        result_dates = set(data["data"]["results"].keys())
        # warmup 日期不应出现
        assert (base + timedelta(days=10)).isoformat() not in result_dates
        # 所有返回日期都在请求区间内
        for d in result_dates:
            assert start.isoformat() <= d <= end.isoformat()

    def test_compute_insufficient_history_returns_partial_results(self, auth_client, test_db):
        """历史不足 lookback 时不应 500，ma_60 在能算的位置出值、不能算的位置 None。"""
        _seed_long_history(symbol="SHORT.SH", n=30)  # 只有 30 根，MA60 算不出
        base = date(2025, 1, 2)

        resp = auth_client.post(
            "/never_guess_my_usage/quant/data/indicators/compute",
            json={
                "symbol": "SHORT.SH",
                "start_date": base.isoformat(),
                "end_date": (base + timedelta(days=29)).isoformat(),
                "interval": "daily",
                "indicator_names": ["ma"],
            },
        )
        data = resp.get_json()
        assert data["success"] is True
        # 30 根数据全部算出（ma_60 全为 None 是预期，因为不够）
        results = data["data"]["results"]
        assert len(results) == 30
        for row in results.values():
            assert row["ma_60"] is None

    def test_compute_missing_symbol_returns_error(self, auth_client):
        resp = auth_client.post(
            "/never_guess_my_usage/quant/data/indicators/compute",
            json={
                "start_date": "2025-01-01",
                "end_date": "2025-12-31",
                "interval": "daily",
            },
        )
        data = resp.get_json()
        assert data["success"] is False

    def test_compute_invalid_interval_returns_error(self, auth_client):
        resp = auth_client.post(
            "/never_guess_my_usage/quant/data/indicators/compute",
            json={
                "symbol": "TEST.SH",
                "start_date": "2025-01-01",
                "end_date": "2025-12-31",
                "interval": "yearly",
            },
        )
        data = resp.get_json()
        assert data["success"] is False

    def test_compute_by_range_requires_auth(self, app, test_db):
        client = app.test_client()
        resp = client.post(
            "/never_guess_my_usage/quant/data/indicators/compute",
            json={
                "symbol": "TEST.SH",
                "start_date": "2025-01-01",
                "end_date": "2025-12-31",
                "interval": "daily",
            },
        )
        assert resp.status_code == 401

    def test_compute_weekly_interval_fetches_warmup(self, auth_client, test_db):
        """周线形态：MA60 on weekly 需要 ~60 周前置历史。后端应多拉 60*7 天的日线再聚合成周线。"""
        # 注入 504 天日线 ≈ 72 周；确保 >= 60 周前置 + 一定请求区间
        _seed_long_history(symbol="WEEKLY.SH", n=504)
        base = date(2025, 1, 2)
        # 请求从第 60 周开始（避免日期是周中导致 ISO 周对不齐）
        end = base + timedelta(days=503)
        start = base + timedelta(days=420)  # ~60 周后

        resp = auth_client.post(
            "/never_guess_my_usage/quant/data/indicators/compute",
            json={
                "symbol": "WEEKLY.SH",
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "interval": "weekly",
                "indicator_names": ["ma"],
            },
        )
        data = resp.get_json()
        assert data["success"] is True, data
        meta = data["data"]["meta"]
        results = data["data"]["results"]
        assert meta["warmup_count"] >= 59, f"expected warmup >= 59, got {meta['warmup_count']}"
        # 所有结果日期应落在请求区间内
        for d in results:
            assert start.isoformat() <= d <= end.isoformat()
        # 区间内第一个日期的 ma_60 应有值（warmup 生效）
        first_date = sorted(results.keys())[0]
        assert results[first_date]["ma_60"] is not None, (
            f"ma_60 应有值（warmup_count={meta['warmup_count']}），got {results[first_date]}"
        )

    def test_compute_minute_interval_fetches_warmup(self, auth_client, test_db):
        """分时形态：MA60 on 5m 需要 60 根 5m bar 前置历史。
        跨午夜：4 天 × 48 根/天 = 192 根；请求第三天到第四天，前两天作 warmup（96 根 > 60）。
        """
        base_dt, end_dt = _seed_multi_day_minute(symbol="MINWARM.SH", days=4, bars_per_day=48)
        # 请求从第三天开始：前两天 96 根作 warmup，足够 MA60（60 根）生效
        start_dt = base_dt + timedelta(days=2)

        resp = auth_client.post(
            "/never_guess_my_usage/quant/data/indicators/compute",
            json={
                "symbol": "MINWARM.SH",
                "start_date": start_dt.date().isoformat(),
                "end_date": end_dt.date().isoformat(),
                "start_datetime": start_dt.strftime("%Y-%m-%d %H:%M:%S"),
                "end_datetime": end_dt.strftime("%Y-%m-%d %H:%M:%S"),
                "interval": "minute",
                "indicator_names": ["ma"],
            },
        )
        data = resp.get_json()
        assert data["success"] is True, data
        meta = data["data"]["meta"]
        results = data["data"]["results"]
        # 至少 96 根 warmup（前两天）
        assert meta["warmup_count"] >= 96, f"expected warmup >= 96, got {meta['warmup_count']}"
        # 第一根（请求区间首根）的 ma_60 应有值（warmup 跨日生效）
        sorted_keys = sorted(results.keys())
        first_key = sorted_keys[0]
        assert results[first_key]["ma_60"] is not None, (
            f"ma_60 应有值（warmup_count={meta['warmup_count']}），got {results[first_key]}"
        )
        # key 应该是 datetime 串，不是纯 date
        assert "T" in first_key, f"expected datetime key, got {first_key}"

    def test_compute_minute_single_day_morning_has_warmup(self, auth_client, test_db):
        """单日请求 [9:30, 15:00]：上午首根 9:30 的 ma_60 应该有值。

        验证后端不会用 minutes 偏移（午休断点）；改用日历天回退，至少 2 天 buffer。
        """
        # 4 天 × 48 根 = 192 根；请求第 4 天全天的指标
        base_dt, end_dt = _seed_multi_day_minute(symbol="SINGLE.SH", days=4, bars_per_day=48)
        request_start = base_dt + timedelta(days=3)  # 第 4 天 09:35

        resp = auth_client.post(
            "/never_guess_my_usage/quant/data/indicators/compute",
            json={
                "symbol": "SINGLE.SH",
                "start_date": request_start.date().isoformat(),
                "end_date": end_dt.date().isoformat(),
                "start_datetime": request_start.strftime("%Y-%m-%d %H:%M:%S"),
                "end_datetime": end_dt.strftime("%Y-%m-%d %H:%M:%S"),
                "interval": "minute",
                "indicator_names": ["ma"],
            },
        )
        data = resp.get_json()
        assert data["success"] is True, data
        results = data["data"]["results"]
        sorted_keys = sorted(results.keys())
        # 第 4 天上午 09:35 的 ma_60 应该有值（前面 3 天 × 48 根 = 144 根，远超 60）
        first_key = sorted_keys[0]
        first_hour = first_key.split("T")[1]
        assert first_hour.startswith("09:"), f"expected morning bar, got {first_key}"
        assert results[first_key]["ma_60"] is not None, (
            f"上午首根 9:30 应有 ma_60（warmup 跨日/午休），got {results[first_key]}"
        )
        # 第 4 天下午的 bar 也应有值
        afternoon_keys = [k for k in sorted_keys if k.split("T")[1].startswith("13:") or k.split("T")[1].startswith("14:")]
        assert afternoon_keys, "应至少有 1 根下午 bar"
        assert results[afternoon_keys[0]]["ma_60"] is not None

    def test_compute_minute_end_day_bars_not_excluded_by_separator(self, auth_client, test_db):
        """回归测试：end_date 当天的所有 bar 必须保留。

        之前的 bug：边界用空格分隔（前端 payload），bar key 用 T 分隔（DB isoformat）；
        字符串比较 "T" > " "，导致 end_date 当天所有 bar 被错误剔除。
        """
        base_dt, end_dt = _seed_multi_day_minute(symbol="ENDDAY.SH", days=2, bars_per_day=48)
        request_start = base_dt + timedelta(days=1)
        # 关键：end_date 与 start_date 同一天 → 当天 48 根必须全保留
        resp = auth_client.post(
            "/never_guess_my_usage/quant/data/indicators/compute",
            json={
                "symbol": "ENDDAY.SH",
                "start_date": request_start.date().isoformat(),
                "end_date": request_start.date().isoformat(),
                "start_datetime": request_start.strftime("%Y-%m-%d %H:%M:%S"),
                # 边界明确给到 23:59:59（含下午末根）
                "end_datetime": f"{request_start.date().isoformat()} 23:59:59",
                "interval": "minute",
                "indicator_names": ["ma"],
            },
        )
        data = resp.get_json()
        assert data["success"] is True, data
        results = data["data"]["results"]
        sorted_keys = sorted(results.keys())
        # 末根必须是当天的最后一根（不是空 / 不是前一天）
        last_key = sorted_keys[-1]
        last_date = last_key.split("T")[0]
        assert last_date == request_start.date().isoformat(), (
            f"end_date 当天末根应在结果中，got {last_key}"
        )
        # 且 ma_60 应有值（前一天全 48 根 + 当天之前的部分）
        assert results[last_key]["ma_60"] is not None
        # 上午 + 下午都应至少有 bar 存在
        morning = [k for k in sorted_keys if k.split("T")[1].startswith("09:") or k.split("T")[1].startswith("10:") or k.split("T")[1].startswith("11:")]
        afternoon = [k for k in sorted_keys if k.split("T")[1].startswith("13:") or k.split("T")[1].startswith("14:")]
        assert morning, "上午 bar 应保留"
        assert afternoon, "下午 bar 应保留（之前会被分隔符 bug 误删）"


class TestListIndicatorsEndpoint:
    """GET /data/indicators 测试。"""

    def test_list_missing_symbol_returns_error(self, auth_client):
        resp = auth_client.get("/never_guess_my_usage/quant/data/indicators")
        data = resp.get_json()
        assert data["success"] is False

    def test_list_with_symbol_empty_when_no_indicators(self, auth_client, seed_daily_bars):
        resp = auth_client.get(
            "/never_guess_my_usage/quant/data/indicators",
            params={"symbol": "000001.SZ"},
        )
        data = resp.get_json()
        assert data["success"] is True
        assert data["data"]["items"] == []
        assert data["data"]["total"] == 0

    def test_list_after_upsert(self, auth_client, seed_daily_bars):
        from service.quant.indicator_service import upsert_daily_indicators
        upsert_daily_indicators(symbols=["000001.SZ"], adjust_flag="qfq")

        resp = auth_client.get(
            "/never_guess_my_usage/quant/data/indicators",
            params={"symbol": "000001.SZ"},
        )
        data = resp.get_json()
        assert data["success"] is True
        items = data["data"]["items"]
        assert len(items) > 0
        names = {item["indicator_name"] for item in items}
        assert "ma_5" in names or "macd_dif" in names

    def test_list_filter_by_names(self, auth_client, seed_daily_bars):
        from service.quant.indicator_service import upsert_daily_indicators
        upsert_daily_indicators(symbols=["000001.SZ"], adjust_flag="qfq")

        resp = auth_client.get(
            "/never_guess_my_usage/quant/data/indicators",
            params={"symbol": "000001.SZ", "names": "macd_dif,macd_dea"},
        )
        data = resp.get_json()
        assert data["success"] is True
        names = {item["indicator_name"] for item in data["data"]["items"]}
        assert names.issubset({"macd_dif", "macd_dea"})

    def test_list_requires_auth(self, app):
        client = app.test_client()
        resp = client.get(
            "/never_guess_my_usage/quant/data/indicators?symbol=000001.SZ",
        )
        assert resp.status_code == 401
