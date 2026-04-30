import json
from datetime import datetime

import sqlitelog
from flask import Blueprint, current_app, request
from peewee import DoesNotExist, IntegrityError

from conf.runtime import runtime_state
from dto.common import build_page_result, error_response, get_request_data, parse_pagination_args, success_response, to_bool
from model.db import db
from model.entities import ModelMeta, Notification, SystemPrompt, TestLimit, User
from model.repositories.user_repository import get_active_notifications
from service.auth_service import require_admin_auth
from service.model_service import get_runtime_state_snapshot, invalidate_model_cache


admin_bp = Blueprint("admin_routes", __name__, url_prefix="/never_guess_my_usage")


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
        model_type = int(data.get("model_type", "").strip())
        if not model_name:
            return error_response("模型名称不能为空")
        model = ModelMeta.create(
            model_name=model_name,
            model_desc=data.get("model_desc", ""),
            model_type=model_type,
            model_grp=data.get("model_grp", "").strip(),
            recommend=to_bool(data.get("recommend", "false")),
            status_valid=to_bool(data.get("status_valid", "true")),
        )
        invalidate_model_cache("model_meta_create", logger=current_app.logger)
        return success_response(data=model.to_dict(), msg="模型创建成功")
    except IntegrityError:
        return error_response("模型名称已存在")
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
        if "model_name" in data:
            model.model_name = data["model_name"].strip()
        if "model_desc" in data:
            model.model_desc = data["model_desc"]
        if "model_type" in data:
            model.model_type = int(data["model_type"])
        if "model_grp" in data:
            model.model_grp = data["model_grp"].strip()
        if "recommend" in data:
            model.recommend = to_bool(data["recommend"])
        if "status_valid" in data:
            model.status_valid = to_bool(data["status_valid"])
        model.save()
        invalidate_model_cache("model_meta_update", logger=current_app.logger)
        return success_response(data=model.to_dict(), msg="模型更新成功")
    except DoesNotExist:
        return error_response("模型不存在")
    except IntegrityError:
        return error_response("模型名称已存在")
    except Exception as exc:
        return error_response(f"更新模型失败: {exc}")


@admin_bp.route("/model_meta/batch_update", methods=["POST"])
@require_admin_auth
def model_meta_batch_update():
    try:
        data = get_request_data()
        raw_ids = data.get("ids")
        if raw_ids is None:
            return error_response("模型ID列表不能为空")
        if isinstance(raw_ids, str):
            raw_ids = raw_ids.strip()
            if not raw_ids:
                return error_response("模型ID列表不能为空")
            try:
                parsed_ids = json.loads(raw_ids)
            except Exception:
                parsed_ids = [item.strip() for item in raw_ids.split(",") if item.strip()]
        else:
            parsed_ids = raw_ids
        if not isinstance(parsed_ids, list) or not parsed_ids:
            return error_response("模型ID列表不能为空")
        model_ids = [int(item) for item in parsed_ids]
        updates = {}
        if "recommend" in data:
            updates["recommend"] = to_bool(data.get("recommend"))
        if "status_valid" in data:
            updates["status_valid"] = to_bool(data.get("status_valid"))
        if "model_grp" in data:
            updates["model_grp"] = str(data.get("model_grp") or "").strip()
        if not updates:
            return error_response("至少需要一个可更新字段")
        affected_rows = ModelMeta.update(**updates).where(ModelMeta.id.in_(model_ids)).execute()
        invalidate_model_cache("model_meta_batch_update", logger=current_app.logger)
        return success_response(data={"updated": affected_rows, "ids": model_ids}, msg=f"批量更新成功，共更新 {affected_rows} 条模型记录")
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
        invalidate_model_cache("model_meta_delete", logger=current_app.logger)
        return success_response(msg="模型删除成功")
    except DoesNotExist:
        return error_response("模型不存在")
    except Exception as exc:
        return error_response(f"删除模型失败: {exc}")


@admin_bp.route("/system_prompt/list", methods=["GET"])
@require_admin_auth
def system_prompt_list():
    try:
        page, page_size, offset = parse_pagination_args(default_page_size=30)
        role_group = request.args.get("role_group")
        status_valid = request.args.get("status_valid")
        keyword = (request.args.get("keyword") or "").strip()
        if status_valid is not None:
            status_valid = to_bool(status_valid)
        query = SystemPrompt.select()
        if role_group:
            query = query.where(SystemPrompt.role_group == role_group)
        if status_valid is not None:
            query = query.where(SystemPrompt.status_valid == status_valid)
        if keyword:
            query = query.where(
                (SystemPrompt.role_name.contains(keyword))
                | (SystemPrompt.role_group.contains(keyword))
                | (SystemPrompt.role_desc.contains(keyword))
            )
        total = query.count()
        query = query.order_by(SystemPrompt.id.desc()).offset(offset).limit(page_size)
        prompts = [item for item in query.dicts().iterator()]
        return success_response(data=build_page_result(prompts, total, page, page_size))
    except Exception as exc:
        return error_response(f"获取系统提示词列表失败: {exc}")


@admin_bp.route("/system_prompt/get/<int:prompt_id>", methods=["GET"])
@require_admin_auth
def system_prompt_get(prompt_id):
    try:
        return success_response(data=SystemPrompt.get_by_id(prompt_id).to_dict())
    except DoesNotExist:
        return error_response("系统提示词不存在")
    except Exception as exc:
        return error_response(f"获取系统提示词失败: {exc}")


@admin_bp.route("/system_prompt/create", methods=["POST"])
@require_admin_auth
def system_prompt_create():
    try:
        data = get_request_data()
        role_name = data.get("role_name", "").strip()
        role_group = data.get("role_group", "").strip()
        if not role_name or not role_group:
            return error_response("角色名称和角色分组不能为空")
        prompt = SystemPrompt.create(
            role_name=role_name,
            role_group=role_group,
            role_desc=data.get("role_desc", ""),
            role_content=data.get("role_content", ""),
            status_valid=to_bool(data.get("status_valid", "true")),
        )
        return success_response(data=prompt.to_dict(), msg="系统提示词创建成功")
    except IntegrityError:
        return error_response("该角色名称和分组组合已存在")
    except Exception as exc:
        return error_response(f"创建系统提示词失败: {exc}")


@admin_bp.route("/system_prompt/update", methods=["POST"])
@require_admin_auth
def system_prompt_update():
    try:
        data = get_request_data()
        prompt_id = data.get("id")
        if not prompt_id:
            return error_response("系统提示词ID不能为空")
        prompt = SystemPrompt.get_by_id(int(prompt_id))
        if "role_name" in data:
            prompt.role_name = data["role_name"].strip()
        if "role_group" in data:
            prompt.role_group = data["role_group"].strip()
        if "role_desc" in data:
            prompt.role_desc = data["role_desc"]
        if "role_content" in data:
            prompt.role_content = data["role_content"]
        if "status_valid" in data:
            prompt.status_valid = to_bool(data["status_valid"])
        prompt.save()
        return success_response(data=prompt.to_dict(), msg="系统提示词更新成功")
    except DoesNotExist:
        return error_response("系统提示词不存在")
    except IntegrityError:
        return error_response("该角色名称和分组组合已存在")
    except Exception as exc:
        return error_response(f"更新系统提示词失败: {exc}")


@admin_bp.route("/system_prompt/delete", methods=["POST"])
@require_admin_auth
def system_prompt_delete():
    try:
        data = get_request_data()
        prompt_id = data.get("id")
        if not prompt_id:
            return error_response("系统提示词ID不能为空")
        prompt = SystemPrompt.get_by_id(int(prompt_id))
        prompt.delete_instance()
        return success_response(msg="系统提示词删除成功")
    except DoesNotExist:
        return error_response("系统提示词不存在")
    except Exception as exc:
        return error_response(f"删除系统提示词失败: {exc}")


@admin_bp.route("/test_limit/list", methods=["GET"])
@require_admin_auth
def test_limit_list():
    try:
        page, page_size, offset = parse_pagination_args(default_page_size=50)
        keyword = (request.args.get("keyword") or "").strip()
        query = TestLimit.select()
        if keyword:
            query = query.where(TestLimit.user_ip.contains(keyword))
        total = query.count()
        query = query.order_by(TestLimit.id.desc()).offset(offset).limit(page_size)
        limits = [test_limit_to_dict(limit) for limit in query.iterator()]
        return success_response(data=build_page_result(limits, total, page, page_size))
    except Exception as exc:
        return error_response(f"获取测试限制列表失败: {exc}")


@admin_bp.route("/test_limit/get/<int:limit_id>", methods=["GET"])
@require_admin_auth
def test_limit_get(limit_id):
    try:
        return success_response(data=test_limit_to_dict(TestLimit.get_by_id(limit_id)))
    except DoesNotExist:
        return error_response("测试限制不存在")
    except Exception as exc:
        return error_response(f"获取测试限制失败: {exc}")


@admin_bp.route("/test_limit/create", methods=["POST"])
@require_admin_auth
def test_limit_create():
    try:
        data = get_request_data()
        user_ip = data.get("user_ip", "").strip()
        if not user_ip:
            return error_response("用户IP不能为空")
        test_limit = TestLimit.create(user_ip=user_ip, user_count=int(data.get("user_count", 0)), limit=int(data.get("limit", 20)))
        return success_response(data=test_limit_to_dict(test_limit), msg="测试限制创建成功")
    except IntegrityError:
        return error_response("该IP已存在限制记录")
    except Exception as exc:
        return error_response(f"创建测试限制失败: {exc}")


@admin_bp.route("/test_limit/update", methods=["POST"])
@require_admin_auth
def test_limit_update():
    try:
        data = get_request_data()
        limit_id = data.get("id")
        if not limit_id:
            return error_response("限制ID不能为空")
        test_limit = TestLimit.get_by_id(int(limit_id))
        if "user_ip" in data:
            test_limit.user_ip = data["user_ip"].strip()
        if "user_count" in data:
            test_limit.user_count = int(data["user_count"])
        if "limit" in data:
            test_limit.limit = int(data["limit"])
        test_limit.save()
        return success_response(data=test_limit_to_dict(test_limit), msg="测试限制更新成功")
    except DoesNotExist:
        return error_response("测试限制不存在")
    except IntegrityError:
        return error_response("该IP已存在限制记录")
    except Exception as exc:
        return error_response(f"更新测试限制失败: {exc}")


@admin_bp.route("/test_limit/delete", methods=["POST"])
@require_admin_auth
def test_limit_delete():
    try:
        data = get_request_data()
        limit_id = data.get("id")
        if not limit_id:
            return error_response("限制ID不能为空")
        test_limit = TestLimit.get_by_id(int(limit_id))
        test_limit.delete_instance()
        return success_response(msg="测试限制删除成功")
    except DoesNotExist:
        return error_response("测试限制不存在")
    except Exception as exc:
        return error_response(f"删除测试限制失败: {exc}")


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


@admin_bp.route("/user/list", methods=["GET"])
@require_admin_auth
def user_list():
    try:
        page, page_size, offset = parse_pagination_args(default_page_size=50)
        keyword = (request.args.get("keyword") or "").strip()
        role = (request.args.get("role") or "").strip()
        is_active = request.args.get("is_active")
        query = User.select()
        if keyword:
            query = query.where(User.username.contains(keyword))
        if role:
            query = query.where(User.role == role)
        if is_active is not None:
            query = query.where(User.is_active == to_bool(is_active))
        total = query.count()
        query = query.order_by(User.id.desc()).offset(offset).limit(page_size)
        return success_response(data=build_page_result([user_to_dict(user) for user in query.iterator()], total, page, page_size))
    except Exception as exc:
        return error_response(f"获取用户列表失败: {exc}")


@admin_bp.route("/user/get/<int:user_id>", methods=["GET"])
@require_admin_auth
def user_get(user_id):
    try:
        return success_response(data=user_to_detail_dict(User.get_by_id(user_id)))
    except DoesNotExist:
        return error_response("用户不存在")
    except Exception as exc:
        return error_response(f"获取用户信息失败: {exc}")


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


@admin_bp.route("/notification/list", methods=["GET"])
@require_admin_auth
def notification_list():
    try:
        page, page_size, offset = parse_pagination_args(default_page_size=20)
        status = request.args.get("status")
        keyword = (request.args.get("keyword") or "").strip()
        query = Notification.select()
        if status:
            query = query.where(Notification.status == status)
        if keyword:
            query = query.where((Notification.title.contains(keyword)) | (Notification.content.contains(keyword)))
        total = query.count()
        query = query.order_by(Notification.priority.desc(), Notification.publish_time.desc()).offset(offset).limit(page_size)
        notifications = [notification_to_dict(notification) for notification in query.iterator()]
        return success_response(data=build_page_result(notifications, total, page, page_size))
    except Exception as exc:
        return error_response(f"获取通知列表失败: {exc}")


@admin_bp.route("/notification/active_list", methods=["GET"])
def notification_active_list():
    try:
        limit = request.args.get("limit", 10, type=int)
        return success_response(data=get_active_notifications(limit=limit))
    except Exception as exc:
        return error_response(f"获取有效通知列表失败: {exc}")


@admin_bp.route("/notification/get/<int:notification_id>", methods=["GET"])
@require_admin_auth
def notification_get(notification_id):
    try:
        return success_response(data=notification_to_dict(Notification.get_by_id(notification_id)))
    except DoesNotExist:
        return error_response("通知不存在")
    except Exception as exc:
        return error_response(f"获取通知失败: {exc}")


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


@admin_bp.route("/sql_execute", methods=["POST"])
@require_admin_auth
def sql_execute():
    if not runtime_state.settings.enable_sql_execute:
        return error_response("SQL执行功能已禁用")
    try:
        data = get_request_data()
        sql = data.get("sql", "").strip()
        params = data.get("params", [])
        if not sql:
            return error_response("SQL语句不能为空")
        current_app.logger.info(f"Admin SQL execute: {sql[:100]}...")
        results = sqlitelog.message_query(sql, params if params else None)
        return success_response(data=results, msg="SQL执行成功")
    except Exception as exc:
        current_app.logger.error(f"SQL execute error: {exc}")
        return error_response(f"SQL执行失败: {exc}")


@admin_bp.route("/runtime/overview", methods=["GET"])
@require_admin_auth
def runtime_overview():
    try:
        return success_response(data={"runtime": get_runtime_state_snapshot(), "database": {"path": str(db.database)}})
    except Exception as exc:
        return error_response(f"获取运行时概览失败: {exc}")


@admin_bp.route("/sql/meta", methods=["GET"])
@require_admin_auth
def sql_meta():
    try:
        table_names = db.get_tables()
        tables = []
        for table_name in table_names:
            columns = db.get_columns(table_name)
            column_items = [
                {
                    "name": col.name,
                    "data_type": getattr(col, "data_type", ""),
                    "nullable": bool(getattr(col, "null", True)),
                    "primary_key": bool(getattr(col, "primary_key", False)),
                }
                for col in columns
            ]
            count_sql = f'SELECT COUNT(*) AS total FROM "{table_name}"'
            count_result = sqlitelog.message_query(count_sql)
            row_count = int(count_result[0].get("total", 0)) if count_result else 0
            tables.append({"table_name": table_name, "row_count": row_count, "columns": column_items})
        return success_response(data={"database": {"path": str(db.database)}, "tables": tables})
    except Exception as exc:
        return error_response(f"获取数据库元信息失败: {exc}")
