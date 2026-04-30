from dataclasses import dataclass
from typing import Optional

from dto.common import parse_json_list


@dataclass
class DialogContentRequest:
    dialog_id: Optional[int]

    @classmethod
    def from_data(cls, data):
        raw = data.get("dialogId")
        return cls(dialog_id=int(raw) if raw is not None and str(raw).strip() else None)


@dataclass
class DialogDeleteRequest:
    dialog_ids: list

    @classmethod
    def from_data(cls, data):
        return cls(dialog_ids=parse_json_list(data.get("dialog_ids", "[]"), default=[]))


@dataclass
class DialogTitleUpdateRequest:
    dialog_id: Optional[int]
    new_title: str

    @classmethod
    def from_data(cls, data):
        raw = data.get("dialog_id")
        dialog_id = int(raw) if raw is not None and str(raw).strip() else None
        return cls(dialog_id=dialog_id, new_title=str(data.get("new_title", "")).strip())
