"""CRUD 装饰器工厂：为 admin 资源统一 list/get/create/update/delete 五件套。

设计目标：
- 每个资源从 ~50 行/端点 × 5 端点 = ~250 行降到 ~10 行配置
- URL、参数、返回结构 100% 与重构前一致
- 支持字段白名单、过滤字段、必填字段、副作用钩子

使用示例（admin_routes.py 中）：
    @admin_bp.route("/test_limit/list", methods=["GET"])
    @crud_list(TestLimit, serializer=test_limit_to_dict,
               search_fields=["user_ip"], default_page_size=50)
    def test_limit_list(): ...

    @admin_bp.route("/test_limit/get/<int:limit_id>", methods=["GET"])
    @crud_get(TestLimit, serializer=test_limit_to_dict)
    def test_limit_get(limit_id): ...

    @admin_bp.route("/test_limit/create", methods=["POST"])
    @crud_create(TestLimit, serializer=test_limit_to_dict,
                 required=["user_ip"],
                 field_map={"user_ip": str, "user_count": int, "limit": int})
    def test_limit_create(): ...

    @admin_bp.route("/test_limit/update", methods=["POST"])
    @crud_update(TestLimit, serializer=test_limit_to_dict,
                 field_map={"user_ip": str, "user_count": int, "limit": int})
    def test_limit_update(): ...

    @admin_bp.route("/test_limit/delete", methods=["POST"])
    @crud_delete(TestLimit)
    def test_limit_delete(): ...
"""
from __future__ import annotations

from functools import wraps
from typing import Any, Callable

from flask import request
from peewee import DoesNotExist, IntegrityError

from dto.common import (
    build_page_result,
    error_response,
    get_request_data,
    parse_pagination_args,
    success_response,
    to_bool,
)


def _coerce(value: Any, caster: Callable[[Any], Any]) -> Any:
    """按 caster 类型转换 value；caster 不存在则原样返回。"""
    if value is None:
        return None
    return caster(value)


def crud_list(model, *, serializer, search_fields=None, filters=None,
              default_page_size=50, order_by=None, extra_query_filter=None):
    """通用 list 端点装饰器。

    Args:
        model: peewee Model
        serializer: 单条记录 → dict 的函数
        search_fields: 关键字搜索的字段名列表（OR contains）
        filters: 额外过滤 dict，键为查询参数名，值为 (field, caster)
                 例如 {"role_group": (SystemPrompt.role_group, str)}
        default_page_size: 默认每页
        order_by: 排序字段（默认按 id desc）
        extra_query_filter: 接收 query 后再修饰（注入更复杂的 where 条件）
    """
    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            try:
                page, page_size, offset = parse_pagination_args(default_page_size=default_page_size)
                keyword = (request.args.get("keyword") or "").strip()
                query = model.select()
                if search_fields and keyword:
                    from peewee import fn
                    clauses = [getattr(model, f).contains(keyword) for f in search_fields]
                    or_clause = clauses[0]
                    for c in clauses[1:]:
                        or_clause = or_clause | c
                    query = query.where(or_clause)
                if filters:
                    for arg_name, (field, caster) in filters.items():
                        value = request.args.get(arg_name)
                        if value is None or value == "":
                            continue
                        if caster is bool:
                            query = query.where(field == to_bool(value))
                        else:
                            query = query.where(field == caster(value))
                if extra_query_filter:
                    query = extra_query_filter(query, request.args)
                total = query.count()
                ob = order_by or model.id.desc()
                items = [serializer(item) for item in query.order_by(ob).offset(offset).limit(page_size).iterator()]
                return success_response(data=build_page_result(items, total, page, page_size))
            except Exception as exc:
                return error_response(f"获取{_label(model)}列表失败: {exc}")
        return wrapper
    return decorator


def crud_get(model, *, serializer, id_param="id", not_found_msg=None):
    """通用 get 端点装饰器。"""
    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            pk = kwargs.get(id_param)
            try:
                instance = model.get_by_id(int(pk)) if pk is not None else None
                return success_response(data=serializer(instance))
            except DoesNotExist:
                return error_response(not_found_msg or f"{_label(model)}不存在")
            except Exception as exc:
                return error_response(f"获取{_label(model)}失败: {exc}")
        return wrapper
    return decorator


def crud_create(model, *, serializer, required=None, field_map=None,
                on_create=None, not_found_msg=None, integrity_msg=None):
    """通用 create 端点装饰器。

    Args:
        required: 必填字段名列表（自动 trim str）
        field_map: {字段名: caster} 例如 {"role_name": str, "status_valid": bool}
        on_create: 接 (instance, data) → msg 用于返回前执行副作用（如 sqlitelog.create_user 走特殊路径）
    """
    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            try:
                data = get_request_data()
                if required:
                    for field in required:
                        v = str(data.get(field, "")).strip()
                        if not v:
                            return error_response(f"{field}不能为空")
                kwargs_create = {}
                if field_map:
                    for field, caster in field_map.items():
                        if field not in data:
                            continue
                        kwargs_create[field] = _coerce(data[field], caster)
                instance = model.create(**kwargs_create)
                if on_create:
                    on_create(instance, data)
                    instance.save()
                return success_response(data=serializer(instance), msg=f"{_label(model)}创建成功")
            except IntegrityError:
                return error_response(integrity_msg or f"{_label(model)}已存在")
            except Exception as exc:
                return error_response(f"创建{_label(model)}失败: {exc}")
        return wrapper
    return decorator


def crud_update(model, *, serializer, field_map=None, id_field="id",
                not_found_msg=None, integrity_msg=None):
    """通用 update 端点装饰器。"""
    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            try:
                data = get_request_data()
                pk = data.get(id_field)
                if not pk:
                    return error_response(f"{_label(model)}ID不能为空")
                instance = model.get_by_id(int(pk))
                if field_map:
                    for field, caster in field_map.items():
                        if field not in data:
                            continue
                        if caster is bool:
                            setattr(instance, field, to_bool(data[field]))
                        else:
                            setattr(instance, field, _coerce(data[field], caster))
                instance.save()
                return success_response(data=serializer(instance), msg=f"{_label(model)}更新成功")
            except DoesNotExist:
                return error_response(not_found_msg or f"{_label(model)}不存在")
            except IntegrityError:
                return error_response(integrity_msg or f"{_label(model)}已存在")
            except Exception as exc:
                return error_response(f"更新{_label(model)}失败: {exc}")
        return wrapper
    return decorator


def crud_delete(model, *, id_field="id", not_found_msg=None):
    """通用 delete 端点装饰器。"""
    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            try:
                data = get_request_data()
                pk = data.get(id_field)
                if not pk:
                    return error_response(f"{_label(model)}ID不能为空")
                instance = model.get_by_id(int(pk))
                instance.delete_instance()
                return success_response(msg=f"{_label(model)}删除成功")
            except DoesNotExist:
                return error_response(not_found_msg or f"{_label(model)}不存在")
            except Exception as exc:
                return error_response(f"删除{_label(model)}失败: {exc}")
        return wrapper
    return decorator


def _label(model) -> str:
    """把 Model 类名转成中文友好的标签（默认简单 title-cased）。"""
    name = model.__name__
    # 去掉 'Quant'/'Model' 等冗余前缀
    for prefix in ("Quant", "Model"):
        if name.startswith(prefix):
            name = name[len(prefix):]
    return name
