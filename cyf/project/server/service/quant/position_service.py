from __future__ import annotations

from datetime import datetime
from typing import Optional

from quant.entities import QuantDailyBar, QuantPositionJournal
from service.quant.common import normalize_symbol


def _parse_occurred_at(value) -> datetime:
    if isinstance(value, datetime):
        return value
    text = str(value or "").strip()
    if not text:
        raise ValueError("occurred_at 不能为空")
    normalized = text.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    raise ValueError(f"无法解析 occurred_at: {value}")


def _normalize_side(value: str) -> str:
    side = str(value or "buy").strip().lower()
    if side not in ("buy", "sell"):
        raise ValueError("side 仅支持 buy / sell")
    return side


def _to_int(value, *, default: Optional[int] = None) -> Optional[int]:
    if value in (None, ""):
        return default
    return int(value)


def _to_float(value, *, default: Optional[float] = None) -> Optional[float]:
    if value in (None, ""):
        return default
    return float(value)


def _signed_quantity(side: str, quantity: int) -> int:
    return quantity if side == "buy" else -quantity


def list_position_journal(
    strategy_id: Optional[int] = None,
    symbol: Optional[str] = None,
    source: Optional[str] = None,
    limit: int = 100,
) -> list[dict]:
    query = QuantPositionJournal.select()
    if strategy_id:
        query = query.where(QuantPositionJournal.strategy_id == strategy_id)
    if symbol:
        query = query.where(QuantPositionJournal.symbol == normalize_symbol(symbol))
    if source:
        query = query.where(QuantPositionJournal.source == source)
    query = query.order_by(QuantPositionJournal.occurred_at.desc(), QuantPositionJournal.id.desc()).limit(limit)
    return [item.to_dict() for item in query.iterator()]


def get_position_entry(entry_id: int) -> dict:
    return QuantPositionJournal.get_by_id(entry_id).to_dict()


def create_position_entry(
    *,
    symbol: str,
    side: str,
    quantity,
    occurred_at,
    created_by: str,
    strategy_id=None,
    run_id=None,
    operation_id=None,
    price=None,
    source: str = "manual",
    reason: str = "",
    remark: str = "",
) -> dict:
    normalized_quantity = _to_int(quantity, default=0) or 0
    if normalized_quantity <= 0:
        raise ValueError("quantity 必须大于 0")
    record = QuantPositionJournal.create(
        strategy_id=_to_int(strategy_id),
        run_id=_to_int(run_id),
        operation_id=_to_int(operation_id),
        symbol=normalize_symbol(symbol),
        side=_normalize_side(side),
        price=_to_float(price),
        quantity=normalized_quantity,
        occurred_at=_parse_occurred_at(occurred_at),
        source=str(source or "manual").strip() or "manual",
        reason=str(reason or "").strip(),
        remark=str(remark or "").strip(),
        created_by=str(created_by or "").strip(),
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    return record.to_dict()


def update_position_entry(entry_id: int, **updates) -> dict:
    record = QuantPositionJournal.get_by_id(entry_id)
    if "strategy_id" in updates:
        record.strategy_id = _to_int(updates["strategy_id"])
    if "run_id" in updates:
        record.run_id = _to_int(updates["run_id"])
    if "operation_id" in updates:
        record.operation_id = _to_int(updates["operation_id"])
    if "symbol" in updates:
        record.symbol = normalize_symbol(updates["symbol"])
    if "side" in updates:
        record.side = _normalize_side(updates["side"])
    if "price" in updates:
        record.price = _to_float(updates["price"])
    if "quantity" in updates:
        normalized_quantity = _to_int(updates["quantity"], default=0) or 0
        if normalized_quantity <= 0:
            raise ValueError("quantity 必须大于 0")
        record.quantity = normalized_quantity
    if "occurred_at" in updates:
        record.occurred_at = _parse_occurred_at(updates["occurred_at"])
    if "source" in updates:
        record.source = str(updates["source"] or "manual").strip() or "manual"
    if "reason" in updates:
        record.reason = str(updates["reason"] or "").strip()
    if "remark" in updates:
        record.remark = str(updates["remark"] or "").strip()
    record.updated_at = datetime.now()
    record.save()
    return record.to_dict()


def delete_position_entry(entry_id: int) -> bool:
    record = QuantPositionJournal.get_by_id(entry_id)
    record.delete_instance()
    return True


def list_position_summary(strategy_id: Optional[int] = None) -> list[dict]:
    entries = list_position_journal(strategy_id=strategy_id, limit=5000)
    positions = {}
    for item in sorted(entries, key=lambda row: row.get("occurred_at") or ""):
        symbol = item["symbol"]
        quantity = int(item.get("quantity") or 0)
        price = float(item["price"]) if item.get("price") is not None else None
        side = item.get("side") or "buy"
        signed_qty = _signed_quantity(side, quantity)
        bucket = positions.setdefault(
            symbol,
            {
                "symbol": symbol,
                "strategy_id": item.get("strategy_id"),
                "net_quantity": 0,
                "cost_amount": 0.0,
                "avg_cost": None,
                "latest_price": None,
                "market_value": None,
                "unrealized_pnl": None,
                "unrealized_pnl_pct": None,
                "last_occurred_at": item.get("occurred_at"),
                "last_side": side,
                "sources": set(),
            },
        )
        bucket["net_quantity"] += signed_qty
        bucket["last_occurred_at"] = item.get("occurred_at")
        bucket["last_side"] = side
        if item.get("source"):
            bucket["sources"].add(item["source"])
        if price is not None:
            bucket["cost_amount"] += price * signed_qty
        if bucket["net_quantity"] > 0 and bucket["cost_amount"] > 0:
            bucket["avg_cost"] = round(bucket["cost_amount"] / bucket["net_quantity"], 4)

    summary = []
    for symbol, bucket in positions.items():
        if bucket["net_quantity"] <= 0:
            continue
        latest_bar = (
            QuantDailyBar.select()
            .where(QuantDailyBar.symbol == symbol)
            .order_by(QuantDailyBar.trade_date.desc())
            .first()
        )
        latest_price = latest_bar.close_price if latest_bar else None
        bucket["latest_price"] = latest_price
        if latest_price is not None:
            bucket["market_value"] = round(float(latest_price) * bucket["net_quantity"], 4)
        if latest_price is not None and bucket["avg_cost"] is not None:
            pnl = (float(latest_price) - bucket["avg_cost"]) * bucket["net_quantity"]
            bucket["unrealized_pnl"] = round(pnl, 4)
            cost_base = bucket["avg_cost"] * bucket["net_quantity"]
            bucket["unrealized_pnl_pct"] = round(pnl / cost_base, 6) if cost_base else None
        bucket["sources"] = sorted(bucket["sources"])
        summary.append(bucket)
    summary.sort(key=lambda item: (item["market_value"] or 0), reverse=True)
    return summary
