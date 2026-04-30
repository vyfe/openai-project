from __future__ import annotations

import gzip
import json
import os
import uuid
from datetime import datetime

from quant_client.constants import SUPPORTED_DATASET
from quant_client.provider_factory import get_provider


def build_fetch_bundle(provider_name: str, symbols: list[str], start_date: str, end_date: str, adjust_flag: str) -> dict:
    provider = get_provider(provider_name)
    records = provider.fetch_daily_bars(symbols=symbols, start_date=start_date, end_date=end_date, adjust_flag=adjust_flag)
    batch_id = uuid.uuid4().hex
    actual_source = provider.provider_name
    if records:
        actual_source = str(records[0].get("source") or provider.provider_name)
    return {
        "dataset": SUPPORTED_DATASET,
        "bundle_version": 1,
        "batch_id": batch_id,
        "source": actual_source,
        "source_run_id": batch_id,
        "generated_at": datetime.now().isoformat(),
        "market": "A_SHARE",
        "provider_meta": {
            "provider_name": actual_source,
            "requested_provider": provider.provider_name,
            "provider_version": provider.provider_version,
            "adjust_flag": adjust_flag,
            "start_date": start_date,
            "end_date": end_date,
        },
        "records": records,
    }


def write_bundle(output_path: str, bundle: dict):
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    raw = json.dumps(bundle, ensure_ascii=False, indent=2).encode("utf-8")
    if output_path.endswith(".gz"):
        with gzip.open(output_path, "wb") as fp:
            fp.write(raw)
        return
    with open(output_path, "wb") as fp:
        fp.write(raw)


def bundle_to_gzip_bytes(bundle: dict) -> bytes:
    raw = json.dumps(bundle, ensure_ascii=False).encode("utf-8")
    return gzip.compress(raw)

