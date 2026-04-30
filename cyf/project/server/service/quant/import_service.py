from __future__ import annotations

import gzip
import hashlib
import json
import os
import uuid
from datetime import datetime
from typing import Optional

from quant.db import quant_db
from quant.entities import QuantDailyBar, QuantImportBatch, QuantInstrument
from quant_client.constants import SUPPORTED_DATASET
from service.quant.common import infer_exchange, normalize_code, normalize_symbol, parse_trade_date, to_float


def ensure_quant_runtime_dirs(bundle_dir: str):
    os.makedirs(bundle_dir, exist_ok=True)


def parse_bundle_bytes(file_bytes: bytes) -> dict:
    if file_bytes[:2] == b"\x1f\x8b":
        file_bytes = gzip.decompress(file_bytes)
    return json.loads(file_bytes.decode("utf-8"))


def normalize_bundle(bundle: dict) -> dict:
    dataset = str(bundle.get("dataset") or "").strip()
    if dataset != SUPPORTED_DATASET:
        raise ValueError(f"不支持的数据集类型: {dataset}")

    records = bundle.get("records")
    if not isinstance(records, list) or not records:
        raise ValueError("records 不能为空")

    batch_id = str(bundle.get("batch_id") or uuid.uuid4().hex)
    source = str(bundle.get("source") or "").strip().lower()
    if not source:
        raise ValueError("source 不能为空")

    normalized_records = []
    for item in records:
        code = normalize_code(item.get("code") or item.get("symbol"))
        exchange = str(item.get("exchange") or infer_exchange(code)).upper()
        normalized_records.append(
            {
                "symbol": normalize_symbol(item.get("symbol") or code),
                "code": code,
                "exchange": exchange,
                "trade_date": parse_trade_date(item.get("trade_date")),
                "adjust_flag": str(item.get("adjust_flag") or "qfq"),
                "open_price": to_float(item.get("open_price")),
                "high_price": to_float(item.get("high_price")),
                "low_price": to_float(item.get("low_price")),
                "close_price": to_float(item.get("close_price")),
                "preclose_price": to_float(item.get("preclose_price")),
                "volume": to_float(item.get("volume")),
                "amount": to_float(item.get("amount")),
                "turnover_rate": to_float(item.get("turnover_rate")),
                "pct_change": to_float(item.get("pct_change")),
                "source": source,
                "source_run_id": str(bundle.get("source_run_id") or batch_id),
                "data_source_version": str(item.get("data_source_version") or bundle.get("data_source_version") or ""),
            }
        )

    return {
        "dataset": dataset,
        "batch_id": batch_id,
        "source": source,
        "source_run_id": str(bundle.get("source_run_id") or batch_id),
        "records": normalized_records,
    }


def _chunked(items: list[dict], size: int = 500):
    for index in range(0, len(items), size):
        yield items[index:index + size]


def import_bundle(bundle: dict, file_name: str = "", payload_bytes: Optional[bytes] = None) -> dict:
    normalized = normalize_bundle(bundle)
    payload_sha256 = hashlib.sha256(payload_bytes or json.dumps(bundle, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    now = datetime.now()

    existing = QuantImportBatch.get_or_none(QuantImportBatch.batch_id == normalized["batch_id"])
    if existing:
        return existing.to_dict()

    batch = QuantImportBatch.create(
        batch_id=normalized["batch_id"],
        dataset=normalized["dataset"],
        source=normalized["source"],
        source_run_id=normalized["source_run_id"],
        file_name=file_name,
        payload_sha256=payload_sha256,
        status="running",
        records_total=len(normalized["records"]),
        created_at=now,
    )

    try:
        instrument_rows = {}
        bar_rows = []
        for item in normalized["records"]:
            instrument_rows[item["symbol"]] = {
                "symbol": item["symbol"],
                "code": item["code"],
                "exchange": item["exchange"],
                "market": "A_SHARE",
                "name": "",
                "source": item["source"],
                "status": "active",
                "created_at": now,
                "updated_at": now,
            }
            row = dict(item)
            row["created_at"] = now
            row["updated_at"] = now
            bar_rows.append(row)

        with quant_db.atomic():
            for chunk in _chunked(list(instrument_rows.values())):
                QuantInstrument.insert_many(chunk).on_conflict_replace().execute()
            for chunk in _chunked(bar_rows):
                QuantDailyBar.insert_many(chunk).on_conflict_replace().execute()

        batch.status = "success"
        batch.records_imported = len(bar_rows)
        batch.finished_at = datetime.now()
        batch.message = "导入完成"
        batch.save()
        return batch.to_dict()
    except Exception as exc:
        batch.status = "failed"
        batch.finished_at = datetime.now()
        batch.message = str(exc)
        batch.save()
        raise


def fetch_import_batches(limit: int = 20):
    query = QuantImportBatch.select().order_by(QuantImportBatch.id.desc()).limit(limit)
    return [item.to_dict() for item in query.iterator()]
