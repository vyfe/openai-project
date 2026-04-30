from model.db import db, init_db as _init_db
from model.entities import ALL_MODELS, Dialog, Log, ModelMeta, Notification, SystemPrompt, TestLimit, User
from model.repositories.log_repository import (
    delete_dialogs,
    get_dialog_context,
    get_dialog_list,
    set_dialog,
    set_log,
    update_dialog_title,
)
from model.repositories.model_meta_repository import (
    get_model_meta_list,
    get_system_prompt_by_id,
    get_system_prompt_list,
    get_system_prompts_by_group,
)
from model.repositories.user_repository import (
    check_test_limit_exceeded,
    create_notification,
    create_user,
    delete_notification,
    find_user_by_token,
    get_active_notifications,
    get_active_token_count,
    get_all_active_users,
    get_notification_count,
    get_notification_list,
    get_or_create_test_limit,
    get_user_api_key,
    get_user_browser_conf,
    get_user_by_username,
    get_user_token_payload,
    increment_test_limit,
    message_query,
    reset_user_password,
    set_user_browser_conf,
    set_user_token_payload,
    update_notification,
    user_exists_in_db,
    verify_user_password,
)


def init_db():
    _init_db(ALL_MODELS, User)
