import json
import logging
import re
from datetime import datetime

import sqlitelog
from flask import Blueprint, request
from peewee import DoesNotExist, IntegrityError

from conf.runtime import runtime_state
from dto.common import build_page_result, error_response, get_request_data, parse_pagination_args, success_response, to_bool
from model.db import db
from model.entities import ModelMeta, Notification, SystemPrompt, TestLimit, User
from model.repositories.user_repository import get_active_notifications
from routes._crud_factory import crud_create, crud_delete, crud_get, crud_list, crud_update
from service.auth_service import require_admin_auth
from service.model_service import get_runtime_state_snapshot, invalidate_model_cache


admin_bp = Blueprint("admin_routes", __name__, url_prefix="/never_guess_my_usage")
llm_logger = logging.getLogger("llm.web")
_SQL_TYPE_PATTERN = re.compile(r"^\s*([a-zA-Z]+)")
_SQL_TARGET_PATTERN = re.compile(r"\b(?:from|into|update|table)\s+[`\"]?([a-zA-Z0-9_]+)", re.IGNORECASE)


# ---------------------------------------------------------------------------
# 序列化器
# ---------------------------------------------------------------------------

def test_limit_to_dict(limit):
    return {"id": limit.id, "user_ip": limit.user_ip, "user_count": limit.user_count, "limit": limit.limit}


def user_to_dict(user):
    api_key = user.api_key or ""
    api_key_masked = "-"
    if api_key:
        api_key_masked = api_key if len(api_key) <= 8 else f"{api_key[:4]}****{api_key[-4:]}"
    return {
        "id": user.id,
        "username": user.username,
        "api_key_masked": api_key_masked,
        "role": user.role,
        "is_active": user.is_active,
        "created_at": user.created_at.strftime("%Y-%m-%d %H:%M:%S") if user.created_at else None,
        "updated_at": user.updated_at.strftime("%Y-%m-%d %H:%M:%S") if user.updated_at else None,
    }


def user_to_detail_dict(user):
    data = user_to_dict(user)
    data["api_key"] = user.api_key
    return data


def notification_to_dict(notification):
    return {
        "id": notification.id,
        "title": notification.title,
        "content": notification.content,
        "publish_time": notification.publish_time.strftime("%Y-%m-%d %H:%M:%S") if notification.publish_time else None,
        "status": notification.status,
        "priority": notification.priority,
        "created_at": notification.created_at.strftime("%Y-%m-%d %H:%M:%S") if notification.created_at else None,
        "updated_at": notification.updated_at.strftime("%Y-%m-%d %H:%M:%S") if notification.updated_at else None,
    }


def _summarize_sql(sql: str, params) -> str:
    statement_match = _SQL_TYPE_PATTERN.search(sql or "")
    target_match = _SQL_TARGET_PATTERN.search(sql or "")
    statement = statement_match.group(1).lower() if statement_match else "unknown"
    target = target_match.group(1) if target_match else "unknown"
    params_count = len(params) if isinstance(params, (list, tuple)) else (1 if params else 0)
    return f"statement={statement} target={target} params_count={params_count}"


# ---------------------------------------------------------------------------
# model_meta（特殊：custom search fields, batch_update）— 保留原始端点
# ---------------------------------------------------------------------------

@admin_bp.route("/model_meta/list", methods=["GET"])
@require_admin_auth
def model_meta_list():
    try:
        page, page_size, offset = parse_pagination_args(default_page_size=50)
        keyword = (request.args.get("keyword") or "").strip()
        recommend = request.args.get("recommend")
        status_valid = request.args.get("status_valid")
        if recommend is not None:
            recommend = to_bool(recommend)
        if status_valid is not None:
            status_valid = to_bool(status_valid)
        query = ModelMeta.select()
        if recommend is not None:
            query = query.where(ModelMeta.recommend == recommend)
        if status_valid is not None:
            query = query.where(ModelMeta.status_valid == status_valid)
        if keyword:
            query = query.where(
                (ModelMeta.model_name.contains(keyword))
                | (ModelMeta.model_desc.contains(keyword))
                | (ModelMeta.model_grp.contains(keyword))
            )
        total = query.count()
        query = query.order_by(ModelMeta.id.desc()).offset(offset).limit(page_size)
        models = [m.to_dict() for m in query.iterator()]
        return success_response(data=build_page_result(models, total, page, page_size))
    except Exception as exc:
        return error_response(f"获取模型列表失败: {exc}")


@admin_bp.route("/model_meta/get/<int:model_id>", methods=["GET"])
@require_admin_auth
def model_meta_get(model_id):
    try:
        return success_response(data=ModelMeta.get_by_id(model_id).to_dict())
    except DoesNotExist:
        return error_response("模型不存在")
    except Exception as exc:
        return error_response(f"获取模型失败: {exc}")


@admin_bp.route("/model_meta/create", methods=["POST"])
@require_admin_auth
def model_meta_create():
    try:
        data = get_request_data()
        model_name = data.get("model_name", "").strip()
        if not model_name:
            return error_response("模型名称不能为空")
        model = ModelMeta.create(
            model_name=model_name,
            model_desc=data.get("model_desc", ""),
            model_grp=data.get("model_grp", ""),
            model_type=int(data.get("model_type", 1)),
            recommend=to_bool(data.get("recommend", "false")),
            allow_net=to_bool(data.get("allow_net", "true")),
            status_valid=to_bool(data.get("status_valid", "true")),
        )
        invalidate_model_cache(reason="admin_create", logger=llm_logger)
        return success_response(data=model.to_dict(), msg="模型创建成功")
    except IntegrityError:
        return error_response("该模型名称已存在")
    except Exception as exc:
        return error_response(f"创建模型失败: {exc}")


@admin_bp.route("/model_meta/update", methods=["POST"])
@require_admin_auth
def model_meta_update():
    try:
        data = get_request_data()
        model_id = data.get("id")
        if not model_id:
            return error_response("模型ID不能为空")
        model = ModelMeta.get_by_id(int(model_id))
        for field in ("model_name", "model_desc", "model_grp"):
            if field in data:
                setattr(model, field, data[field].strip() if isinstance(data[field], str) else data[field])
        if "model_type" in data:
            model.model_type = int(data["model_type"])
        for bool_field in ("recommend", "allow_net", "status_valid"):
            if bool_field in data:
                setattr(model, bool_field, to_bool(data[bool_field]))
        model.save()
        invalidate_model_cache(reason="admin_update", logger=llm_logger)
        return success_response(data=model.to_dict(), msg="模型更新成功")
    except DoesNotExist:
        return error_response("模型不存在")
    except IntegrityError:
        return error_response("该模型名称已存在")
    except Exception as exc:
        return error_response(f"更新模型失败: {exc}")


@admin_bp.route("/model_meta/batch_update", methods=["POST"])
@require_admin_auth
def model_meta_batch_update():
    try:
        data = get_request_data()
        ids = data.get("ids") or []
        if not isinstance(ids, list) or not ids:
            return error_response("请提供要更新的模型ID列表")
        update_kwargs = {}
        if "recommend" in data:
            update_kwargs["recommend"] = to_bool(data["recommend"])
        if "allow_net" in data:
            update_kwargs["allow_net"] = to_bool(data["allow_net"])
        if "status_valid" in data:
            update_kwargs["status_valid"] = to_bool(data["status_valid"])
        if "model_grp" in data:
            update_kwargs["model_grp"] = str(data["model_grp"]).strip()
        if not update_kwargs:
            return error_response("没有要更新的字段")
        updated_count = ModelMeta.update(**update_kwargs).where(ModelMeta.id.in_(ids)).execute()
        invalidate_model_cache(reason="admin_batch_update", logger=llm_logger)
        return success_response(data={"updated_count": updated_count}, msg=f"成功更新 {updated_count} 条模型记录")
    except Exception as exc:
        return error_response(f"批量更新模型失败: {exc}")


@admin_bp.route("/model_meta/delete", methods=["POST"])
@require_admin_auth
def model_meta_delete():
    try:
        data = get_request_data()
        model_id = data.get("id")
        if not model_id:
            return error_response("模型ID不能为空")
        model = ModelMeta.get_by_id(int(model_id))
        model.delete_instance()
        invalidate_model_cache(reason="admin_delete", logger=llm_logger)
        return success_response(msg="模型删除成功")
    except DoesNotExist:
        return error_response("模型不存在")
    except Exception as exc:
        return error_response(f"删除模型失败: {exc}")


# ---------------------------------------------------------------------------
# system_prompt（用 crud_* 装饰器）
# ---------------------------------------------------------------------------

@admin_bp.route("/system_prompt/list", methods=["GET"])
@require_admin_auth
@crud_list(
    SystemPrompt,
    serializer=lambda p: dict(p),
    search_fields=["role_name", "role_group", "role_desc"],
    default_page_size=30,
)
def system_prompt_list():
    pass


@admin_bp.route("/system_prompt/get/<int:prompt_id>", methods=["GET"])
@require_admin_auth
@crud_get(SystemPrompt, serializer=lambda p: dict(p), id_param="prompt_id")
def system_prompt_get(prompt_id):
    pass


@admin_bp.route("/system_prompt/create", methods=["POST"])
@require_admin_auth
@crud_create(
    SystemPrompt,
    serializer=lambda p: dict(p),
    required=["role_name", "role_group"],
    field_map={"role_name": str, "role_group": str, "role_desc": str, "role_content": str, "status_valid": bool},
    integrity_msg="该角色名称和分组组合已存在",
)
def system_prompt_create():
    pass


@admin_bp.route("/system_prompt/update", methods=["POST"])
@require_admin_auth
@crud_update(
    SystemPrompt,
    serializer=lambda p: dict(p),
    field_map={"role_name": str, "role_group": str, "role_desc": str, "role_content": str, "status_valid": bool},
    integrity_msg="该角色名称和分组组合已存在",
)
def system_prompt_update():
    pass


@admin_bp.route("/system_prompt/delete", methods=["POST"])
@require_admin_auth
@crud_delete(SystemPrompt)
def system_prompt_delete():
    pass


# ---------------------------------------------------------------------------
# test_limit（用 crud_* 装饰器）+ reset 特殊端点
# ---------------------------------------------------------------------------

@admin_bp.route("/test_limit/list", methods=["GET"])
@require_admin_auth
@crud_list(TestLimit, serializer=test_limit_to_dict, search_fields=["user_ip"], default_page_size=50)
def test_limit_list():
    pass


@admin_bp.route("/test_limit/get/<int:limit_id>", methods=["GET"])
@require_admin_auth
@crud_get(TestLimit, serializer=test_limit_to_dict, id_param="limit_id", not_found_msg="测试限制不存在")
def test_limit_get(limit_id):
    pass


@admin_bp.route("/test_limit/create", methods=["POST"])
@require_admin_auth
@crud_create(
    TestLimit,
    serializer=test_limit_to_dict,
    required=["user_ip"],
    field_map={"user_ip": str, "user_count": int, "limit": int},
    integrity_msg="该IP已存在限制记录",
)
def test_limit_create():
    pass


@admin_bp.route("/test_limit/update", methods=["POST"])
@require_admin_auth
@crud_update(
    TestLimit,
    serializer=test_limit_to_dict,
    field_map={"user_ip": str, "user_count": int, "limit": int},
    not_found_msg="测试限制不存在",
    integrity_msg="该IP已存在限制记录",
)
def test_limit_update():
    pass


@admin_bp.route("/test_limit/delete", methods=["POST"])
@require_admin_auth
@crud_delete(TestLimit, not_found_msg="测试限制不存在")
def test_limit_delete():
    pass


@admin_bp.route("/test_limit/reset", methods=["POST"])
@require_admin_auth
def test_limit_reset():
    try:
        data = get_request_data()
        limit_id = data.get("id")
        user_ip = data.get("user_ip")
        reset_all = to_bool(data.get("reset_all", "false"))
        if reset_all:
            updated_count = TestLimit.update(user_count=0).execute()
            return success_response(msg=f"成功重置 {updated_count} 条测试限制记录")
        if limit_id:
            test_limit = TestLimit.get_by_id(int(limit_id))
            test_limit.user_count = 0
            test_limit.save()
            return success_response(data=test_limit_to_dict(test_limit), msg="测试限制重置成功")
        if user_ip:
            updated_count = TestLimit.update(user_count=0).where(TestLimit.user_ip == user_ip).execute()
            if updated_count > 0:
                return success_response(msg=f"成功重置IP {user_ip} 的测试限制")
            return error_response("未找到该IP的测试限制记录")
        return error_response("请提供ID、IP或设置reset_all=true")
    except DoesNotExist:
        return error_response("测试限制不存在")
    except Exception as exc:
        return error_response(f"重置测试限制失败: {exc}")


# ---------------------------------------------------------------------------
# user（保留原始端点 — create 走 sqlitelog.create_user，delete 支持 hard_delete）
# ---------------------------------------------------------------------------

@admin_bp.route("/user/list", methods=["GET"])
@require_admin_auth
@crud_list(User, serializer=user_to_dict, search_fields=["username"], default_page_size=50,
           filters={"role": (User.role, str), "is_active": (User.is_active, bool)})
def user_list():
    pass


@admin_bp.route("/user/get/<int:user_id>", methods=["GET"])
@require_admin_auth
@crud_get(User, serializer=user_to_detail_dict, id_param="user_id", not_found_msg="用户不存在")
def user_get(user_id):
    pass


@admin_bp.route("/user/create", methods=["POST"])
@require_admin_auth
def user_create():
    try:
        data = get_request_data()
        username = data.get("username", "").strip()
        new_password = data.get("new_password", "").strip()
        if not username or not new_password:
            return error_response("用户名和新密码不能为空")
        if User.select().where(User.username == username).exists():
            return error_response("用户名已存在")
        user = sqlitelog.create_user(username, new_password, data.get("api_key", "").strip() or None)
        if "role" in data:
            user.role = data["role"]
        if "is_active" in data:
            user.is_active = to_bool(data["is_active"])
        user.save()
        return success_response(data=user_to_dict(user), msg="用户创建成功")
    except Exception as exc:
        return error_response(f"创建用户失败: {exc}")


@admin_bp.route("/user/update", methods=["POST"])
@require_admin_auth
def user_update():
    try:
        data = get_request_data()
        user_id = data.get("id")
        if not user_id:
            return error_response("用户ID不能为空")
        user = User.get_by_id(int(user_id))
        if "username" in data:
            new_username = data["username"].strip()
            if new_username != user.username:
                if User.select().where(User.username == new_username).exists():
                    return error_response("用户名已存在")
                user.username = new_username
        if "role" in data:
            user.role = data["role"]
        if "is_active" in data:
            user.is_active = to_bool(data["is_active"])
        if "api_key" in data:
            user.api_key = data["api_key"].strip() or None
        if "new_password" in data and data["new_password"].strip():
            user.password_hash, user.salt = User.hash_password(data["new_password"].strip())
        user.updated_at = datetime.now()
        user.save()
        return success_response(data=user_to_dict(user), msg="用户信息更新成功")
    except DoesNotExist:
        return error_response("用户不存在")
    except Exception as exc:
        return error_response(f"更新用户信息失败: {exc}")


@admin_bp.route("/user/delete", methods=["POST"])
@require_admin_auth
def user_delete():
    try:
        data = get_request_data()
        user_id = data.get("id")
        if not user_id:
            return error_response("用户ID不能为空")
        hard_delete_value = data.get("hard_delete", "false")
        hard_delete = hard_delete_value if isinstance(hard_delete_value, bool) else str(hard_delete_value).lower() in ("true", "1", "yes")
        user = User.get_by_id(int(user_id))
        if hard_delete:
            user.token = None
            user.delete_instance()
            return success_response(msg="用户永久删除成功")
        user.is_active = False
        user.token = None
        user.updated_at = datetime.now()
        user.save()
        return success_response(msg="用户已标记为未激活")
    except DoesNotExist:
        return error_response("用户不存在")
    except Exception as exc:
        return error_response(f"删除用户失败: {exc}")


# ---------------------------------------------------------------------------
# notification（保留原始端点 — create/update 走 sqlitelog 特殊路径）
# ---------------------------------------------------------------------------

@admin_bp.route("/notification/list", methods=["GET"])
@require_admin_auth
@crud_list(
    Notification,
    serializer=notification_to_dict,
    search_fields=["title", "content"],
    default_page_size=20,
    filters={"status": (Notification.status, str)},
    order_by=Notification.priority.desc(),
)
def notification_list():
    pass


@admin_bp.route("/notification/active_list", methods=["GET"])
def notification_active_list():
    try:
        limit = request.args.get("limit", 10, type=int)
        return success_response(data=get_active_notifications(limit=limit))
    except Exception as exc:
        return error_response(f"获取有效通知列表失败: {exc}")


@admin_bp.route("/notification/get/<int:notification_id>", methods=["GET"])
@require_admin_auth
@crud_get(Notification, serializer=notification_to_dict, id_param="notification_id", not_found_msg="通知不存在")
def notification_get(notification_id):
    pass


@admin_bp.route("/notification/create", methods=["POST"])
@require_admin_auth
def notification_create():
    try:
        data = get_request_data()
        title = data.get("title", "").strip()
        content = data.get("content", "").strip()
        if not title or not content:
            return error_response("通知标题和内容不能为空")
        notification = sqlitelog.create_notification(
            title=title,
            content=content,
            priority=int(data.get("priority", 0)),
            status=data.get("status", "active").strip() if data.get("status", "active").strip() in ["active", "inactive"] else "active",
        )
        return success_response(data=notification_to_dict(notification), msg="通知创建成功")
    except Exception as exc:
        return error_response(f"创建通知失败: {exc}")


@admin_bp.route("/notification/update", methods=["POST"])
@require_admin_auth
def notification_update():
    try:
        data = get_request_data()
        notification_id = data.get("id")
        if not notification_id:
            return error_response("通知ID不能为空")
        update_fields = {}
        if "title" in data:
            update_fields["title"] = data["title"].strip()
        if "content" in data:
            update_fields["content"] = data["content"].strip()
        if "priority" in data:
            update_fields["priority"] = int(data["priority"])
        if "status" in data:
            status = data["status"].strip()
            if status not in ["active", "inactive"]:
                return error_response("状态必须是active或inactive")
            update_fields["status"] = status
        if not update_fields:
            return error_response("没有要更新的字段")
        success = sqlitelog.update_notification(int(notification_id), **update_fields)
        if success:
            return success_response(data=notification_to_dict(Notification.get_by_id(int(notification_id))), msg="通知更新成功")
        return error_response("通知不存在")
    except Exception as exc:
        return error_response(f"更新通知失败: {exc}")


@admin_bp.route("/notification/delete", methods=["POST"])
@require_admin_auth
def notification_delete():
    try:
        data = get_request_data()
        notification_id = data.get("id")
        if not notification_id:
            return error_response("通知ID不能为空")
        success = sqlitelog.delete_notification(int(notification_id))
        if success:
            return success_response(msg="通知删除成功")
        return error_response("通知不存在")
    except Exception as exc:
        return error_response(f"删除通知失败: {exc}")


# ---------------------------------------------------------------------------
# SQL 后门与运行时（保留原始端点）
# ---------------------------------------------------------------------------

@admin_bp.route("/sql_execute", methods=["POST"])
@require_admin_auth
def sql_execute():
    if not runtime_state.settings.enable_sql_execute:
        return error_response("SQL执行功能未启用")
    try:
        data = get_request_data()
        sql = data.get("sql", "").strip()
        params = data.get("params")
        if not sql:
            return error_response("SQL语句不能为空")
        if not (sql.lower().startswith("select") or sql.lower().startswith("pragma")):
            return error_response("仅允许 SELECT/PRAGMA 语句")
        summary = _summarize_sql(sql, params)
        llm_logger.warning(f"管理员执行SQL: {summary}")
        cursor = db.execute_sql(sql, params or ())
        if sql.lower().startswith("select"):
            columns = [d[0] for d in cursor.description]
            rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
            return success_response(data={"columns": columns, "rows": rows[:500], "summary": summary})
        return success_response(data={"summary": summary})
    except Exception as exc:
        return error_response(f"SQL执行失败: {exc}")


@admin_bp.route("/runtime/overview", methods=["GET"])
@require_admin_auth
def runtime_overview():
    try:
        snapshot = get_runtime_state_snapshot()
        return success_response(data=snapshot)
    except Exception as exc:
        return error_response(f"获取运行时总览失败: {exc}")


@admin_bp.route("/sql/meta", methods=["GET"])
@require_admin_auth
def sql_meta():
    try:
        cursor = db.execute_sql(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = [row[0] for row in cursor.fetchall()]
        return success_response(data={"tables": tables})
    except Exception as exc:
        return error_response(f"获取表元信息失败: {exc}")
