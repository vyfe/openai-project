"""行业板块业务服务（按职责拆分）。

- :mod:`service.quant.industry_common` —— 共享工具（_fetch_text/_fetch_json/_now 等）
- :mod:`service.quant.industry_board_service` —— 板块 CRUD、默认板块
- :mod:`service.quant.industry_quote_service` —— 行情拉取（K线/快照/资金流）
- :mod:`service.quant.industry_news_service` —— 公告/新闻/研报采集
- :mod:`service.quant.industry_indicator_service` —— 指标/dashboard/markdown 渲染

本文件仅做 re-export，保留旧导入路径 `from service.quant.industry_service import ...`。
"""

from service.quant.industry_board_service import (
    collect_industry,
    create_or_update_industry_board,
    ensure_default_industry_boards,
    get_industry_board,
    list_industry_boards,
)
from service.quant.industry_common import (
    _fetch_json,
    _fetch_text,
    _get_secid,
    _json_dumps,
    _market_prefix,
    _now,
    _url_hash,
)
from service.quant.industry_indicator_service import (
    _fmt,
    _indicator_row,
    _scaled,
    collect_indicator_snapshots,
    get_industry_dashboard,
    list_industry_news,
    list_research_reports,
    render_industry_daily_markdown,
)
from service.quant.industry_news_service import (
    _classify_event,
    _clean_escaped,
    _normalize_time_label,
    _save_news_like_items,
    collect_announcements,
    collect_news,
    collect_research_reports,
    fetch_announcements,
    fetch_research_reports,
    fetch_ths_stock_news,
)
from service.quant.industry_quote_service import (
    collect_market_snapshot,
    fetch_latest_capital_flow,
    fetch_latest_kline,
    fetch_quote,
    fetch_sina_snapshot,
)

# 保留向后兼容的模块级常量
from service.quant.industry_board_service import DEFAULT_INDUSTRY_BOARDS  # noqa: F401
from service.quant.industry_board_service import INDUSTRY_COLLECT_VERSION  # noqa: F401
