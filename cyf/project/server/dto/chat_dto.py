from dataclasses import dataclass
from typing import Optional


@dataclass
class ChatRequest:
    model: str
    dialog: str
    dialog_mode: str
    dialog_title: str
    system_prompt_id: str
    max_response_tokens: Optional[int]

    @classmethod
    def from_data(cls, data):
        raw_tokens = data.get("max_response_tokens")
        max_tokens = int(raw_tokens) if raw_tokens is not None and str(raw_tokens).strip() else None
        return cls(
            model=str(data.get("model", "")).strip(),
            dialog=str(data.get("dialog", "")),
            dialog_mode=str(data.get("dialog_mode", "single")).strip(),
            dialog_title=str(data.get("dialog_title", "")).strip(),
            system_prompt_id=str(data.get("system_prompt_id", "")).strip(),
            max_response_tokens=max_tokens,
        )


@dataclass
class StreamChatRequest(ChatRequest):
    request_id: str

    @classmethod
    def from_data(cls, data):
        base = ChatRequest.from_data(data)
        return cls(
            model=base.model,
            dialog=base.dialog,
            dialog_mode=base.dialog_mode,
            dialog_title=base.dialog_title,
            system_prompt_id=base.system_prompt_id,
            max_response_tokens=base.max_response_tokens,
            request_id=str(data.get("request_id", "")).strip(),
        )


@dataclass
class ImageChatRequest(ChatRequest):
    size: str
    dialog_id: str

    @classmethod
    def from_data(cls, data):
        base = ChatRequest.from_data(data)
        return cls(
            model=base.model,
            dialog=base.dialog,
            dialog_mode=base.dialog_mode,
            dialog_title=base.dialog_title,
            system_prompt_id=base.system_prompt_id,
            max_response_tokens=base.max_response_tokens,
            size=str(data.get("size", "1024x1024")).strip(),
            dialog_id=str(data.get("dialogId", "")).strip(),
        )


@dataclass
class StreamCancelRequest:
    request_id: str

    @classmethod
    def from_data(cls, data):
        return cls(request_id=str(data.get("request_id", "")).strip())
