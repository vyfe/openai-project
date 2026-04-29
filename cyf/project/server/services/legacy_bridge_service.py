from datetime import datetime
from typing import Any, Dict, Optional

import sqlitelog


def map_legacy_dialog_to_single_master(user: str, dialog_id: int) -> Optional[Dict[str, Any]]:
    dialog = sqlitelog.get_dialog_context(user, dialog_id)
    if not dialog:
        return None

    master = sqlitelog.create_master_conversation(
        owner=user,
        title=dialog.dialog_name,
        session_type='single',
        active_models=[dialog.modelname],
    )
    child = sqlitelog.create_child_conversation(
        master_id=master.id,
        model_id=dialog.modelname,
        status='active',
        backend_dialog_id=dialog.id,
        created_round_index=0,
    )

    return {
        'master_id': master.id,
        'child_id': child.id,
        'legacy_dialog_id': dialog.id,
    }
