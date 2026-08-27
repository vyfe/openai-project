"""data_routes /data/minute_bars 与 /data/fetch_now (5m) API 集成测试。"""

from datetime import date, datetime, timedelta

import pytest


@pytest.fixture()
def seed_minute_bars(test_db):
    from quant.entities import QuantMinuteBar
    base_date = date(2024, 1, 2)
    bars = []
    for offset in range(3):
        d = base_date + timedelta(days=offset)
        for minute in (35, 40, 45):
            bars.append(dict(
                symbol="600519.SH", code="600519", exchange="SH",
                trade_datetime=datetime(d.year, d.month, d.day, 9, minute, 0),
                trade_date=d,
                interval="5m", adjust_flag="qfq",
                open_price=1700.0 + offset * 5 + minute * 0.01,
                high_price=1702.0 + offset * 5,
                low_price=1699.0 + offset * 5,
                close_price=1701.0 + offset * 5,
                volume=1000.0,
                amount=1701000.0,
                source="baostock",
                source_run_id="seed",
            ))
    QuantMinuteBar.insert_many(bars).execute()


class TestMinuteBarsApi:
    def test_get_minute_bars_returns_records(self, auth_client, seed_minute_bars):
        resp = auth_client.get(
            "/never_guess_my_usage/quant/data/minute_bars",
            params={"symbol": "600519.SH", "interval": "5m"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert isinstance(data["data"], list)
        assert len(data["data"]) == 9

    def test_get_minute_bars_missing_symbol(self, auth_client):
        resp = auth_client.get("/never_guess_my_usage/quant/data/minute_bars")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is False

    def test_get_minute_bars_with_date_range(self, auth_client, seed_minute_bars):
        resp = auth_client.get(
            "/never_guess_my_usage/quant/data/minute_bars",
            params={
                "symbol": "600519.SH",
                "interval": "5m",
                "start_datetime": "2024-01-02 00:00:00",
                "end_datetime": "2024-01-02 23:59:59",
            },
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert len(data["data"]) == 3

    def test_get_minute_bars_respects_limit(self, auth_client, seed_minute_bars):
        resp = auth_client.get(
            "/never_guess_my_usage/quant/data/minute_bars",
            params={"symbol": "600519.SH", "interval": "5m", "limit": 5},
        )
        data = resp.get_json()
        assert len(data["data"]) == 5


class TestFetchNowMinute:
    def test_fetch_now_with_frequency_5m_uses_minute_dataset(self, auth_client, monkeypatch):
        from quant.entities import QuantMinuteBar
        from service.quant.import_service import import_bundle

        def fake_build_fetch_bundle(provider_name, symbols, start_date, end_date, adjust_flag, frequency="1d", interval="5m"):
            from quant_client.bundle_builder import build_fetch_bundle as real_build
            return real_build(
                "baostock", symbols, start_date, end_date, adjust_flag,
                frequency=frequency, interval=interval,
            )

        # 走真实 provider 会被网络拦截，monkeypatch 替换为返回写死的 minute bundle
        sample_bundle = {
            "dataset": "a_share_5min_bars_v1",
            "bundle_version": 1,
            "batch_id": "test-fetch-5m",
            "source": "baostock",
            "source_run_id": "test-fetch-5m",
            "records": [
                {
                    "symbol": "600519.SH", "code": "600519", "exchange": "SH",
                    "trade_datetime": "2024-01-02T09:35:00",
                    "trade_date": "2024-01-02",
                    "interval": "5m", "adjust_flag": "qfq",
                    "open_price": 1700.0, "high_price": 1702.0,
                    "low_price": 1699.0, "close_price": 1701.0,
                    "volume": 1000.0, "amount": 1701000.0,
                    "source": "baostock", "data_source_version": "v1",
                },
            ],
        }

        def fake_build(provider_name, symbols, start_date, end_date, adjust_flag, frequency="1d", interval="5m"):
            return sample_bundle

        monkeypatch.setattr("routes.quant.data_routes.build_fetch_bundle", fake_build)

        resp = auth_client.post(
            "/never_guess_my_usage/quant/data/fetch_now",
            json={
                "symbols": ["600519.SH"],
                "start_date": "2024-01-02",
                "end_date": "2024-01-02",
                "provider": "baostock",
                "adjust_flag": "qfq",
                "frequency": "5m",
                "interval": "5m",
            },
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["data"]["dataset"] == "a_share_5min_bars_v1"
        assert QuantMinuteBar.select().count() == 1