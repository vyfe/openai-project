"""backtest_service 长/短分支测试。

不写真实行情 / 真实策略：mock QuantDailyBar + QuantStrategy + evaluate_series，
构造受控的 series_results，验证 trades 数组里 side / entry_price / exit_price 字段。
"""
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest


def _fake_bar(trade_date, open_price, close_price):
    bar = MagicMock()
    bar.trade_date = trade_date
    bar.open_price = open_price
    bar.close_price = close_price
    return bar


def _fake_strategy(signal_type="buy"):
    s = MagicMock()
    s.id = 1
    s.name = "测试策略"
    s.symbols = ["000001.SZ"]
    s.status = "active"
    s.updated_at = None
    s.rule_config_json = "{}"
    # to_dict() 返回 strategiesnapshot
    s.to_dict.return_value = {"id": 1, "name": "测试策略", "signal_type": signal_type}
    return s


def _run_backtest_with(series_results, bars_by_symbol):
    """跑 backtest，mock evaluate_series / _load_bars_for_symbol / QuantStrategy / QuantBacktestRun.create / DB 查询。"""
    from service.quant import backtest_service

    strategy = _fake_strategy()
    fake_run = MagicMock()
    fake_run.id = 99
    fake_run.benchmark_symbol = ""
    fake_run.equity_curve_json = "[]"
    fake_run.trades_json = "[]"
    fake_run.metrics_json = "{}"
    fake_run.summary_json = "{}"
    fake_run.data_source_version = "v1"

    # run_backtest 最后 return record.to_dict()；让 to_dict 从 fake_run.trades_json 等
    # 实际写入的字段解析（MagicMock 默认支持属性赋值）。
    def _to_dict_impl():
        import json as _json
        return {
            "trades": _json.loads(fake_run.trades_json or "[]"),
            "metrics": _json.loads(fake_run.metrics_json or "{}"),
            "summary": _json.loads(fake_run.summary_json or "{}"),
            "data_source_version": fake_run.data_source_version,
        }
    fake_run.to_dict.side_effect = _to_dict_impl

    with patch.object(backtest_service, "QuantStrategy") as fake_model, \
         patch.object(backtest_service, "QuantBacktestRun") as fake_record_model, \
         patch.object(backtest_service, "_resolve_symbols", return_value=["000001.SZ"]), \
         patch.object(backtest_service, "_load_bars_for_symbol", side_effect=lambda s, _: bars_by_symbol.get(s, [])), \
         patch.object(backtest_service, "evaluate_series", return_value=series_results), \
         patch.object(backtest_service, "_latest_data_version", return_value="v1"):
        fake_model.get_by_id.return_value = strategy
        fake_record_model.create.return_value = fake_run

        return backtest_service.run_backtest(
            strategy_id=1,
            start_date="2026-09-01",
            end_date="2026-09-10",
            hold_days=2,
            top_n=3,
            initial_capital=100000.0,
            commission_rate=0.0,  # 简化：让手续费=0，断言只看 gross_return
            slippage_rate=0.0,
        )


def _passed_result(trade_date_iso, signal_type, score=2.5, reasons=None):
    return {
        "passed": True,
        "score": score,
        "signal_type": signal_type,
        "reasons": reasons or ["规则通过"],
        "metrics": {"trade_date": trade_date_iso, "close_price": 11.0},
    }


class TestLongShortBranch:
    """signal_type 决定 backtest 走 long 还是 short 路径。"""

    def test_buy_signal_uses_long_path(self):
        """buy 信号：entry=次日 open，exit=hold_days 天后 close，return=(exit-entry)/entry。"""
        bars = [
            _fake_bar(date(2026, 9, 1), 10.0, 10.5),   # idx 0 — 信号日（不会用到当根 bar）
            _fake_bar(date(2026, 9, 2), 11.0, 11.5),   # idx 1 — entry_idx（open=11.0）
            _fake_bar(date(2026, 9, 3), 12.0, 12.5),   # idx 2 — exit_idx（hold_days=2, close=12.5）
        ]
        result = _run_backtest_with(
            series_results=[_passed_result("2026-09-01", "buy")],
            bars_by_symbol={"000001.SZ": bars},
        )

        trades = result["trades"]
        assert len(trades) == 1
        t = trades[0]
        assert t["signal_type"] == "buy"
        assert t["side"] == "long"
        assert t["entry_price"] == 11.0      # entry_idx open
        assert t["exit_price"] == 12.5       # exit_idx close
        # gross_return 服务侧 round 到 6 位：(12.5-11.0)/11.0 = 0.136364
        assert t["gross_return"] == pytest.approx(0.136364, rel=1e-6)
        assert t["entry_date"] == "2026-09-02"
        assert t["exit_date"] == "2026-09-03"

    def test_watch_signal_defaults_to_long(self):
        """watch 信号走 long 分支（向后兼容）。"""
        bars = [
            _fake_bar(date(2026, 9, 1), 10.0, 10.5),
            _fake_bar(date(2026, 9, 2), 11.0, 11.5),
            _fake_bar(date(2026, 9, 3), 12.0, 12.5),
        ]
        result = _run_backtest_with(
            series_results=[_passed_result("2026-09-01", "watch")],
            bars_by_symbol={"000001.SZ": bars},
        )

        trades = result["trades"]
        assert len(trades) == 1
        assert trades[0]["side"] == "long"
        assert trades[0]["entry_price"] == 11.0
        assert trades[0]["exit_price"] == 12.5
        assert trades[0]["gross_return"] == pytest.approx(0.136364, rel=1e-6)

    def test_sell_signal_uses_short_path(self):
        """sell 信号：entry=次日 open 卖出开仓，exit=hold_days 天后 open 买入平仓。
        return=(open - cover) / open — 价跌为正。"""
        bars = [
            _fake_bar(date(2026, 9, 1), 10.0, 10.5),   # idx 0 — 信号日
            _fake_bar(date(2026, 9, 2), 12.0, 11.5),   # idx 1 — entry_idx（open=12.0 卖出开仓）
            _fake_bar(date(2026, 9, 3), 10.5, 11.0),   # idx 2 — exit_idx（open=10.5 买回平仓）
        ]
        result = _run_backtest_with(
            series_results=[_passed_result("2026-09-01", "sell")],
            bars_by_symbol={"000001.SZ": bars},
        )

        trades = result["trades"]
        assert len(trades) == 1
        t = trades[0]
        assert t["signal_type"] == "sell"
        assert t["side"] == "short"
        assert t["entry_price"] == 12.0      # entry_idx open（卖出价）
        assert t["exit_price"] == 10.5       # exit_idx open（买回价）
        # 做空收益：(12.0 - 10.5) / 12.0 = 0.125（价跌为正）
        assert t["gross_return"] == pytest.approx((12.0 - 10.5) / 12.0, rel=1e-6)
        assert t["entry_date"] == "2026-09-02"
        assert t["exit_date"] == "2026-09-03"

    def test_short_profit_when_price_drops(self):
        """做空成功（价跌）应当是 + 收益。"""
        bars = [
            _fake_bar(date(2026, 9, 1), 10.0, 10.5),
            _fake_bar(date(2026, 9, 2), 20.0, 19.5),  # 卖出价 20
            _fake_bar(date(2026, 9, 3), 18.0, 17.5),  # 买回价 18
        ]
        result = _run_backtest_with(
            series_results=[_passed_result("2026-09-01", "sell")],
            bars_by_symbol={"000001.SZ": bars},
        )
        assert result["trades"][0]["gross_return"] > 0
        assert result["trades"][0]["gross_return"] == pytest.approx((20.0 - 18.0) / 20.0, rel=1e-6)

    def test_short_loss_when_price_rises(self):
        """做空失败（价涨）应当是负收益。"""
        bars = [
            _fake_bar(date(2026, 9, 1), 10.0, 10.5),
            _fake_bar(date(2026, 9, 2), 18.0, 17.5),  # 卖出价 18
            _fake_bar(date(2026, 9, 3), 20.0, 19.5),  # 买回价 20
        ]
        result = _run_backtest_with(
            series_results=[_passed_result("2026-09-01", "sell")],
            bars_by_symbol={"000001.SZ": bars},
        )
        assert result["trades"][0]["gross_return"] < 0
        assert result["trades"][0]["gross_return"] == pytest.approx((18.0 - 20.0) / 18.0, rel=1e-6)

    def test_long_uses_entry_open_and_exit_close_specifically(self):
        """long 必须用 entry_idx open + exit_idx close（不能用 close/open 互换）。"""
        # entry_idx open=11.0, close=11.5；exit_idx open=12.0, close=12.5
        # long 应该用 entry_idx open (11.0) + exit_idx close (12.5)
        # 不是用 entry_idx close (11.5) + exit_idx open (12.0)
        bars = [
            _fake_bar(date(2026, 9, 1), 10.0, 10.5),
            _fake_bar(date(2026, 9, 2), 11.0, 11.5),
            _fake_bar(date(2026, 9, 3), 12.0, 12.5),
        ]
        result = _run_backtest_with(
            series_results=[_passed_result("2026-09-01", "buy")],
            bars_by_symbol={"000001.SZ": bars},
        )
        t = result["trades"][0]
        assert t["entry_price"] == 11.0  # entry_idx open
        assert t["exit_price"] == 12.5   # exit_idx close
        # 注意：不是 11.5（entry_idx close）也不是 12.0（exit_idx open）

    def test_short_uses_entry_open_and_exit_open_specifically(self):
        """short 必须用 entry_idx open + exit_idx open（双边开盘价）。"""
        # entry_idx open=11.0；exit_idx open=12.0
        # short 应该用 entry_idx open (11.0 卖出) + exit_idx open (12.0 买回)
        # 不是用 exit_idx close
        bars = [
            _fake_bar(date(2026, 9, 1), 10.0, 10.5),
            _fake_bar(date(2026, 9, 2), 11.0, 11.5),
            _fake_bar(date(2026, 9, 3), 12.0, 12.5),
        ]
        result = _run_backtest_with(
            series_results=[_passed_result("2026-09-01", "sell")],
            bars_by_symbol={"000001.SZ": bars},
        )
        t = result["trades"][0]
        assert t["entry_price"] == 11.0  # entry_idx open（卖出开仓）
        assert t["exit_price"] == 12.0   # exit_idx open（买回平仓）
        # 注意：不是 11.5（entry_idx close）也不是 12.5（exit_idx close）

    def test_trades_record_has_side_field(self):
        """每条 trade 都应当带 side 字段（向后兼容：旧记录没这个字段也得容错）。"""
        bars = [
            _fake_bar(date(2026, 9, 1), 10.0, 10.5),
            _fake_bar(date(2026, 9, 2), 11.0, 11.5),
            _fake_bar(date(2026, 9, 3), 12.0, 12.5),
        ]
        for sig in ("buy", "sell", "watch"):
            result = _run_backtest_with(
                series_results=[_passed_result("2026-09-01", sig)],
                bars_by_symbol={"000001.SZ": bars},
            )
            assert "side" in result["trades"][0]
            expected = "short" if sig == "sell" else "long"
            assert result["trades"][0]["side"] == expected


class TestEquityCurveWithMixedSides:
    """_build_equity_curve 不区分 long/short：每天的 trade 求平均收益，乘以当前 capital。"""

    def test_short_negative_return_consumes_capital(self):
        """做空亏钱（价涨）会让 capital 缩。"""
        from service.quant.backtest_service import _build_equity_curve

        trades = [
            {"exit_date": "2026-09-03", "net_return": -0.10},  # 做空亏 10%
        ]
        curve = _build_equity_curve(100000.0, trades, "2026-09-01")
        # 第二点 capital = 100000 * (1 - 0.10) = 90000
        assert curve[1]["capital"] == 90000.0
        assert curve[1]["net_value"] == pytest.approx(0.9, rel=1e-6)

    def test_long_positive_return_grows_capital(self):
        trades = [
            {"exit_date": "2026-09-03", "net_return": 0.05},  # 做多赚 5%
        ]
        from service.quant.backtest_service import _build_equity_curve
        curve = _build_equity_curve(100000.0, trades, "2026-09-01")
        assert curve[1]["capital"] == 105000.0


class TestBenchmarkCurve:
    """_build_benchmark_curve（buy & hold 净值曲线）+ _benchmark_summary。"""

    def test_benchmark_curve_buy_and_hold_growth(self):
        """起点 open 买入，end 区间 close 卖出 → net_value = close / open_start。"""
        from service.quant.backtest_service import _build_benchmark_curve

        bars = [
            _fake_bar(date(2026, 9, 1), 10.0, 10.5),   # 起点：open=10.0
            _fake_bar(date(2026, 9, 2), 11.0, 11.5),
            _fake_bar(date(2026, 9, 3), 12.0, 12.5),   # 终点：close=12.5
        ]
        curve = _build_benchmark_curve(bars, "2026-09-01", "2026-09-03")
        assert curve[0]["date"] == "2026-09-01"
        assert curve[0]["net_value"] == 1.0
        # 终点 net_value = 12.5 / 10.0 = 1.25（buy & hold 涨 25%）
        assert curve[-1]["date"] == "2026-09-03"
        assert curve[-1]["net_value"] == pytest.approx(1.25, rel=1e-6)
        # 中间点 net_value 应介于两者之间
        assert curve[1]["net_value"] == pytest.approx(1.15, rel=1e-6)  # 11.5 / 10.0
        assert curve[2]["net_value"] == pytest.approx(1.25, rel=1e-6)

    def test_benchmark_curve_falls(self):
        """价跌时 net_value < 1.0。"""
        from service.quant.backtest_service import _build_benchmark_curve

        bars = [
            _fake_bar(date(2026, 9, 1), 10.0, 10.5),
            _fake_bar(date(2026, 9, 2), 9.0, 8.5),
            _fake_bar(date(2026, 9, 3), 8.0, 7.5),
        ]
        curve = _build_benchmark_curve(bars, "2026-09-01", "2026-09-03")
        assert curve[-1]["net_value"] == pytest.approx(0.75, rel=1e-6)

    def test_benchmark_curve_filters_out_of_range_bars(self):
        from service.quant.backtest_service import _build_benchmark_curve

        bars = [
            _fake_bar(date(2026, 9, 1), 10.0, 10.5),
            _fake_bar(date(2026, 9, 5), 11.0, 11.5),  # 在范围内
            _fake_bar(date(2026, 9, 10), 12.0, 12.5),  # 在范围内
        ]
        curve = _build_benchmark_curve(bars, "2026-09-02", "2026-09-08")
        # 区间 [09-02, 09-08] 只保留 09-05 → 09-05 作 entry，candidates[1:] 空
        # → curve 只有 1 个起点（1.0）
        assert len(curve) == 1
        assert curve[0]["net_value"] == 1.0
        assert curve[0]["date"] == "2026-09-02"

    def test_benchmark_curve_empty_bars(self):
        from service.quant.backtest_service import _build_benchmark_curve
        assert _build_benchmark_curve([], "2026-09-01", "2026-09-10") == []

    def test_benchmark_curve_no_overlap_returns_empty(self):
        """区间内无 bar 且 bars 全部早于 start_date → 返回空（无法确定 anchor）。"""
        from service.quant.backtest_service import _build_benchmark_curve

        bars = [
            _fake_bar(date(2026, 9, 1), 10.0, 10.5),
            _fake_bar(date(2026, 9, 2), 11.0, 11.5),
        ]
        # bars 全部早于 start_date → 无 anchor → 返回空
        curve = _build_benchmark_curve(bars, "2026-11-01", "2026-11-20")
        assert curve == []

    def test_benchmark_summary_with_curve(self):
        from service.quant.backtest_service import _benchmark_summary

        curve = [
            {"date": "2026-09-01", "net_value": 1.0},
            {"date": "2026-09-10", "net_value": 1.20},  # +20%
        ]
        summary = _benchmark_summary(curve, total_commission_rate=0.001)
        assert summary["benchmark_gross_return"] == pytest.approx(0.20, rel=1e-6)
        # net = gross - (commission + slippage) * 2 = 0.20 - 0.002
        assert summary["benchmark_net_return"] == pytest.approx(0.20 - 0.002, rel=1e-6)

    def test_benchmark_summary_empty_curve(self):
        from service.quant.backtest_service import _benchmark_summary
        summary = _benchmark_summary([], 0.001)
        assert summary["benchmark_gross_return"] is None
        assert summary["benchmark_net_return"] is None
        assert summary["alpha"] is None


class TestBenchmarkInBacktestIntegration:
    """run_backtest 跑通后端到端，验证 benchmark_curve 字段被填充。"""

    def test_run_backtest_with_benchmark_fills_curve(self):
        """run_backtest 应当生成 benchmark_curve 字段（基于配置 benchmark_symbol）。"""
        # 跑 backtest，benchmark_symbol 设 "510300.SH"
        # 验证 to_dict 返回里有 benchmark_curve + metrics.benchmark_gross_return / alpha
        strategy = _fake_strategy()
        strategy.id = 1
        # to_dict 返回带 signal_type
        strategy.to_dict.return_value = {"id": 1, "name": "测试策略", "signal_type": "buy"}

        # mock 全套
        from service.quant import backtest_service
        fake_run = MagicMock()
        fake_run.id = 99
        fake_run.benchmark_symbol = "510300.SH"
        # 关键：record.benchmark_curve_json 会被写入；to_dict 会 json.loads 它
        fake_run.benchmark_curve_json = "[]"
        fake_run.trades_json = "[]"
        fake_run.metrics_json = "{}"
        fake_run.summary_json = "{}"
        fake_run.equity_curve_json = "[]"
        fake_run.data_source_version = "v1"

        def _to_dict_impl():
            import json as _json
            return {
                "trades": _json.loads(fake_run.trades_json or "[]"),
                "metrics": _json.loads(fake_run.metrics_json or "{}"),
                "summary": _json.loads(fake_run.summary_json or "{}"),
                "benchmark_curve": _json.loads(fake_run.benchmark_curve_json or "[]"),
                "equity_curve": _json.loads(fake_run.equity_curve_json or "[]"),
                "benchmark_symbol": fake_run.benchmark_symbol,
            }
        fake_run.to_dict.side_effect = _to_dict_impl

        # mock 基准 bars
        benchmark_bars = [
            _fake_bar(date(2026, 9, 1), 5.0, 5.5),   # 起点 open=5.0
            _fake_bar(date(2026, 9, 2), 5.5, 6.0),
            _fake_bar(date(2026, 9, 3), 6.0, 6.5),   # 终点 close=6.5（+30%）
        ]

        def _load(symbol, end_date):
            """统一 mock _load_bars_for_symbol：基准 symbol → benchmark_bars，策略 symbol → strategy_bars"""
            if symbol == "510300.SH":
                return benchmark_bars
            if symbol == "000001.SZ":
                return strategy_bars
            return []

        # mock 一个有 passed=True 的信号（buy 类型），触发 trade 计算
        passed_result = _passed_result("2026-09-01", "buy")
        # 不传 buy_and_hold_result，因为 buy 信号走 long 路径（前面已测过）

        strategy_bars = [
            _fake_bar(date(2026, 9, 1), 10.0, 10.5),
            _fake_bar(date(2026, 9, 2), 11.0, 11.5),
            _fake_bar(date(2026, 9, 3), 12.0, 12.5),
        ]

        def _resolve_symbols(s, override):
            return ["000001.SZ"]

        with patch.object(backtest_service, "QuantStrategy") as fake_model, \
             patch.object(backtest_service, "QuantBacktestRun") as fake_record_model, \
             patch.object(backtest_service, "_resolve_symbols", side_effect=_resolve_symbols), \
             patch.object(backtest_service, "_load_bars_for_symbol", side_effect=_load), \
             patch.object(backtest_service, "evaluate_series", return_value=[passed_result]), \
             patch.object(backtest_service, "_latest_data_version", return_value="v1"):
            fake_model.get_by_id.return_value = strategy
            fake_record_model.create.return_value = fake_run

            result = backtest_service.run_backtest(
                strategy_id=1,
                start_date="2026-09-01",
                end_date="2026-09-03",
                hold_days=2,
                top_n=3,
                initial_capital=100000.0,
                commission_rate=0.0,
                slippage_rate=0.0,
                benchmark_symbol="510300.SH",  # ← 配置基准
            )

        # benchmark_curve 字段被填充（_build_benchmark_curve 算出来的 buy & hold）
        assert "benchmark_curve" in result
        assert len(result["benchmark_curve"]) >= 2
        # buy & hold 6.5 / 5.0 = 1.30
        assert result["benchmark_curve"][-1]["net_value"] == pytest.approx(1.30, rel=1e-6)
        # metrics 里 benchmark_gross_return = 0.30
        assert result["metrics"]["benchmark_gross_return"] == pytest.approx(0.30, rel=1e-6)