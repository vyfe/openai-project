from datetime import datetime, timedelta
from typing import Optional

from model.repositories.log_repository import delete_dialogs, get_dialog_context, get_dialog_list, update_dialog_title
from service.dialog_context_service import parse_dialog_payload


def get_recent_dialogs(user: str, days: Optional[int] = 15):
    min_time = None if days is None or days <= 0 else (datetime.now() - timedelta(days=days)).date()
    dialog_list = get_dialog_list(user, min_time)
    return [{**item, "start_date": item["start_date"].strftime("%Y-%m-%d")} for item in dialog_list]


def get_dialog_content(user: str, dialog_id: int):
    result = get_dialog_context(user, int(dialog_id))
    if not result:
        return None
    context, role_setting, usage = parse_dialog_payload(result.context)
    return {"chattype": result.chattype, "context": context, "role_setting": role_setting, "usage": usage}


def delete_user_dialogs(user: str, dialog_ids: list) -> int:
    return delete_dialogs(user, dialog_ids)


def rename_dialog(user: str, dialog_id: int, new_title: str) -> bool:
    return update_dialog_title(user, dialog_id, new_title)
