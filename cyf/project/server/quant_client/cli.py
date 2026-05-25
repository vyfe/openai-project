#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import logging
from typing import List

from quant_client.bundle_builder import build_fetch_bundle, write_bundle
from quant_client.constants import DEFAULT_TASK_TYPE
from quant_client.http_client import QuantTaskClient
from quant_client.provider_factory import list_supported_providers

logger = logging.getLogger("quant.client")


def _read_symbols(args) -> List[str]:
    symbols: List[str] = []
    if args.symbols:
        symbols.extend([item.strip() for item in args.symbols.split(",") if item.strip()])
    if args.symbols_file:
        with open(args.symbols_file, "r", encoding="utf-8") as fp:
            for line in fp:
                line = line.strip()
                if line and not line.startswith("#"):
                    symbols.append(line)
    deduped = []
    seen = set()
    for item in symbols:
        if item not in seen:
            seen.add(item)
            deduped.append(item)
    return deduped


def _build_client(args) -> QuantTaskClient:
    return QuantTaskClient(
        base_url=args.server_url,
        token=getattr(args, "token", "") or "",
        user=getattr(args, "user", "") or "",
        password=getattr(args, "password", "") or "",
        timeout=getattr(args, "timeout", 60) or 60,
    )


def cmd_providers(_args):
    logger.info("list providers")
    print(json.dumps({"providers": list_supported_providers()}, ensure_ascii=False, indent=2))


def cmd_fetch_bars(args):
    symbols = _read_symbols(args)
    if not symbols:
        raise SystemExit("请通过 --symbols 或 --symbols-file 提供至少一个 symbol")
    logger.info(
        "fetch bars provider=%s symbols=%s start=%s end=%s adjust=%s",
        args.provider,
        len(symbols),
        args.start_date,
        args.end_date,
        args.adjust_flag,
    )
    bundle = build_fetch_bundle(
        provider_name=args.provider,
        symbols=symbols,
        start_date=args.start_date,
        end_date=args.end_date,
        adjust_flag=args.adjust_flag,
    )
    if args.output:
        write_bundle(args.output, bundle)
        print(json.dumps({"success": True, "output": args.output, "records": len(bundle["records"])}, ensure_ascii=False, indent=2))
        return
    print(json.dumps(bundle, ensure_ascii=False, indent=2))


def cmd_claim_task(args):
    client = _build_client(args)
    logger.info("claim task client_id=%s", args.client_id)
    result = client.claim_task(client_id=args.client_id, capabilities=list_supported_providers())
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_run_once(args):
    client = _build_client(args)
    logger.info("run_once claim client_id=%s", args.client_id)
    claim_result = client.claim_task(client_id=args.client_id, capabilities=list_supported_providers())
    task = (claim_result or {}).get("data")
    if not task:
        logger.info("run_once no task client_id=%s", args.client_id)
        print(json.dumps({"success": True, "message": "no task"}, ensure_ascii=False, indent=2))
        return

    task_id = task["task_id"]
    payload = task.get("payload") or {}
    task_type = task.get("task_type")
    if task_type != DEFAULT_TASK_TYPE:
        logger.warning("unsupported task type client_id=%s task_id=%s task_type=%s", args.client_id, task_id, task_type)
        result = client.report_task_failure(args.client_id, task_id, f"不支持的任务类型: {task_type}")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    try:
        logger.info("execute task client_id=%s task_id=%s task_type=%s", args.client_id, task_id, task_type)
        bundle = build_fetch_bundle(
            provider_name=str(payload.get("provider") or "auto"),
            symbols=payload.get("symbols") or [],
            start_date=str(payload.get("start_date") or ""),
            end_date=str(payload.get("end_date") or ""),
            adjust_flag=str(payload.get("adjust_flag") or "qfq"),
        )
        result = client.report_task_success(args.client_id, task_id, bundle, message="采集并上报成功")
        logger.info("task success client_id=%s task_id=%s records=%s", args.client_id, task_id, len(bundle.get("records") or []))
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as exc:
        logger.exception("task failure client_id=%s task_id=%s", args.client_id, task_id)
        result = client.report_task_failure(args.client_id, task_id, str(exc))
        print(json.dumps(result, ensure_ascii=False, indent=2))


def build_parser():
    parser = argparse.ArgumentParser(description="独立量化采集客户端，可打包为 Windows/macOS 二进制")
    subparsers = parser.add_subparsers(dest="command", required=True)

    providers_parser = subparsers.add_parser("providers", help="列出支持的数据源")
    providers_parser.set_defaults(func=cmd_providers)

    fetch_parser = subparsers.add_parser("fetch-bars", help="抓取 A 股日线并输出 bundle")
    fetch_parser.add_argument("--provider", choices=list_supported_providers(), required=True, help="数据源")
    fetch_parser.add_argument("--symbols", help="逗号分隔的 symbol，例如 600519,000001.SZ")
    fetch_parser.add_argument("--symbols-file", help="symbol 文件，每行一个")
    fetch_parser.add_argument("--start-date", required=True, help="开始日期，YYYY-MM-DD")
    fetch_parser.add_argument("--end-date", required=True, help="结束日期，YYYY-MM-DD")
    fetch_parser.add_argument("--adjust-flag", default="qfq", choices=["qfq", "hfq", "raw"], help="复权类型")
    fetch_parser.add_argument("--output", help="输出路径，支持 .json 或 .json.gz")
    fetch_parser.set_defaults(func=cmd_fetch_bars)

    claim_parser = subparsers.add_parser("claim-task", help="向服务端认领一个任务")
    claim_parser.add_argument("--server-url", required=True, help="服务端地址，例如 http://localhost:39997")
    claim_parser.add_argument("--client-id", required=True, help="客户端标识")
    claim_parser.add_argument("--token", help="Bearer token")
    claim_parser.add_argument("--user", help="用户名")
    claim_parser.add_argument("--password", help="密码")
    claim_parser.add_argument("--timeout", type=int, default=60, help="请求超时秒数")
    claim_parser.set_defaults(func=cmd_claim_task)

    run_parser = subparsers.add_parser("run-once", help="认领一个任务并执行一次采集上报")
    run_parser.add_argument("--server-url", required=True, help="服务端地址，例如 http://localhost:39997")
    run_parser.add_argument("--client-id", required=True, help="客户端标识")
    run_parser.add_argument("--token", help="Bearer token")
    run_parser.add_argument("--user", help="用户名")
    run_parser.add_argument("--password", help="密码")
    run_parser.add_argument("--timeout", type=int, default=60, help="请求超时秒数")
    run_parser.set_defaults(func=cmd_run_once)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
