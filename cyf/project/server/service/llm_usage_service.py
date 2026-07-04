from typing import Any, Dict


def normalize_usage(raw_usage: Any) -> Dict[str, int]:
    if raw_usage is None:
        return {"total_tokens": 0}

    if isinstance(raw_usage, dict):
        prompt_tokens = int(raw_usage.get("prompt_tokens") or raw_usage.get("input_tokens") or 0)
        completion_tokens = int(raw_usage.get("completion_tokens") or raw_usage.get("output_tokens") or 0)
        total_tokens = int(raw_usage.get("total_tokens") or (prompt_tokens + completion_tokens) or 0)
    else:
        prompt_tokens = int(getattr(raw_usage, "prompt_tokens", None) or getattr(raw_usage, "input_tokens", None) or 0)
        completion_tokens = int(getattr(raw_usage, "completion_tokens", None) or getattr(raw_usage, "output_tokens", None) or 0)
        total_tokens = int(getattr(raw_usage, "total_tokens", None) or (prompt_tokens + completion_tokens) or 0)

    usage = {"total_tokens": total_tokens}
    if prompt_tokens:
        usage["prompt_tokens"] = prompt_tokens
    if completion_tokens:
        usage["completion_tokens"] = completion_tokens
    return usage


def estimate_total_tokens(text: str) -> Dict[str, int]:
    return {"total_tokens": max(0, len((text or "").encode("utf-8")) // 4)}
