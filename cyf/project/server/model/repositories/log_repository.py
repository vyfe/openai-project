from datetime import date, datetime

from peewee import DoesNotExist

from model.entities import Dialog, Log


def set_log(user: str, usage: int, model: str, text: str):
    Log.create(username=user, usage=usage, modelname=model, request_text=text)


def set_dialog(user: str, model: str, chattype: str, dialog_name: str, context: str, dialog_id: int = None):
    time_str = datetime.now().strftime("%Y-%m-%d")
    if dialog_id is not None:
        Dialog.update(modelname=model, dialog_name=dialog_name, start_date=time_str, context=context).where(Dialog.id == dialog_id).execute()
        return dialog_id
    return Dialog.replace(
        username=user,
        chattype=chattype,
        modelname=model,
        dialog_name=dialog_name,
        start_date=time_str,
        context=context,
    ).execute()


def get_dialog_list(user: str, start_date: date):
    query = (
        Dialog.select(Dialog.id, Dialog.username, Dialog.chattype, Dialog.modelname, Dialog.dialog_name, Dialog.start_date)
        .where(Dialog.username == user, Dialog.start_date >= start_date)
        .order_by(Dialog.id.desc())
    )
    return [dialog for dialog in query.dicts().iterator()] if query.exists() else []


def get_dialog_context(user: str, dialog_id: int):
    try:
        return Dialog.get(Dialog.username == user, Dialog.id == dialog_id)
    except DoesNotExist:
        return None


def delete_dialogs(user: str, dialog_ids: list) -> int:
    if not dialog_ids:
        return 0
    return Dialog.delete().where((Dialog.username == user) & (Dialog.id.in_(dialog_ids))).execute()


def update_dialog_title(user: str, dialog_id: int, new_title: str) -> bool:
    try:
        rows_modified = Dialog.update(dialog_name=new_title).where((Dialog.username == user) & (Dialog.id == dialog_id)).execute()
        return rows_modified > 0
    except Exception as exc:
        print(f"更新对话标题时发生错误: {exc}")
        return False
