import time
from datetime import datetime, timedelta

from conf.runtime import runtime_state
from model.repositories.model_meta_repository import get_model_meta_list
from model.repositories.user_repository import get_active_token_count
from service.host_service import random_client


def invalidate_model_cache(reason: str = "manual", logger=None):
    runtime_state.model_cache.pop("models", None)
    runtime_state.cache_expiry_time.pop("models", None)
    if logger:
        logger.info(f"模型缓存已失效，reason={reason}")


def filter_models(models_data, exclude_keywords=None):
    exclude_keywords = exclude_keywords or ["instruct", "realtime", "audio"]
    filtered_models = []
    for model in models_data:
        model_id = model.get("id", "")
        has_exclude_keyword = any(keyword.lower() in model_id.lower() for keyword in exclude_keywords)
        if not has_exclude_keyword:
            filtered_model = {"id": model_id.lower(), "label": model_id.lower()}
            for key, value in model.items():
                if key not in ["id", "label"] and key not in filtered_model:
                    filtered_model[key] = value
            filtered_models.append(filtered_model)
    return filtered_models


def get_cached_models(logger=None):
    current_time = time.time()
    if "models" in runtime_state.cache_expiry_time and current_time < runtime_state.cache_expiry_time["models"]:
        return runtime_state.model_cache.get("models", [])
    try:
        client, _ = random_client()
        models_response = client.models.list()
        filtered_models = filter_models(
            [model.model_dump() for model in models_response.data],
            runtime_state.settings.model_exclude_keywords,
        )
        model_ids = [m["id"] for m in filtered_models]
        model_meta_list = get_model_meta_list(model_names=model_ids)
        meta_map = {meta["model_name"].lower(): meta for meta in model_meta_list}
        meta_order_map = {meta["model_name"].lower(): int(meta.get("id") or 0) for meta in model_meta_list}
        enhanced_models = []
        for model in filtered_models:
            model_id = model["id"].lower()
            meta = meta_map.get(model_id)
            if meta and not meta.get("status_valid", True):
                continue
            model["recommend"] = meta.get("recommend", False) if meta else False
            model["allow_net"] = meta.get("allow_net", True) if meta else True
            model["model_desc"] = meta.get("model_desc", "") if meta else ""
            model["model_type"] = meta.get("model_type", 1) if meta else 1
            model["model_grp"] = meta.get("model_grp", "") if meta else ""
            enhanced_models.append(model)
        enhanced_models.sort(
            key=lambda m: (1 if m.get("recommend", False) else 0, meta_order_map.get(str(m.get("id", "")).lower(), 0)),
            reverse=True,
        )
        runtime_state.model_cache["models"] = enhanced_models
        runtime_state.cache_expiry_time["models"] = current_time + runtime_state.settings.model_cache_ttl
        return enhanced_models
    except Exception as exc:
        if logger:
            logger.error(f"获取模型列表失败: {exc}")
        return []


def is_valid_model(model_name):
    return model_name in [model["id"] for model in get_cached_models()]


def get_grouped_models(logger=None):
    try:
        grouped_models = {}
        for model in get_cached_models(logger=logger):
            model_grp = str(model.get("model_grp", "") or "").strip()
            if not model_grp:
                continue
            grouped_models.setdefault(model_grp, []).append(model)
        return grouped_models
    except Exception as exc:
        if logger:
            logger.error(f"获取分组模型列表失败: {exc}")
        return {}


def seconds_until_next(hour: int, minute: int = 0) -> int:
    now = datetime.now()
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return max(1, int((target - now).total_seconds()))


def get_runtime_state_snapshot() -> dict:
    now_ts = int(time.time())
    with runtime_state.blacklist_lock:
        blacklist_snapshot = dict(runtime_state.api_host_blacklist)
    host_status = []
    for idx, host in enumerate(runtime_state.settings.api_hosts):
        blacklisted_until = blacklist_snapshot.get(idx, 0)
        remaining = max(0, int(blacklisted_until - now_ts))
        host_status.append(
            {
                "index": idx,
                "host": host,
                "blacklisted": remaining > 0,
                "blacklist_remaining_seconds": remaining,
            }
        )
    model_cache_expire_ts = int(runtime_state.cache_expiry_time.get("models", 0) or 0)
    return {
        "uptime_seconds": max(0, int(now_ts - runtime_state.server_start_time)),
        "model_cache": {
            "cached": "models" in runtime_state.model_cache,
            "model_count": len(runtime_state.model_cache.get("models", [])) if isinstance(runtime_state.model_cache.get("models", []), list) else 0,
            "expires_at": model_cache_expire_ts,
            "expires_in_seconds": max(0, model_cache_expire_ts - now_ts) if model_cache_expire_ts else 0,
        },
        "api_hosts": host_status,
        "token_stats": {"active_token_count": get_active_token_count()},
    }
