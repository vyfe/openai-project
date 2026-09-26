import json
from datetime import datetime
from typing import Optional

from quant.entities import QuantOperationRecord
from service.quant.common import normalize_symbol, parse_trade_date


def _normalize_tags(tags) -> list[str]:
    if tags is None:
        return []
    if isinstance(tags, str):
        text = tags.strip()
        if not text:
            return []
        if text.startswith("["):
            try:
                parsed = json.loads(text)
                if isinstance(parsed, list):
                    return [str(item).strip() for item in parsed if str(item).strip()]
            except Exception:
                pass
        return [item.strip() for item in text.split(",") if item.strip()]
    if isinstance(tags, list):
        return [str(item).strip() for item in tags if str(item).strip()]
    raise ValueError("tags 格式不正确")


def _normalize_meta(meta) -> dict:
    if meta is None:
        return {}
    if isinstance(meta, str):
        text = meta.strip()
        if not text:
            return {}
        return json.loads(text)
    if isinstance(meta, dict):
        return meta
    raise ValueError("meta 格式不正确")


def _normalize_number(value, *, integer: bool = False):
    if value in (None, ""):
        return None
    return int(value) if integer else float(value)


def _build_amount(price, quantity, amount):
    normalized_amount = _normalize_number(amount)
    if normalized_amount is not None:
        return normalized_amount
    normalized_price = _normalize_number(price)
    normalized_quantity = _normalize_number(quantity, integer=True)
    if normalized_price is not None and normalized_quantity is not None:
        return round(normalized_price * normalized_quantity, 4)
    return None


def list_operation_records(
    strategy_id: Optional[int] = None,
    symbol: Optional[str] = None,
    status: Optional[str] = None,
    action: Optional[str] = None,
    result_status: Optional[str] = None,
    date_from=None,
    date_to=None,
    created_by: Optional[str] = None,
    limit: int = 100,
) -> list[dict]:
    query = QuantOperationRecord.select()
    if strategy_id:
        query = query.where(QuantOperationRecord.strategy_id == strategy_id)
    if symbol:
        query = query.where(QuantOperationRecord.symbol == normalize_symbol(symbol))
    if status:
        query = query.where(QuantOperationRecord.status == status)
    if action:
        query = query.where(QuantOperationRecord.action == action)
    if result_status:
        query = query.where(QuantOperationRecord.result_status == result_status)
    if date_from:
        query = query.where(QuantOperationRecord.trade_date >= parse_trade_date(date_from))
    if date_to:
        query = query.where(QuantOperationRecord.trade_date <= parse_trade_date(date_to))
    if created_by is not None:
        query = query.where(QuantOperationRecord.created_by == str(created_by).strip())
    query = query.order_by(QuantOperationRecord.trade_date.desc(), QuantOperationRecord.id.desc()).limit(limit)
    return [item.to_dict() for item in query.iterator()]


def get_operation_record(record_id: int, created_by: Optional[str] = None) -> dict:
    query = QuantOperationRecord.select().where(QuantOperationRecord.id == record_id)
    if created_by is not None:
        query = query.where(QuantOperationRecord.created_by == str(created_by).strip())
    return query.get().to_dict()


def create_operation_record(
    *,
    symbol: str,
    trade_date,
    created_by: str,
    action: str = "buy",
    status: str = "draft",
    result_status: str = "",
    strategy_id=None,
    run_id=None,
    signal_id=None,
    price=None,
    quantity=None,
    amount=None,
    thesis: str = "",
    execution_note: str = "",
    review_note: str = "",
    result_pct=None,
    result_amount=None,
    tags=None,
    meta=None,
) -> dict:
    record = QuantOperationRecord.create(
        strategy_id=int(strategy_id) if strategy_id not in (None, "") else None,
        run_id=int(run_id) if run_id not in (None, "") else None,
        signal_id=int(signal_id) if signal_id not in (None, "") else None,
        symbol=normalize_symbol(symbol),
        action=str(action or "buy").strip() or "buy",
        status=str(status or "draft").strip() or "draft",
        result_status=str(result_status or "").strip(),
        trade_date=parse_trade_date(trade_date),
        price=_normalize_number(price),
        quantity=_normalize_number(quantity, integer=True),
        amount=_build_amount(price, quantity, amount),
        thesis=str(thesis or "").strip(),
        execution_note=str(execution_note or "").strip(),
        review_note=str(review_note or "").strip(),
        result_pct=_normalize_number(result_pct),
        result_amount=_normalize_number(result_amount),
        tags_json=json.dumps(_normalize_tags(tags), ensure_ascii=False),
        meta_json=json.dumps(_normalize_meta(meta), ensure_ascii=False),
        created_by=str(created_by or "").strip(),
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    result_dict = record.to_dict()
    # 新建即 executed：diff 视为 None → "executed"，触发持仓联动
    if str(status or "draft").strip().lower() == "executed":
        try:
            _apply_position_change(record, from_status=None, to_status="executed")
        except Exception as exc:
            # 持仓同步失败不应阻断主流程，但应记录
            import logging
            logging.getLogger("quant.ops").warning(
                "operation_create_position_sync_failed | operation_id=%s | error=%s",
                record.id, exc,
            )
    return result_dict


def update_operation_record(record_id: int, **updates) -> dict:
    record = QuantOperationRecord.get_by_id(record_id)
    old_status = record.status

    if "strategy_id" in updates:
        record.strategy_id = int(updates["strategy_id"]) if updates["strategy_id"] not in (None, "") else None
    if "run_id" in updates:
        record.run_id = int(updates["run_id"]) if updates["run_id"] not in (None, "") else None
    if "signal_id" in updates:
        record.signal_id = int(updates["signal_id"]) if updates["signal_id"] not in (None, "") else None
    if "symbol" in updates:
        record.symbol = normalize_symbol(updates["symbol"])
    if "action" in updates:
        record.action = str(updates["action"] or "buy").strip() or "buy"
    if "status" in updates:
        record.status = str(updates["status"] or "draft").strip() or "draft"
    if "result_status" in updates:
        record.result_status = str(updates["result_status"] or "").strip()
    if "trade_date" in updates:
        record.trade_date = parse_trade_date(updates["trade_date"])
    if "price" in updates:
        record.price = _normalize_number(updates["price"])
    if "quantity" in updates:
        record.quantity = _normalize_number(updates["quantity"], integer=True)
    if any(key in updates for key in ("amount", "price", "quantity")):
        amount_source = updates["amount"] if "amount" in updates else record.amount
        price_source = updates["price"] if "price" in updates else record.price
        quantity_source = updates["quantity"] if "quantity" in updates else record.quantity
        record.amount = _build_amount(price_source, quantity_source, amount_source)
    if "thesis" in updates:
        record.thesis = str(updates["thesis"] or "").strip()
    if "execution_note" in updates:
        record.execution_note = str(updates["execution_note"] or "").strip()
    if "review_note" in updates:
        record.review_note = str(updates["review_note"] or "").strip()
    if "result_pct" in updates:
        record.result_pct = _normalize_number(updates["result_pct"])
    if "result_amount" in updates:
        record.result_amount = _normalize_number(updates["result_amount"])
    if "tags" in updates:
        record.tags_json = json.dumps(_normalize_tags(updates["tags"]), ensure_ascii=False)
    if "meta" in updates:
        record.meta_json = json.dumps(_normalize_meta(updates["meta"]), ensure_ascii=False)

    record.updated_at = datetime.now()
    record.save()
    # 状态变更触发持仓联动
    new_status = record.status
    if "status" in updates and old_status != new_status:
        try:
            _apply_position_change(record, from_status=old_status, to_status=new_status)
        except Exception as exc:
            import logging
            logging.getLogger("quant.ops").warning(
                "operation_update_position_sync_failed | operation_id=%s | error=%s",
                record_id, exc,
            )
    return record.to_dict()


def delete_operation_record(record_id: int) -> bool:
    record = QuantOperationRecord.get_by_id(record_id)
    record.delete_instance()
    return True



def _reverse_side(side: str) -> str:
    """动作反向映射（用于反向计提）。"""
    return {"buy": "sell", "sell": "buy", "add": "reduce", "reduce": "add"}.get(side, "sell")


def _apply_position_change(record, *, from_status, to_status):
    """操作记录状态变更时同步持仓流水。

    规则：
    - None/draft/... → executed：创建一条正向流水（计入持仓）
    - executed → 其他状态：创建一条反向流水（计提持仓，自动抵消 net_quantity）
    - watch 动作（数量为 0/None）：跳过
    - created_by 为空：跳过（没有 user 维度，无法归属持仓）
    """
    # watch 不影响持仓
    if str(record.action or "").strip().lower() == "watch":
        return
    # 没有数量不写持仓
    if not record.quantity or int(record.quantity) <= 0:
        return
    # 必须有 created_by 才能归属
    if not str(record.created_by or "").strip():
        return

    # 延迟导入避免循环
    from service.quant.position_service import create_position_entry

    if from_status != "executed" and to_status == "executed":
        # 其他状态 → 已执行：计入持仓
        create_position_entry(
            symbol=record.symbol,
            side=record.action,
            quantity=record.quantity,
            price=record.price,
            occurred_at=record.trade_date,
            source="operation_record",
            reason=str(record.thesis or "").strip(),
            created_by=record.created_by,
            operation_id=record.id,
        )
    elif from_status == "executed" and to_status != "executed":
        # 已执行 → 其他状态：反向计提
        create_position_entry(
            symbol=record.symbol,
            side=_reverse_side(record.action),
            quantity=record.quantity,
            price=record.price,
            occurred_at=record.trade_date,
            source="operation_revoked",
            reason=f"操作 #{record.id} 状态从 executed 变更为 {to_status}",
            created_by=record.created_by,
            operation_id=record.id,
        )
