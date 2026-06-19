"""多模态消息归一化工具。

将 OpenAI/Claude/Gemini 各 provider 的响应统一为项目自有 MessagePart 协议。
同时为多模态模型（model_type=3）提供输入图片的 base64 编码转换。
"""

import base64
import logging
import re
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests

# MessagePart 类型常量
PART_TEXT = "text"
PART_IMAGE = "image"
PART_FILE = "file"
PART_TOOL_RESULT = "tool_result"
PART_ERROR = "error"

# 匹配文本中的 [FILE_URL:<url>] 标记
FILE_URL_MARKER_RE = re.compile(r"\[FILE_URL:(https?://[^\]]+)\]")


def build_text_part(text: str) -> Dict[str, Any]:
    return {"type": PART_TEXT, "text": text}


def build_image_part(url: str, alt: Optional[str] = None) -> Dict[str, Any]:
    part: Dict[str, Any] = {"type": PART_IMAGE, "url": url}
    if alt:
        part["alt"] = alt
    return part


def build_file_part(url: str, name: Optional[str] = None, mime_type: Optional[str] = None) -> Dict[str, Any]:
    part: Dict[str, Any] = {"type": PART_FILE, "url": url}
    if name:
        part["name"] = name
    if mime_type:
        part["mimeType"] = mime_type
    return part


def build_error_part(message: str) -> Dict[str, Any]:
    return {"type": PART_ERROR, "message": message}


def build_parts_from_message(assistant_message: Dict[str, Any]) -> List[Dict[str, Any]]:
    """根据 assistant 消息构建 parts 数组。

    支持以下消息字段组合：
    - content (纯文本) → 生成 text part
    - desc (图片描述) → 优先作为 text，有 url 时作为 alt
    - url (图片/文件 URL) → 生成 image part 或 file part
    """
    parts: List[Dict[str, Any]] = []

    text_content = assistant_message.get("content")
    desc_content = assistant_message.get("desc")
    url = assistant_message.get("url")

    # 文本内容：优先用 content，其次用 desc
    if text_content:
        parts.append(build_text_part(text_content))
    elif desc_content and not url:
        # desc 存在但无 url 时，作为纯文本
        parts.append(build_text_part(desc_content))

    # 图片 URL
    if url:
        alt_text = desc_content or text_content or ""
        parts.append(build_image_part(url, alt=alt_text))

    # 兜底：完全没有内容时也保证至少有一个 text part
    if not parts:
        fallback = text_content or desc_content or ""
        parts.append(build_text_part(fallback))

    return parts


def extract_text_from_parts(parts: List[Dict[str, Any]]) -> str:
    """从 parts 中提取所有 text 部分的拼接文本（用于 content 兼容字段）。"""
    texts = [p["text"] for p in parts if p.get("type") == PART_TEXT and p.get("text")]
    return "\n".join(texts)


def ensure_message_parts(message: Dict[str, Any]) -> Dict[str, Any]:
    """确保消息包含 parts 字段，从 content/desc/url 自动生成 parts。

    如果消息已有 parts 则直接返回，否则根据旧字段构建兼容 parts。
    """
    if message.get("parts"):
        return message

    parts = build_parts_from_message(message)
    result = dict(message)
    result["parts"] = parts

    # 确保 content 字段存在（用于兼容旧前端/复制/搜索）
    if not result.get("content"):
        result["content"] = extract_text_from_parts(parts)

    return result


# =============================================================================
# 多模态模型输入处理（model_type=3）
# =============================================================================

# 已知的图片 MIME 类型
IMAGE_CONTENT_TYPES = {
    "image/png", "image/jpeg", "image/jpg", "image/gif",
    "image/webp", "image/bmp", "image/tiff",
}

# 已知的图片文件扩展名
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff", ".svg"}


def _is_image_url(url: str) -> bool:
    """通过 URL 扩展名简单判断是否为图片。"""
    path = urlparse(url).path.lower()
    return any(path.endswith(ext) for ext in IMAGE_EXTENSIONS)


def download_file_as_data_url(url: str, logger: Optional[logging.Logger] = None, timeout: int = 30) -> Optional[str]:
    """从 URL 下载文件，返回 `data:<mime>;base64,<data>` 格式的 Data URL。

    仅用于多模态模型的图片输入——将 [FILE_URL:...] 标记的图片转换为
    base64 data URL，嵌入 Chat Completion API 的 image_url 内容块。
    """
    try:
        response = requests.get(url, timeout=timeout, stream=True)
        if response.status_code != 200:
            if logger:
                logger.error(f"下载文件失败: {url}, status={response.status_code}")
            return None
        file_data = response.content
        if len(file_data) == 0:
            return None
        content_type = response.headers.get("Content-Type", "").split(";")[0].strip()
        if not content_type or content_type == "application/octet-stream":
            # 从扩展名推断
            path = urlparse(url).path.lower()
            for ext, mime in [
                (".png", "image/png"), (".jpg", "image/jpeg"), (".jpeg", "image/jpeg"),
                (".gif", "image/gif"), (".webp", "image/webp"),
                (".bmp", "image/bmp"), (".tiff", "image/tiff"),
            ]:
                if path.endswith(ext):
                    content_type = mime
                    break
            else:
                content_type = "image/png"  # 兜底
        b64_data = base64.b64encode(file_data).decode("utf-8")
        return f"data:{content_type};base64,{b64_data}"
    except Exception as exc:
        if logger:
            logger.error(f"下载文件异常: {url}, err={exc}")
        return None


def extract_file_urls_from_content(content: str) -> List[str]:
    """从消息文本中提取所有 [FILE_URL:<url>] 的 URL 列表。"""
    if not content:
        return []
    return FILE_URL_MARKER_RE.findall(content)


def strip_file_url_markers(content: str) -> str:
    """移除消息文本中的 [FILE_URL:...] 标记，保留纯文本部分。"""
    if not content:
        return ""
    return FILE_URL_MARKER_RE.sub("", content).strip()


def convert_user_message_for_multimodal(
    message: Dict[str, Any],
    logger: Optional[logging.Logger] = None,
    timeout: int = 30,
) -> Dict[str, Any]:
    """将包含 [FILE_URL:...] 的用户消息转换为多模态 content 数组格式。

    输入示例: {"role": "user", "content": "描述这张图\\n[FILE_URL:http://x/a.png]"}
    输出示例: {"role": "user", "content": [{"type": "text", "text": "描述这张图"},
                                            {"type": "image_url", "image_url": {"url": "data:..."}}]}
    """
    text_content = message.get("content", "")
    if not isinstance(text_content, str):
        # 已经是数组格式，直接返回
        return message

    file_urls = extract_file_urls_from_content(text_content)
    if not file_urls:
        # 没有图片，保持字符串格式
        return message

    # 提取纯文本（去除 [FILE_URL:...] 标记）
    clean_text = strip_file_url_markers(text_content)

    # 构建 content 数组
    content_array: List[Dict[str, Any]] = []
    if clean_text:
        content_array.append({"type": "text", "text": clean_text})

    for url in file_urls:
        data_url = download_file_as_data_url(url, logger=logger, timeout=timeout)
        if data_url:
            content_array.append({
                "type": "image_url",
                "image_url": {"url": data_url},
            })
        elif logger:
            logger.warning(f"跳过无法下载的图片: {url}")

    # 如果所有图片都下载失败，回退到纯文本
    if not content_array:
        return {"role": message.get("role", "user"), "content": text_content}

    return {"role": message.get("role", "user"), "content": content_array}


def convert_dialog_for_multimodal(
    dialogvo: List[Dict[str, Any]],
    logger: Optional[logging.Logger] = None,
) -> List[Dict[str, Any]]:
    """为多模态模型转换整个对话数组中的用户消息。

    仅转换 role=user 的消息；assistant/system 消息保持不变。
    """
    converted = []
    for msg in dialogvo:
        role = msg.get("role", "")
        if role == "user":
            converted.append(convert_user_message_for_multimodal(msg, logger=logger))
        else:
            converted.append(msg)
    return converted


def get_model_type_from_cache(model_name: str) -> int:
    """从运行时缓存获取模型的 model_type。默认返回 1（文本类）。"""
    try:
        from conf.runtime import runtime_state

        models = runtime_state.model_cache.get("models")
        if not models:
            return 1
        model_name_lower = model_name.lower()
        for m in models:
            if str(m.get("id", "")).lower() == model_name_lower:
                return int(m.get("model_type", 1))
        return 1
    except Exception:
        return 1


def is_multimodal_model(model_name: str) -> bool:
    """判断模型是否为多模态类（model_type == 3）。"""
    return get_model_type_from_cache(model_name) == 3
