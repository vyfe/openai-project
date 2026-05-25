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
    log_file = CharField(default="")
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
            "log_file": self.log_file,
            "payload": json.loads(self.payload_json or "{}"),
            "result": json.loads(self.result_json or "{}"),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
        }


class QuantPromptTemplate(QuantBaseModel):
    strategy_id = IntegerField(null=True, index=True)
    template_name = CharField(default="default")
    prompt_version = CharField(index=True)
    status = CharField(default="active", index=True)
    report_type = CharField(default="test_report", index=True)
    prompt_template = TextField(default="")
    change_note = TextField(default="")
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)

    class Meta:
        table_name = "quant_prompt_template"
        indexes = ((("strategy_id", "prompt_version"), True),)

    def to_dict(self):
        return {
            "id": self.id,
            "strategy_id": self.strategy_id,
            "template_name": self.template_name,
            "prompt_version": self.prompt_version,
            "status": self.status,
            "report_type": self.report_type,
            "prompt_template": self.prompt_template,
            "change_note": self.change_note,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class QuantReportRecord(QuantBaseModel):
    report_key = CharField(unique=True)
    strategy_id = IntegerField(index=True)
    run_id = IntegerField(null=True, index=True)
    schedule_run_id = IntegerField(null=True, index=True)
    trade_date = DateField(index=True)
    report_type = CharField(default="test_report", index=True)
    status = CharField(default="success", index=True)
    bundle_version = CharField(default="analysis-bundle-v1")
    prompt_version = CharField(default="template-v1")
    title = CharField(default="")
    analysis_bundle_json = TextField(default="{}")
    report_draft_json = TextField(default="{}")
    final_markdown = TextField(default="")
    memory_references_json = TextField(default="[]")
    meta_json = TextField(default="{}")
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)

    class Meta:
        table_name = "quant_report_record"
        indexes = (
            (("strategy_id", "trade_date"), False),
            (("run_id", "report_type"), False),
        )

    def to_dict(self):
        return {
            "id": self.id,
            "report_key": self.report_key,
            "strategy_id": self.strategy_id,
            "run_id": self.run_id,
            "schedule_run_id": self.schedule_run_id,
            "trade_date": self.trade_date.isoformat() if isinstance(self.trade_date, date) else None,
            "report_type": self.report_type,
            "status": self.status,
            "bundle_version": self.bundle_version,
            "prompt_version": self.prompt_version,
            "title": self.title,
            "analysis_bundle": json.loads(self.analysis_bundle_json or "{}"),
            "report_draft": json.loads(self.report_draft_json or "{}"),
            "final_markdown": self.final_markdown,
            "memory_references": json.loads(self.memory_references_json or "[]"),
            "meta": json.loads(self.meta_json or "{}"),
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


class QuantImChannel(QuantBaseModel):
    name = CharField(unique=True)
    channel_type = CharField(default="feishu_app", index=True)
    status = CharField(default="active", index=True)
    config_json = TextField(default="{}")
    mention_list_json = TextField(default="[]")
    description = TextField(default="")
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)

    class Meta:
        table_name = "quant_im_channel"

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "channel_type": self.channel_type,
            "status": self.status,
            "config": json.loads(self.config_json or "{}"),
            "mention_list": json.loads(self.mention_list_json or "[]"),
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class QuantReportDelivery(QuantBaseModel):
    report_id = IntegerField(null=True, index=True)
    run_id = IntegerField(null=True, index=True)
    channel_id = IntegerField(null=True, index=True)
    channel_type = CharField(default="feishu_app", index=True)
    channel_target = TextField(default="")
    message_type = CharField(default="markdown")
    status = CharField(default="pending", index=True)
    request_payload_json = TextField(default="{}")
    response_payload_json = TextField(default="{}")
    error_message = TextField(default="")
    sent_at = DateTimeField(null=True, index=True)
    created_at = DateTimeField(default=datetime.now)

    class Meta:
        table_name = "quant_report_delivery"
        indexes = (
            (("report_id", "channel_id"), False),
            (("status", "created_at"), False),
        )

    def to_dict(self):
        return {
            "id": self.id,
            "report_id": self.report_id,
            "run_id": self.run_id,
            "channel_id": self.channel_id,
            "channel_type": self.channel_type,
            "channel_target": self.channel_target,
            "message_type": self.message_type,
            "status": self.status,
            "request_payload": json.loads(self.request_payload_json or "{}"),
            "response_payload": json.loads(self.response_payload_json or "{}"),
            "error_message": self.error_message,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class QuantImInboundEvent(QuantBaseModel):
    event_id = CharField(unique=True)
    channel_id = IntegerField(null=True, index=True)
    channel_type = CharField(default="feishu_app", index=True)
    message_id = CharField(default="", index=True)
    chat_id = CharField(default="", index=True)
    sender_id = CharField(default="", index=True)
    sender_type = CharField(default="")
    message_type = CharField(default="")
    command = CharField(default="", index=True)
    status = CharField(default="received", index=True)
    raw_payload_json = TextField(default="{}")
    parsed_payload_json = TextField(default="{}")
    response_payload_json = TextField(default="{}")
    error_message = TextField(default="")
    received_at = DateTimeField(default=datetime.now, index=True)
    processed_at = DateTimeField(null=True)

    class Meta:
        table_name = "quant_im_inbound_event"
        indexes = (
            (("chat_id", "received_at"), False),
            (("sender_id", "received_at"), False),
            (("status", "received_at"), False),
        )

    def to_dict(self):
        return {
            "id": self.id,
            "event_id": self.event_id,
            "channel_id": self.channel_id,
            "channel_type": self.channel_type,
            "message_id": self.message_id,
            "chat_id": self.chat_id,
            "sender_id": self.sender_id,
            "sender_type": self.sender_type,
            "message_type": self.message_type,
            "command": self.command,
            "status": self.status,
            "raw_payload": json.loads(self.raw_payload_json or "{}"),
            "parsed_payload": json.loads(self.parsed_payload_json or "{}"),
            "response_payload": json.loads(self.response_payload_json or "{}"),
            "error_message": self.error_message,
            "received_at": self.received_at.isoformat() if self.received_at else None,
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
        }


class QuantPositionJournal(QuantBaseModel):
    strategy_id = IntegerField(null=True, index=True)
    run_id = IntegerField(null=True, index=True)
    operation_id = IntegerField(null=True, index=True)
    symbol = CharField(index=True)
    side = CharField(default="buy", index=True)
    price = FloatField(null=True)
    quantity = IntegerField(default=0)
    occurred_at = DateTimeField(index=True)
    source = CharField(default="manual", index=True)
    reason = TextField(default="")
    remark = TextField(default="")
    created_by = CharField(default="", index=True)
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)

    class Meta:
        table_name = "quant_position_journal"
        indexes = (
            (("symbol", "occurred_at"), False),
            (("strategy_id", "occurred_at"), False),
        )

    def to_dict(self):
        return {
            "id": self.id,
            "strategy_id": self.strategy_id,
            "run_id": self.run_id,
            "operation_id": self.operation_id,
            "symbol": self.symbol,
            "side": self.side,
            "price": self.price,
            "quantity": self.quantity,
            "occurred_at": self.occurred_at.isoformat() if self.occurred_at else None,
            "source": self.source,
            "reason": self.reason,
            "remark": self.remark,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }




class QuantFeishuUserBinding(QuantBaseModel):
    """飞书用户与慧聊用户绑定关系"""
    feishu_open_id = CharField(unique=True, index=True)
    username = CharField(index=True)
    bound_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)

    class Meta:
        table_name = "quant_feishu_user_binding"

    def to_dict(self):
        return {
            "id": self.id,
            "feishu_open_id": self.feishu_open_id,
            "username": self.username,
            "bound_at": self.bound_at.isoformat() if self.bound_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

QUANT_MODELS = [
    QuantInstrument,
    QuantDailyBar,
    QuantDailyIndicator,
    QuantImportBatch,
    QuantStrategy,
    QuantStrategyRun,
    QuantStrategySignal,
    QuantOperationRecord,
    QuantBacktestRun,
    QuantScheduleConfig,
    QuantScheduleRun,
    QuantPromptTemplate,
    QuantReportRecord,
    QuantImChannel,
    QuantReportDelivery,
    QuantImInboundEvent,
    QuantPositionJournal,
    QuantFeishuUserBinding,
]
