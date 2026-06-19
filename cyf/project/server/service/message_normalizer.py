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

# 已知的图片 MIME 类型 → image_url 块
IMAGE_CONTENT_TYPES = {
    "image/png", "image/jpeg", "image/jpg", "image/gif",
    "image/webp", "image/bmp", "image/tiff",
}

# 已知的图片文件扩展名
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff", ".svg"}

# 文本类文件扩展名 → 读取内容作为 text 块
TEXT_FILE_EXTENSIONS = {
    ".txt", ".md", ".markdown", ".json", ".csv", ".xml", ".yaml", ".yml",
    ".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".htm", ".css", ".scss", ".less",
    ".log", ".sh", ".bash", ".zsh", ".cfg", ".ini", ".toml", ".conf",
    ".java", ".c", ".cpp", ".h", ".hpp", ".go", ".rs", ".rb", ".php",
    ".sql", ".r", ".m", ".swift", ".kt", ".scala", ".vue", ".svelte",
}

# 文件处理结果类型
class _FileResult:
    """多模态文件处理结果。"""
    __slots__ = ("kind", "data")
    def __init__(self, kind: str, data: str):
        self.kind = kind  # "image" | "text" | "unsupported"
        self.data = data  # data URL or text content


def _classify_file(url: str, content_type: str) -> str:
    """根据 URL 扩展名和 Content-Type 判断文件类别：image / text / unsupported。"""
    path = urlparse(url).path.lower()
    # 先看扩展名
    for ext in IMAGE_EXTENSIONS:
        if path.endswith(ext):
            return "image"
    for ext in TEXT_FILE_EXTENSIONS:
        if path.endswith(ext):
            return "text"
    # 扩展名未知时，看 Content-Type
    if content_type in IMAGE_CONTENT_TYPES:
        return "image"
    if content_type.startswith("text/") or content_type in {
        "application/json", "application/xml", "application/javascript",
        "application/x-yaml", "application/x-sh",
    }:
        return "text"
    return "unsupported"


def process_file_for_multimodal(
    url: str, logger: Optional[logging.Logger] = None, timeout: int = 30
) -> Optional[_FileResult]:
    """下载 [FILE_URL:...] 指向的文件，按类型返回处理结果。

    - 图片：返回 data URL（base64 编码），用于 image_url 块
    - 文本文件：读取并返回文本内容，用于 text 块
    - 不支持的格式：返回 None，保留原始 [FILE_URL:...] 标记在文本中
    """
    try:
        response = requests.get(url, timeout=timeout)
        if response.status_code != 200:
            if logger:
                logger.error(f"下载文件失败: {url}, status={response.status_code}")
            return None
        file_data = response.content
        if len(file_data) == 0:
            return None

        content_type = response.headers.get("Content-Type", "").split(";")[0].strip()
        file_kind = _classify_file(url, content_type)

        if file_kind == "image":
            # 确定准确的 MIME 类型
            if not content_type or content_type == "application/octet-stream":
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
                    content_type = "image/png"
            b64_data = base64.b64encode(file_data).decode("utf-8")
            return _FileResult("image", f"data:{content_type};base64,{b64_data}")

        elif file_kind == "text":
            # 尝试 UTF-8 解码，失败则用 Latin-1 兜底
            try:
                text = file_data.decode("utf-8")
            except UnicodeDecodeError:
                text = file_data.decode("latin-1")
            filename = urlparse(url).path.rsplit("/", 1)[-1] or "file"
            if logger:
                logger.info(f"文本文件已读取: {filename}, {len(text)} 字符")
            return _FileResult("text", text)

        else:
            if logger:
                logger.warning(f"不支持的文件类型（{content_type}），保留原始标记: {url}")
            return None

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

    根据文件类型分别处理：
    - 图片（png/jpg/gif 等）→ image_url 块（base64 data URL）
    - 文本文件（txt/md/json/py 等）→ text 块（读取文件内容）
    - 不支持的格式 → 保留原始 [FILE_URL:...] 标记在文本中

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
        # 没有文件，保持字符串格式
        return message

    # 提取纯文本（去除 [FILE_URL:...] 标记）
    clean_text = strip_file_url_markers(text_content)

    # 构建 content 数组
    content_array: List[Dict[str, Any]] = []
    if clean_text:
        content_array.append({"type": "text", "text": clean_text})

    for url in file_urls:
        result = process_file_for_multimodal(url, logger=logger, timeout=timeout)
        if result is None:
            # 下载失败或不支持的格式：保留原始标记在文本中
            filename = urlparse(url).path.rsplit("/", 1)[-1] or "file"
            content_array.append({
                "type": "text",
                "text": f"\n[附件: {filename}]\n[链接: {url}]\n",
            })
            continue

        if result.kind == "image":
            content_array.append({
                "type": "image_url",
                "image_url": {"url": result.data},
            })
        elif result.kind == "text":
            filename = urlparse(url).path.rsplit("/", 1)[-1] or "file"
            content_array.append({
                "type": "text",
                "text": f"\n--- 文件: {filename} ---\n{result.data}\n--- 文件结束 ---\n",
            })

    # 如果 content_array 为空（极端情况），回退到原始文本
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
