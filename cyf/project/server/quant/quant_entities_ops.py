import json
from datetime import date, datetime

from peewee import BooleanField, CharField, DateField, DateTimeField, FloatField, IntegerField, Model, TextField

from quant.db import quant_db


class QuantBaseModel(Model):
    class Meta:
        database = quant_db


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
    model_name = CharField(default="")
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
            "model_name": self.model_name,
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


class QuantImChannel(QuantBaseModel):
    name = CharField(unique=True)
    channel_type = CharField(default="feishu_app", index=True)
    status = CharField(default="active", index=True)
    # webhook_url 是历史遗留字段（NOT NULL，无业务读写）。保留以对齐现有 DB schema，
    # 业务代码不读写它。如需清理，请走专门的迁移脚本。
    webhook_url = TextField(default="")
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
            "webhook_url": self.webhook_url,
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


class QuantClientTask(QuantBaseModel):
    """数据采集 Agent 任务队列。跨进程持久化（web / scheduler / agent 共用同一份 quant.db）。"""
    task_id = CharField(unique=True, index=True)
    task_type = CharField(default="", index=True)
    status = CharField(default="pending", index=True)
    payload_json = TextField(default="{}")
    note = TextField(default="")
    client_id = CharField(default="", index=True)
    lease_seconds = IntegerField(default=600)
    lease_expires_at = DateTimeField(null=True, index=True)
    leased_at = DateTimeField(null=True)
    attempts = IntegerField(default=0)
    message = TextField(default="")
    import_batch_json = TextField(default="{}")
    schedule_run_id = IntegerField(null=True, index=True)
    created_at = DateTimeField(default=datetime.now, index=True)
    finished_at = DateTimeField(null=True)

    class Meta:
        table_name = "quant_client_task"
        indexes = (
            (("status", "lease_expires_at"), False),
        )

    def to_dict(self):
        return {
            "id": self.id,
            "task_id": self.task_id,
            "task_type": self.task_type,
            "status": self.status,
            "payload": json.loads(self.payload_json or "{}"),
            "note": self.note,
            "client_id": self.client_id,
            "lease_seconds": self.lease_seconds,
            "lease_expires_at": self.lease_expires_at.isoformat() if self.lease_expires_at else None,
            "leased_at": self.leased_at.isoformat() if self.leased_at else None,
            "attempts": self.attempts,
            "message": self.message,
            "import_batch": json.loads(self.import_batch_json or "{}"),
            "schedule_run_id": self.schedule_run_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
        }
