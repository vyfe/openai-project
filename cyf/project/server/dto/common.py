import json
from dataclasses import dataclass

from flask import request


def get_request_data(as_text: bool = False):
    content_type = request.content_type
    if content_type and "application/json" in content_type:
        json_data = request.get_json(silent=True)
        if json_data:
            if as_text:
                return {key: str(value) for key, value in json_data.items()}
            return json_data
        return request.values
    return request.values


def to_bool(value):
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).lower() in ("true", "1", "yes")


def parse_pagination_args(default_page_size: int = 20, max_page_size: int = 200):
    page = request.args.get("page", default=1, type=int) or 1
    page_size = request.args.get("page_size", default=default_page_size, type=int) or default_page_size
    page = 1 if page < 1 else page
    if page_size < 1:
        page_size = default_page_size
    if page_size > max_page_size:
        page_size = max_page_size
    offset = (page - 1) * page_size
    return page, page_size, offset


def build_page_result(items, total, page, page_size):
    pages = (total + page_size - 1) // page_size if total > 0 else 1
    return {
        "items": items,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "pages": pages,
        },
    }


def success_response(data=None, msg=None):
    return {"success": True, "data": data, "msg": msg or "操作成功"}


def error_response(msg):
    return {"success": False, "msg": msg}


def parse_json_list(raw_value, default=None):
    if raw_value is None:
        return default if default is not None else []
    if isinstance(raw_value, list):
        return raw_value
    try:
        return json.loads(raw_value)
    except Exception:
        return default if default is not None else []
