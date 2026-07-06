"""数据/仪表盘 API 路由集成测试。"""

import pytest


class TestDataRoutes:
    """测试数据相关路由。"""

    def test_dashboard_overview(self, auth_client):
        resp = auth_client.get("/never_guess_my_usage/quant/dashboard/overview")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True

    def test_providers(self, auth_client):
        resp = auth_client.get("/never_guess_my_usage/quant/providers")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True

    def test_daily_bars_missing_symbol(self, auth_client):
        resp = auth_client.get("/never_guess_my_usage/quant/data/daily_bars")
        data = resp.get_json()
        # 无 symbol 参数应返回失败
        assert data["success"] is False

    def test_daily_bars_with_symbol(self, auth_client, seed_daily_bars):
        resp = auth_client.get("/never_guess_my_usage/quant/data/daily_bars", params={"symbol": "000001.SZ"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True

    def test_symbol_upsert_adds_instrument(self, auth_client):
        from quant.entities import QuantInstrument

        resp = auth_client.post(
            "/never_guess_my_usage/quant/symbols/upsert",
            json={"symbol": "000657.SZ", "name": "中钨高新", "code": "000657", "exchange": "SZ"},
        )

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["data"]["symbol"] == "000657.SZ"
        assert QuantInstrument.get(QuantInstrument.symbol == "000657.SZ").name == "中钨高新"

        symbols_resp = auth_client.get("/never_guess_my_usage/quant/symbols", params={"limit": 20})
        symbols = symbols_resp.get_json()["data"]
        assert any(item["symbol"] == "000657.SZ" for item in symbols)

    def test_fetch_now_imports_bundle(self, auth_client, monkeypatch):
        from quant.entities import QuantDailyBar, QuantInstrument

        def fake_build_fetch_bundle(provider_name, symbols, start_date, end_date, adjust_flag):
            return {
                "dataset": "a_share_daily_bars_v1",
                "bundle_version": 1,
                "batch_id": "test-fetch-now",
                "source": "mock_provider",
                "source_run_id": "test-fetch-now",
                "generated_at": "2026-07-05T00:00:00",
                "market": "A_SHARE",
                "provider_meta": {
                    "provider_name": provider_name,
                    "adjust_flag": adjust_flag,
                    "start_date": start_date,
                    "end_date": end_date,
                },
                "records": [
                    {
                        "symbol": "000657.SZ",
                        "code": "000657",
                        "exchange": "SZ",
                        "trade_date": "2026-07-03",
                        "adjust_flag": adjust_flag,
                        "open_price": 95.0,
                        "high_price": 96.5,
                        "low_price": 87.8,
                        "close_price": 89.63,
                        "preclose_price": 97.03,
                        "volume": 1000,
                        "amount": 100000,
                        "turnover_rate": 2.1,
                        "pct_change": -7.62,
                        "source": "mock_provider",
                    }
                ],
            }

        monkeypatch.setattr("routes.quant.data_routes.build_fetch_bundle", fake_build_fetch_bundle)

        resp = auth_client.post(
            "/never_guess_my_usage/quant/data/fetch_now",
            json={
                "symbols": ["000657.SZ"],
                "start_date": "2026-07-03",
                "end_date": "2026-07-03",
                "provider": "auto",
                "adjust_flag": "qfq",
            },
        )

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["data"]["batch_id"] == "test-fetch-now"
        assert data["data"]["records_imported"] == 1
        assert QuantDailyBar.select().where(QuantDailyBar.symbol == "000657.SZ").count() == 1
        assert QuantInstrument.select().where(QuantInstrument.symbol == "000657.SZ").count() == 1
