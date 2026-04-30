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
    limit: int = 100,
) -> list[dict]:
    query = QuantOperationRecord.select()
    if strategy_id:
        query = query.where(QuantOperationRecord.strategy_id == strategy_id)
    if symbol:
        query = query.where(QuantOperationRecord.symbol == normalize_symbol(symbol))
    if status:
        query = query.where(QuantOperationRecord.status == status)
    query = query.order_by(QuantOperationRecord.trade_date.desc(), QuantOperationRecord.id.desc()).limit(limit)
    return [item.to_dict() for item in query.iterator()]


def get_operation_record(record_id: int) -> dict:
    return QuantOperationRecord.get_by_id(record_id).to_dict()


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
    return record.to_dict()


def update_operation_record(record_id: int, **updates) -> dict:
    record = QuantOperationRecord.get_by_id(record_id)

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
    return record.to_dict()


def delete_operation_record(record_id: int) -> bool:
    record = QuantOperationRecord.get_by_id(record_id)
    record.delete_instance()
    return True
