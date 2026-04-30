import json
from datetime import datetime, timedelta

from model.repositories.log_repository import delete_dialogs, get_dialog_context, get_dialog_list, update_dialog_title


def get_recent_dialogs(user: str, days: int = 15):
    min_time = (datetime.now() - timedelta(days=days)).date()
    dialog_list = get_dialog_list(user, min_time)
    return [{**item, "start_date": item["start_date"].strftime("%Y-%m-%d")} for item in dialog_list]


def get_dialog_content(user: str, dialog_id: int):
    result = get_dialog_context(user, int(dialog_id))
    if not result:
        return None
    context = json.loads(result.context)
    return {"chattype": result.chattype, "context": context}


def delete_user_dialogs(user: str, dialog_ids: list) -> int:
    return delete_dialogs(user, dialog_ids)


def rename_dialog(user: str, dialog_id: int, new_title: str) -> bool:
    return update_dialog_title(user, dialog_id, new_title)
