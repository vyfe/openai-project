from __future__ import annotations

import gzip
import json
import os
import uuid
from datetime import datetime

from quant_client.constants import DATASET_BY_FREQUENCY, SUPPORTED_DATASET
from quant_client.provider_factory import get_provider


def build_fetch_bundle(
    provider_name: str,
    symbols: list[str],
    start_date: str,
    end_date: str,
    adjust_flag: str,
    frequency: str = "1d",
    interval: str = "5m",
) -> dict:
    """按 frequency 分发：1d 走 fetch_daily_bars；非 1d 走 fetch_minute_bars。

    frequency 与 interval 必须配套：frequency=5m 时 interval 仅作为 provider 内部换算 frequency 编码的元数据。
    """
    if frequency not in DATASET_BY_FREQUENCY:
        raise ValueError(f"不支持的 frequency: {frequency}")
    provider = get_provider(provider_name)

    if frequency == "1d":
        records = provider.fetch_daily_bars(
            symbols=symbols, start_date=start_date, end_date=end_date, adjust_flag=adjust_flag,
        )
    else:
        if not hasattr(provider, "fetch_minute_bars"):
            raise RuntimeError(
                f"数据源 {provider_name} 不支持分时 K 线，请使用 baostock/eastmoney/sina 或 auto"
            )
        records = provider.fetch_minute_bars(
            symbols=symbols, interval=interval,
            start_dt=start_date, end_dt=end_date, adjust_flag=adjust_flag,
        )

    batch_id = uuid.uuid4().hex
    actual_source = provider.provider_name
    if records:
        actual_source = str(records[0].get("source") or provider.provider_name)
    return {
        "dataset": DATASET_BY_FREQUENCY[frequency],
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
            "frequency": frequency,
            "interval": interval,
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

