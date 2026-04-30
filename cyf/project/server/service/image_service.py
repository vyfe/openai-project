import json
import os
import re
from urllib.parse import urlparse

import requests

from conf.runtime import runtime_state
from model.repositories.log_repository import set_dialog, set_log
from service.common_service import handle_api_exception
from service.host_service import get_client_for_user
from service.model_service import is_valid_model
from service.system_prompt_service import fetch_system_prompt


FILE_URL_PATTERN = re.compile(r"\[FILE_URL:(https?://[^\]]+)\]")


def extract_title_from_dialog(dialogvo: list, max_length: int = 50) -> str:
    for msg in dialogvo:
        if msg.get("role") == "user":
            content = msg.get("content", "")
            return content[:max_length] + "..." if len(content) > max_length else content
    return "Untitled"


def url_to_file(url: str, logger) -> bytes:
    response = requests.get(url, timeout=30)
    if response.status_code == 200:
        return response.content
    logger.error(f"URL转文件失败: 状态码 {response.status_code}")
    raise Exception(f"无法下载文件，状态码: {response.status_code}")


def get_content_type(filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    content_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
        ".tiff": "image/tiff",
    }
    return content_types.get(ext, "application/octet-stream")


def process_pic_dialog_with_urls(dialogs: str, logger) -> dict:
    result = {
        "processed_dialogs": dialogs,
        "files": [],
        "text_content": dialogs,
        "original_content": dialogs,
    }
    file_urls = FILE_URL_PATTERN.findall(dialogs)
    if file_urls:
        text_content = FILE_URL_PATTERN.sub("", dialogs).strip()
        result["text_content"] = text_content
        for url in file_urls:
            try:
                file_data = url_to_file(url, logger)
                filename = os.path.basename(urlparse(url).path) or "file"
                result["files"].append(
                    {
                        "url": url,
                        "data": (filename, file_data, get_content_type(filename)),
                        "filename": filename,
                    }
                )
            except Exception as exc:
                logger.error(f"处理文件URL失败 {url}: {exc}")
    result["processed_dialogs"] = result["text_content"]
    return result


def generate_or_edit_image(user: str, payload, logger):
    model = payload.model
    if not is_valid_model(model):
        return {"msg": "not supported user or model"}, 200

    dialogs = payload.dialog
    dialog_mode = payload.dialog_mode
    dialog_id = payload.dialog_id or None
    system_prompt_id = payload.system_prompt_id
    dialog_title = payload.dialog_title
    size = payload.size

    if dialog_mode == "single":
        dialogvo = []
        processed_data = process_pic_dialog_with_urls(dialogs, logger)
        title = dialog_title or processed_data["original_content"]
    else:
        dialogvo = json.loads(dialogs)
        title = dialog_title or extract_title_from_dialog(dialogvo)
        if system_prompt_id:
            system_prompt = fetch_system_prompt(int(system_prompt_id))
            sys_content = system_prompt["role_content"] if system_prompt else ""
        else:
            sys_content = next((msg["content"] for msg in dialogvo if msg["role"] == "system"), "")
        full_content = f"{sys_content}\n{dialogvo[-1]['content']}" if sys_content else dialogvo[-1]["content"]
        processed_data = process_pic_dialog_with_urls(full_content, logger)

    try:
        client, url_index = get_client_for_user(user)
        if processed_data["files"]:
            result = client.images.edit(
                model=model,
                image=processed_data["files"][0]["data"],
                prompt=processed_data["text_content"],
                n=1,
                response_format="url",
                size=size,
                timeout=300,
            )
        else:
            result = client.images.generate(
                model=model,
                prompt=processed_data["text_content"],
                n=1,
                response_format="url",
                size=size,
                timeout=300,
            )
    except Exception as api_exc:
        return handle_api_exception(api_exc, logger, user=user, model=model, dialog_content=dialogs, url_index=url_index), 200

    desc = result.data[0].revised_prompt or "图片已生成"
    result_save = {"role": "assistant", "desc": desc, "url": f"{result.data[0].url}"}
    set_log(user, 1, model, json.dumps(result.to_dict()))
    try:
        if dialog_mode == "single":
            dialogvo.append({"role": "user", "desc": processed_data["original_content"]})
            dialogvo.append(result_save)
        else:
            if not isinstance(dialogvo, list):
                dialogvo = [dialogvo]
            dialogvo.append(result_save)
        set_dialog(user, model, "pic", title, json.dumps(dialogvo), dialog_id)
    except Exception as exc:
        logger.error(f"获取对话历史失败: {exc}")
        if not isinstance(dialogvo, list):
            dialogvo = [dialogvo]
        dialogvo.append(result_save)
        set_dialog(user, model, "pic", title, json.dumps(dialogvo))
    return result_save, 200
