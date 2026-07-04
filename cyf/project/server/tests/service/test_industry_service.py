from datetime import date

from quant.entities import (
    QuantDailyBar,
    QuantIndustryNewsItem,
    QuantMarketSnapshot,
    QuantResearchReportItem,
)
from service.quant.industry_service import collect_industry, get_industry_dashboard, list_industry_boards


def _patch_collectors(monkeypatch):
    monkeypatch.setattr(
        "service.quant.industry_service.fetch_latest_kline",
        lambda code: {
            "name": "中钨高新" if code == "000657" else "鼎泰高科",
            "trade_date": "2026-07-03",
            "open_price": 10.0,
            "close_price": 11.0,
            "high_price": 11.5,
            "low_price": 9.8,
            "volume": 10000.0,
            "amount": 120000000.0,
            "amplitude_pct": 5.0,
            "pct_change": 3.2,
            "change": 0.34,
            "turnover_rate": 2.1,
            "source": "mock_kline",
            "payload": {},
        },
    )
    monkeypatch.setattr(
        "service.quant.industry_service.fetch_quote",
        lambda code: {
            "name": "中钨高新" if code == "000657" else "鼎泰高科",
            "current_price": 11.0,
            "pe_ttm": 55.0,
            "pb": 20.0,
            "market_cap": 200000000000.0,
            "float_market_cap": 180000000000.0,
            "source": "mock_quote",
            "payload": {},
        },
    )
    monkeypatch.setattr(
        "service.quant.industry_service.fetch_latest_capital_flow",
        lambda code: {
            "trade_date": "2026-07-03",
            "main_flow": 10000000.0,
            "super_large_flow": 6000000.0,
            "large_flow": 4000000.0,
            "mid_flow": -1000000.0,
            "small_flow": -9000000.0,
            "main_flow_pct": 1.2,
            "source": "mock_flow",
            "payload": {},
        },
    )
    monkeypatch.setattr(
        "service.quant.industry_service.fetch_announcements",
        lambda code, limit=15: [
            {
                "title": f"{code} 一季报",
                "url": f"https://example.com/{code}/ann",
                "published_at": "2026-07-03",
                "source": "mock_ann",
                "domain": "example.com",
                "summary": "业绩披露",
                "payload": {},
            }
        ],
    )
    monkeypatch.setattr(
        "service.quant.industry_service.fetch_ths_stock_news",
        lambda code, name, limit=20: [
            {
                "title": f"{name} 新闻",
                "url": f"https://example.com/{code}/news",
                "published_at": "2026-07-03",
                "source": "mock_news",
                "domain": "example.com",
                "summary": "个股资讯",
                "payload": {},
            }
        ],
    )
    monkeypatch.setattr(
        "service.quant.industry_service.fetch_research_reports",
        lambda code, limit=10: [
            {
                "title": f"{code} 研报",
                "url": f"https://example.com/{code}/report",
                "published_at": "2026-07-03",
                "org_name": "测试机构",
                "rating": "买入",
                "source": "mock_report",
                "payload": {},
            }
        ],
    )


def test_default_boards_seeded():
    boards = list_industry_boards()
    assert {item["board_key"] for item in boards} >= {"tungsten", "pcb_drill"}
    assert any(symbol["symbol"] == "000657.SZ" for item in boards for symbol in item["symbols"])
    assert any(symbol["symbol"] == "301377.SZ" for item in boards for symbol in item["symbols"])


def test_collect_industry_writes_dashboard_data(monkeypatch):
    _patch_collectors(monkeypatch)

    result = collect_industry()

    assert result["market_snapshots"] == 2
    assert result["daily_bars"] == 2
    assert result["news_items"] == 2
    assert result["announcements"] == 2
    assert result["research_reports"] == 2
    assert result["errors"] == []
    assert QuantMarketSnapshot.select().count() == 2
    assert QuantDailyBar.select().count() == 2
    assert QuantIndustryNewsItem.select().count() == 4
    assert QuantResearchReportItem.select().count() == 2

    dashboard = get_industry_dashboard(board_key="tungsten")
    assert dashboard["latest_trade_date"] == "2026-07-03"
    assert dashboard["latest_cards"][0]["symbol"] == "000657.SZ"
    assert dashboard["news"]
    assert dashboard["research_reports"]
