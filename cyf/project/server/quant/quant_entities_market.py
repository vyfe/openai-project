import json
from datetime import date, datetime

from peewee import BooleanField, CharField, DateField, DateTimeField, FloatField, IntegerField, Model, TextField

from quant.db import quant_db


class QuantBaseModel(Model):
    class Meta:
        database = quant_db


class QuantBaseModel(Model):
    class Meta:
        database = quant_db


class QuantInstrument(QuantBaseModel):
    symbol = CharField(unique=True)
    code = CharField(index=True)
    exchange = CharField(index=True)
    market = CharField(default="A_SHARE", index=True)
    name = CharField(default="")
    source = CharField(default="")
    status = CharField(default="active")
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)

    class Meta:
        table_name = "quant_instrument"


class QuantDailyBar(QuantBaseModel):
    symbol = CharField(index=True)
    code = CharField(index=True)
    exchange = CharField(index=True)
    trade_date = DateField(index=True)
    adjust_flag = CharField(default="qfq", index=True)
    open_price = FloatField(null=True)
    high_price = FloatField(null=True)
    low_price = FloatField(null=True)
    close_price = FloatField(null=True)
    preclose_price = FloatField(null=True)
    volume = FloatField(null=True)
    amount = FloatField(null=True)
    turnover_rate = FloatField(null=True)
    pct_change = FloatField(null=True)
    change = FloatField(null=True)
    amplitude_pct = FloatField(null=True)
    source = CharField(default="")
    source_run_id = CharField(default="", index=True)
    data_source_version = CharField(default="")
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)

    class Meta:
        table_name = "quant_daily_bar"
        indexes = ((( "symbol", "trade_date", "adjust_flag"), True),)

    def to_dict(self):
        return {
            "id": self.id,
            "symbol": self.symbol,
            "code": self.code,
            "exchange": self.exchange,
            "trade_date": self.trade_date.isoformat() if isinstance(self.trade_date, date) else None,
            "adjust_flag": self.adjust_flag,
            "open_price": self.open_price,
            "high_price": self.high_price,
            "low_price": self.low_price,
            "close_price": self.close_price,
            "preclose_price": self.preclose_price,
            "volume": self.volume,
            "amount": self.amount,
            "turnover_rate": self.turnover_rate,
            "pct_change": self.pct_change,
            "source": self.source,
            "source_run_id": self.source_run_id,
            "data_source_version": self.data_source_version,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class QuantImportBatch(QuantBaseModel):
    batch_id = CharField(unique=True)
    dataset = CharField(index=True)
    source = CharField(index=True)
    source_run_id = CharField(default="", index=True)
    file_name = CharField(default="")
    payload_sha256 = CharField(default="")
    status = CharField(default="pending", index=True)
    records_total = IntegerField(default=0)
    records_imported = IntegerField(default=0)
    message = TextField(default="")
    created_at = DateTimeField(default=datetime.now)
    finished_at = DateTimeField(null=True)

    class Meta:
        table_name = "quant_import_batch"

    def to_dict(self):
        return {
            "id": self.id,
            "batch_id": self.batch_id,
            "dataset": self.dataset,
            "source": self.source,
            "source_run_id": self.source_run_id,
            "file_name": self.file_name,
            "payload_sha256": self.payload_sha256,
            "status": self.status,
            "records_total": self.records_total,
            "records_imported": self.records_imported,
            "message": self.message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
        }


class QuantMarketSnapshot(QuantBaseModel):
    board_id = IntegerField(index=True)
    symbol = CharField(index=True)
    code = CharField(index=True)
    exchange = CharField(index=True)
    name = CharField(default="")
    trade_date = DateField(index=True)
    current_price = FloatField(null=True)
    open_price = FloatField(null=True)
    high_price = FloatField(null=True)
    low_price = FloatField(null=True)
    close_price = FloatField(null=True)
    preclose_price = FloatField(null=True)
    pct_change = FloatField(null=True)
    volume = FloatField(null=True)
    amount = FloatField(null=True)
    pe_ttm = FloatField(null=True)
    pb = FloatField(null=True)
    market_cap = FloatField(null=True)
    float_market_cap = FloatField(null=True)
    main_flow = FloatField(null=True)
    super_large_flow = FloatField(null=True)
    large_flow = FloatField(null=True)
    mid_flow = FloatField(null=True)
    small_flow = FloatField(null=True)
    main_flow_pct = FloatField(null=True)
    source = CharField(default="")
    payload_json = TextField(default="{}")
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)

    class Meta:
        table_name = "quant_market_snapshot"
        indexes = ((( "board_id", "symbol", "trade_date"), True),)

    def to_dict(self):
        return {
            "id": self.id,
            "board_id": self.board_id,
            "symbol": self.symbol,
            "code": self.code,
            "exchange": self.exchange,
            "name": self.name,
            "trade_date": self.trade_date.isoformat() if isinstance(self.trade_date, date) else None,
            "current_price": self.current_price,
            "open_price": self.open_price,
            "high_price": self.high_price,
            "low_price": self.low_price,
            "close_price": self.close_price,
            "preclose_price": self.preclose_price,
            "pct_change": self.pct_change,
            "volume": self.volume,
            "amount": self.amount,
            "pe_ttm": self.pe_ttm,
            "pb": self.pb,
            "market_cap": self.market_cap,
            "float_market_cap": self.float_market_cap,
            "main_flow": self.main_flow,
            "super_large_flow": self.super_large_flow,
            "large_flow": self.large_flow,
            "mid_flow": self.mid_flow,
            "small_flow": self.small_flow,
            "main_flow_pct": self.main_flow_pct,
            "source": self.source,
            "payload": json.loads(self.payload_json or "{}"),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class QuantIndustryBoard(QuantBaseModel):
    board_key = CharField(unique=True, index=True)
    name = CharField()
    description = TextField(default="")
    status = CharField(default="active", index=True)
    keywords_json = TextField(default="[]")
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)

    class Meta:
        table_name = "quant_industry_board"

    def to_dict(self):
        return {
            "id": self.id,
            "board_key": self.board_key,
            "name": self.name,
            "description": self.description,
            "status": self.status,
            "keywords": json.loads(self.keywords_json or "[]"),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class QuantIndustryWatchSymbol(QuantBaseModel):
    board_id = IntegerField(index=True)
    symbol = CharField(index=True)
    code = CharField(index=True)
    exchange = CharField(index=True)
    name = CharField(default="")
    role = TextField(default="")
    weight = FloatField(default=1.0)
    status = CharField(default="active", index=True)
    keywords_json = TextField(default="[]")
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)

    class Meta:
        table_name = "quant_industry_watch_symbol"
        indexes = ((( "board_id", "symbol"), True),)

    def to_dict(self):
        return {
            "id": self.id,
            "board_id": self.board_id,
            "symbol": self.symbol,
            "code": self.code,
            "exchange": self.exchange,
            "name": self.name,
            "role": self.role,
            "weight": self.weight,
            "status": self.status,
            "keywords": json.loads(self.keywords_json or "[]"),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class QuantIndustryNewsItem(QuantBaseModel):
    board_id = IntegerField(index=True)
    symbol = CharField(default="", index=True)
    code = CharField(default="", index=True)
    keyword = CharField(default="", index=True)
    title = TextField()
    url = TextField()
    url_hash = CharField(unique=True, index=True)
    source = CharField(default="")
    domain = CharField(default="")
    published_at = CharField(default="", index=True)
    summary = TextField(default="")
    payload_json = TextField(default="{}")
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)

    class Meta:
        table_name = "quant_industry_news_item"

    def to_dict(self):
        return {
            "id": self.id,
            "board_id": self.board_id,
            "symbol": self.symbol,
            "code": self.code,
            "keyword": self.keyword,
            "title": self.title,
            "url": self.url,
            "url_hash": self.url_hash,
            "source": self.source,
            "domain": self.domain,
            "published_at": self.published_at,
            "summary": self.summary,
            "payload": json.loads(self.payload_json or "{}"),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class QuantResearchReportItem(QuantBaseModel):
    board_id = IntegerField(index=True)
    symbol = CharField(default="", index=True)
    code = CharField(default="", index=True)
    title = TextField()
    url = TextField()
    url_hash = CharField(unique=True, index=True)
    org_name = CharField(default="", index=True)
    analyst = CharField(default="")
    rating = CharField(default="")
    target_price = FloatField(null=True)
    published_at = CharField(default="", index=True)
    summary = TextField(default="")
    source = CharField(default="")
    payload_json = TextField(default="{}")
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)

    class Meta:
        table_name = "quant_research_report_item"

    def to_dict(self):
        return {
            "id": self.id,
            "board_id": self.board_id,
            "symbol": self.symbol,
            "code": self.code,
            "title": self.title,
            "url": self.url,
            "url_hash": self.url_hash,
            "org_name": self.org_name,
            "analyst": self.analyst,
            "rating": self.rating,
            "target_price": self.target_price,
            "published_at": self.published_at,
            "summary": self.summary,
            "source": self.source,
            "payload": json.loads(self.payload_json or "{}"),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class QuantIndustryIndicatorSnapshot(QuantBaseModel):
    board_id = IntegerField(index=True)
    indicator_key = CharField(index=True)
    indicator_name = CharField()
    indicator_group = CharField(default="", index=True)
    subject_code = CharField(default="", index=True)
    subject_name = CharField(default="")
    observed_date = DateField(index=True)
    value = FloatField(null=True)
    unit = CharField(default="")
    source = CharField(default="")
    payload_json = TextField(default="{}")
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)

    class Meta:
        table_name = "quant_industry_indicator_snapshot"
        indexes = ((( "board_id", "indicator_key", "subject_code", "observed_date"), True),)

    def to_dict(self):
        return {
            "id": self.id,
            "board_id": self.board_id,
            "indicator_key": self.indicator_key,
            "indicator_name": self.indicator_name,
            "indicator_group": self.indicator_group,
            "subject_code": self.subject_code,
            "subject_name": self.subject_name,
            "observed_date": self.observed_date.isoformat() if isinstance(self.observed_date, date) else None,
            "value": self.value,
            "unit": self.unit,
            "source": self.source,
            "payload": json.loads(self.payload_json or "{}"),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class QuantDailyIndicator(QuantBaseModel):
    symbol = CharField(index=True)
    code = CharField(index=True)
    exchange = CharField(index=True)
    trade_date = DateField(index=True)
    adjust_flag = CharField(default="qfq", index=True)
    indicator_name = CharField(index=True)
    indicator_version = CharField(default="", index=True)
    params_json = TextField(default="{}")
    value_json = TextField(default="{}")
    source_bar_count = IntegerField(default=0)
    source_run_id = CharField(default="", index=True)
    data_source_version = CharField(default="")
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)

    class Meta:
        table_name = "quant_daily_indicator"
        indexes = (
            (("symbol", "trade_date", "adjust_flag", "indicator_name", "indicator_version"), True),
            (("indicator_name", "trade_date"), False),
        )

    def to_dict(self):
        return {
            "id": self.id,
            "symbol": self.symbol,
            "code": self.code,
            "exchange": self.exchange,
            "trade_date": self.trade_date.isoformat() if isinstance(self.trade_date, date) else None,
            "adjust_flag": self.adjust_flag,
            "indicator_name": self.indicator_name,
            "indicator_version": self.indicator_version,
            "params": json.loads(self.params_json or "{}"),
            "value": json.loads(self.value_json or "{}"),
            "source_bar_count": self.source_bar_count,
            "source_run_id": self.source_run_id,
            "data_source_version": self.data_source_version,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
