import json
from datetime import date, datetime

from peewee import BooleanField, CharField, DateField, DateTimeField, FloatField, IntegerField, Model, TextField

from quant.db import quant_db


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


class QuantStrategy(QuantBaseModel):
    name = CharField(unique=True)
    market = CharField(default="A_SHARE", index=True)
    status = CharField(default="active", index=True)
    description = TextField(default="")
    symbols_json = TextField(default="[]")
    rule_config_json = TextField(default="{}")
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)

    class Meta:
        table_name = "quant_strategy"

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "market": self.market,
            "status": self.status,
            "description": self.description,
            "symbols": json.loads(self.symbols_json or "[]"),
            "rule_config": json.loads(self.rule_config_json or "{}"),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class QuantStrategyRun(QuantBaseModel):
    strategy_id = IntegerField(index=True)
    run_key = CharField(unique=True)
    trade_date = DateField(index=True)
    status = CharField(default="running", index=True)
    symbols_total = IntegerField(default=0)
    signals_total = IntegerField(default=0)
    summary_json = TextField(default="{}")
    error_message = TextField(default="")
    created_at = DateTimeField(default=datetime.now)
    finished_at = DateTimeField(null=True)

    class Meta:
        table_name = "quant_strategy_run"
        indexes = ((( "strategy_id", "trade_date"), False),)

    def to_dict(self):
        return {
            "id": self.id,
            "strategy_id": self.strategy_id,
            "run_key": self.run_key,
            "trade_date": self.trade_date.isoformat() if isinstance(self.trade_date, date) else None,
            "status": self.status,
            "symbols_total": self.symbols_total,
            "signals_total": self.signals_total,
            "summary": json.loads(self.summary_json or "{}"),
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
        }


class QuantStrategySignal(QuantBaseModel):
    run_id = IntegerField(index=True)
    strategy_id = IntegerField(index=True)
    symbol = CharField(index=True)
    trade_date = DateField(index=True)
    passed = BooleanField(default=False, index=True)
    score = FloatField(default=0)
    signal_type = CharField(default="watch")
    reasons_json = TextField(default="[]")
    metrics_json = TextField(default="{}")
    created_at = DateTimeField(default=datetime.now)

    class Meta:
        table_name = "quant_strategy_signal"
        indexes = ((( "run_id", "symbol"), True),)

    def to_dict(self):
        return {
            "id": self.id,
            "run_id": self.run_id,
            "strategy_id": self.strategy_id,
            "symbol": self.symbol,
            "trade_date": self.trade_date.isoformat() if isinstance(self.trade_date, date) else None,
            "passed": self.passed,
            "score": self.score,
            "signal_type": self.signal_type,
            "reasons": json.loads(self.reasons_json or "[]"),
            "metrics": json.loads(self.metrics_json or "{}"),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class QuantOperationRecord(QuantBaseModel):
    strategy_id = IntegerField(null=True, index=True)
    run_id = IntegerField(null=True, index=True)
    signal_id = IntegerField(null=True, index=True)
    symbol = CharField(index=True)
    action = CharField(default="buy", index=True)
    status = CharField(default="draft", index=True)
    result_status = CharField(default="", index=True)
    trade_date = DateField(index=True)
    price = FloatField(null=True)
    quantity = IntegerField(null=True)
    amount = FloatField(null=True)
    thesis = TextField(default="")
    execution_note = TextField(default="")
    review_note = TextField(default="")
    result_pct = FloatField(null=True)
    result_amount = FloatField(null=True)
    tags_json = TextField(default="[]")
    meta_json = TextField(default="{}")
    created_by = CharField(default="", index=True)
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)

    class Meta:
        table_name = "quant_operation_record"
        indexes = ((("symbol", "trade_date"), False),)

    def to_dict(self):
        return {
            "id": self.id,
            "strategy_id": self.strategy_id,
            "run_id": self.run_id,
            "signal_id": self.signal_id,
            "symbol": self.symbol,
            "action": self.action,
            "status": self.status,
            "result_status": self.result_status,
            "trade_date": self.trade_date.isoformat() if isinstance(self.trade_date, date) else None,
            "price": self.price,
            "quantity": self.quantity,
            "amount": self.amount,
            "thesis": self.thesis,
            "execution_note": self.execution_note,
            "review_note": self.review_note,
            "result_pct": self.result_pct,
            "result_amount": self.result_amount,
            "tags": json.loads(self.tags_json or "[]"),
            "meta": json.loads(self.meta_json or "{}"),
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class QuantBacktestRun(QuantBaseModel):
    strategy_id = IntegerField(index=True)
    strategy_name = CharField(default="")
    status = CharField(default="running", index=True)
    mode = CharField(default="event_study")
    start_date = DateField(index=True)
    end_date = DateField(index=True)
    benchmark_symbol = CharField(default="")
    hold_days = IntegerField(default=5)
    top_n = IntegerField(default=3)
    initial_capital = FloatField(default=100000.0)
    commission_rate = FloatField(default=0.001)
    slippage_rate = FloatField(default=0.0005)
    signals_total = IntegerField(default=0)
    trades_total = IntegerField(default=0)
    summary_json = TextField(default="{}")
    metrics_json = TextField(default="{}")
    equity_curve_json = TextField(default="[]")
    trades_json = TextField(default="[]")
    strategy_snapshot_json = TextField(default="{}")
    data_source_version = CharField(default="")
    code_version = CharField(default="")
    error_message = TextField(default="")
    created_at = DateTimeField(default=datetime.now)
    finished_at = DateTimeField(null=True)

    class Meta:
        table_name = "quant_backtest_run"
        indexes = ((("strategy_id", "start_date", "end_date"), False),)

    def to_dict(self):
        return {
            "id": self.id,
            "strategy_id": self.strategy_id,
            "strategy_name": self.strategy_name,
            "status": self.status,
            "mode": self.mode,
            "start_date": self.start_date.isoformat() if isinstance(self.start_date, date) else None,
            "end_date": self.end_date.isoformat() if isinstance(self.end_date, date) else None,
            "benchmark_symbol": self.benchmark_symbol,
            "hold_days": self.hold_days,
            "top_n": self.top_n,
            "initial_capital": self.initial_capital,
            "commission_rate": self.commission_rate,
            "slippage_rate": self.slippage_rate,
            "signals_total": self.signals_total,
            "trades_total": self.trades_total,
            "summary": json.loads(self.summary_json or "{}"),
            "metrics": json.loads(self.metrics_json or "{}"),
            "equity_curve": json.loads(self.equity_curve_json or "[]"),
            "trades": json.loads(self.trades_json or "[]"),
            "strategy_snapshot": json.loads(self.strategy_snapshot_json or "{}"),
            "data_source_version": self.data_source_version,
            "code_version": self.code_version,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
        }


class QuantScheduleConfig(QuantBaseModel):
    name = CharField(unique=True)
    task_type = CharField(index=True)
    status = CharField(default="active", index=True)
    cron_expr = CharField()
    market_calendar = CharField(default="A_SHARE", index=True)
    timezone = CharField(default="Asia/Shanghai")
    payload_json = TextField(default="{}")
    retry_max = IntegerField(default=1)
    retry_delay_seconds = IntegerField(default=180)
    allow_manual_run = BooleanField(default=True)
    description = TextField(default="")
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)

    class Meta:
        table_name = "quant_schedule_config"

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "task_type": self.task_type,
            "status": self.status,
            "cron_expr": self.cron_expr,
            "market_calendar": self.market_calendar,
            "timezone": self.timezone,
            "payload": json.loads(self.payload_json or "{}"),
            "retry_max": self.retry_max,
            "retry_delay_seconds": self.retry_delay_seconds,
            "allow_manual_run": self.allow_manual_run,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class QuantScheduleRun(QuantBaseModel):
    schedule_id = IntegerField(index=True)
    schedule_name = CharField(default="")
    task_type = CharField(index=True)
    run_key = CharField(unique=True)
    trigger_source = CharField(default="cron", index=True)
    status = CharField(default="pending", index=True)
    scheduled_for = DateTimeField(index=True)
    trade_date = DateField(null=True, index=True)
    attempts = IntegerField(default=0)
    max_retries = IntegerField(default=1)
    next_retry_at = DateTimeField(null=True, index=True)
    message = TextField(default="")
    payload_json = TextField(default="{}")
    result_json = TextField(default="{}")
    created_at = DateTimeField(default=datetime.now)
    started_at = DateTimeField(null=True)
    finished_at = DateTimeField(null=True)

    class Meta:
        table_name = "quant_schedule_run"
        indexes = (
            (("schedule_id", "scheduled_for"), False),
            (("status", "scheduled_for"), False),
        )

    def to_dict(self):
        return {
            "id": self.id,
            "schedule_id": self.schedule_id,
            "schedule_name": self.schedule_name,
            "task_type": self.task_type,
            "run_key": self.run_key,
            "trigger_source": self.trigger_source,
            "status": self.status,
            "scheduled_for": self.scheduled_for.isoformat() if self.scheduled_for else None,
            "trade_date": self.trade_date.isoformat() if isinstance(self.trade_date, date) else None,
            "attempts": self.attempts,
            "max_retries": self.max_retries,
            "next_retry_at": self.next_retry_at.isoformat() if self.next_retry_at else None,
            "message": self.message,
            "payload": json.loads(self.payload_json or "{}"),
            "result": json.loads(self.result_json or "{}"),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
        }


QUANT_MODELS = [
    QuantInstrument,
    QuantDailyBar,
    QuantImportBatch,
    QuantStrategy,
    QuantStrategyRun,
    QuantStrategySignal,
    QuantOperationRecord,
    QuantBacktestRun,
    QuantScheduleConfig,
    QuantScheduleRun,
]
