from datetime import datetime
from typing import Optional

from models import Dialog


class LegacyDialogRepo:
    @staticmethod
    def set_dialog(user: str, model: str, chattype: str, dialog_name: str, context: str, dialog_id: Optional[int] = None):
        time_str = datetime.now().strftime('%Y-%m-%d')
        if dialog_id is not None:
            Dialog.update(
                modelname=model,
                dialog_name=dialog_name,
                start_date=time_str,
                context=context,
            ).where(Dialog.id == dialog_id).execute()
            return dialog_id
        return Dialog.replace(
            username=user,
            chattype=chattype,
            modelname=model,
            dialog_name=dialog_name,
            start_date=time_str,
            context=context,
        ).execute()
