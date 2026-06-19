"""message_normalizer 纯函数测试 — 多模态消息归一化工具。

覆盖 Master 分支合入的多模态能力核心逻辑：
- MessagePart 构建器（text/image/file/error）
- assistant 消息 → parts 转换
- [FILE_URL:...] 提取/剥离
- 文件类型分类（image/text/unsupported）
- 多模态用户消息转换
- 模型类型缓存查询
"""

from unittest.mock import MagicMock, patch

import pytest

from service.message_normalizer import (
    PART_TEXT,
    PART_IMAGE,
    PART_FILE,
    PART_ERROR,
    _FileResult,
    build_text_part,
    build_image_part,
    build_file_part,
    build_error_part,
    build_parts_from_message,
    extract_text_from_parts,
    ensure_message_parts,
    _classify_file,
    extract_file_urls_from_content,
    strip_file_url_markers,
    convert_user_message_for_multimodal,
    convert_dialog_for_multimodal,
    get_model_type_from_cache,
    is_multimodal_model,
)


# ============================================================================
# MessagePart 构建器
# ============================================================================

class TestBuildTextPart:
    def test_builds_text_part(self):
        result = build_text_part("hello")
        assert result == {"type": PART_TEXT, "text": "hello"}

    def test_builds_empty_text(self):
        result = build_text_part("")
        assert result == {"type": PART_TEXT, "text": ""}


class TestBuildImagePart:
    def test_builds_image_part_without_alt(self):
        result = build_image_part("http://x.com/a.png")
        assert result == {"type": PART_IMAGE, "url": "http://x.com/a.png"}

    def test_builds_image_part_with_alt(self):
        result = build_image_part("http://x.com/a.png", "a photo")
        assert result == {"type": PART_IMAGE, "url": "http://x.com/a.png", "alt": "a photo"}


class TestBuildFilePart:
    def test_builds_file_part_minimal(self):
        result = build_file_part("http://x.com/a.pdf")
        assert result == {"type": PART_FILE, "url": "http://x.com/a.pdf"}

    def test_builds_file_part_with_name(self):
        result = build_file_part("http://x.com/a.pdf", "report.pdf")
        assert result["name"] == "report.pdf"

    def test_builds_file_part_with_mime_type(self):
        result = build_file_part("http://x.com/a.pdf", mime_type="application/pdf")
        assert result["mimeType"] == "application/pdf"


class TestBuildErrorPart:
    def test_builds_error_part(self):
        result = build_error_part("something went wrong")
        assert result == {"type": PART_ERROR, "message": "something went wrong"}


# ============================================================================
# build_parts_from_message — assistant 消息转 parts
# ============================================================================

class TestBuildPartsFromMessage:
    def test_content_only_creates_text_part(self):
        msg = {"content": "hello world"}
        parts = build_parts_from_message(msg)
        assert len(parts) == 1
        assert parts[0] == {"type": PART_TEXT, "text": "hello world"}

    def test_desc_without_url_creates_text_part(self):
        msg = {"desc": "a beautiful sunset"}
        parts = build_parts_from_message(msg)
        assert len(parts) == 1
        assert parts[0] == {"type": PART_TEXT, "text": "a beautiful sunset"}

    def test_url_only_creates_image_part_without_alt(self):
        msg = {"url": "http://x.com/img.png"}
        parts = build_parts_from_message(msg)
        assert len(parts) == 1
        # alt 为空时不写入 key（build_image_part 的 if alt 判断）
        assert parts[0] == {"type": PART_IMAGE, "url": "http://x.com/img.png"}

    def test_url_with_desc_sets_alt(self):
        msg = {"url": "http://x.com/img.png", "desc": "sunset"}
        parts = build_parts_from_message(msg)
        assert len(parts) == 1
        assert parts[0] == {"type": PART_IMAGE, "url": "http://x.com/img.png", "alt": "sunset"}

    def test_content_and_url_creates_both_parts(self):
        msg = {"content": "here is an image", "url": "http://x.com/img.png"}
        parts = build_parts_from_message(msg)
        assert len(parts) == 2
        assert parts[0] == {"type": PART_TEXT, "text": "here is an image"}
        assert parts[1]["type"] == PART_IMAGE

    def test_empty_message_creates_fallback_text_part(self):
        msg = {}
        parts = build_parts_from_message(msg)
        assert len(parts) == 1
        assert parts[0] == {"type": PART_TEXT, "text": ""}


# ============================================================================
# extract_text_from_parts
# ============================================================================

class TestExtractTextFromParts:
    def test_extracts_single_text(self):
        parts = [{"type": PART_TEXT, "text": "hello"}]
        assert extract_text_from_parts(parts) == "hello"

    def test_joins_multiple_texts(self):
        parts = [
            {"type": PART_TEXT, "text": "line1"},
            {"type": PART_IMAGE, "url": "http://x.com/a.png"},
            {"type": PART_TEXT, "text": "line2"},
        ]
        assert extract_text_from_parts(parts) == "line1\nline2"

    def test_skips_empty_texts(self):
        parts = [
            {"type": PART_TEXT, "text": ""},
            {"type": PART_TEXT, "text": "valid"},
            {"type": PART_TEXT, "text": None},
        ]
        assert extract_text_from_parts(parts) == "valid"

    def test_no_text_parts_returns_empty(self):
        parts = [{"type": PART_IMAGE, "url": "http://x.com/a.png"}]
        assert extract_text_from_parts(parts) == ""


# ============================================================================
# ensure_message_parts
# ============================================================================

class TestEnsureMessageParts:
    def test_already_has_parts_returns_unchanged(self):
        msg = {"content": "hello", "parts": [{"type": PART_TEXT, "text": "hello"}]}
        result = ensure_message_parts(msg)
        assert result == msg

    def test_generates_parts_from_content(self):
        msg = {"content": "hello"}
        result = ensure_message_parts(msg)
        assert "parts" in result
        assert result["parts"] == [{"type": PART_TEXT, "text": "hello"}]
        assert result["content"] == "hello"

    def test_generates_content_when_missing(self):
        msg = {"desc": "sunset", "url": "http://x.com/img.png"}
        result = ensure_message_parts(msg)
        assert "content" in result
        assert "parts" in result

    def test_parts_field_unchanged_when_present(self):
        # ensure_message_parts 遇到已有 parts 时直接返回原消息（不修改）
        msg = {"parts": [{"type": PART_TEXT, "text": "kept"}]}
        result = ensure_message_parts(msg)
        assert result is msg  # 原样返回
        assert result["parts"] == [{"type": PART_TEXT, "text": "kept"}]


# ============================================================================
# _FileResult
# ============================================================================

class TestFileResult:
    def test_image_kind(self):
        fr = _FileResult("image", "data:image/png;base64,abc")
        assert fr.kind == "image"
        assert fr.data == "data:image/png;base64,abc"

    def test_text_kind(self):
        fr = _FileResult("text", "hello file content")
        assert fr.kind == "text"
        assert fr.data == "hello file content"

    def test_unsupported_kind(self):
        fr = _FileResult("unsupported", "")
        assert fr.kind == "unsupported"

    def test_slots_prevents_extra_attrs(self):
        fr = _FileResult("image", "data")
        with pytest.raises(AttributeError):
            fr.extra = "no"


# ============================================================================
# _classify_file — 根据 URL/Content-Type 分类
# ============================================================================

class TestClassifyFile:
    def test_png_extension(self):
        assert _classify_file("http://x.com/a.png", "") == "image"

    def test_jpg_extension(self):
        assert _classify_file("http://x.com/a.jpg", "") == "image"
        assert _classify_file("http://x.com/a.jpeg", "") == "image"

    def test_gif_extension(self):
        assert _classify_file("http://x.com/a.gif", "") == "image"

    def test_webp_extension(self):
        assert _classify_file("http://x.com/a.webp", "") == "image"

    def test_txt_extension(self):
        assert _classify_file("http://x.com/a.txt", "") == "text"

    def test_md_extension(self):
        assert _classify_file("http://x.com/readme.md", "") == "text"

    def test_json_extension(self):
        assert _classify_file("http://x.com/data.json", "") == "text"

    def test_py_extension(self):
        assert _classify_file("http://x.com/script.py", "") == "text"

    def test_csv_extension(self):
        assert _classify_file("http://x.com/data.csv", "") == "text"

    def test_html_extension(self):
        assert _classify_file("http://x.com/page.html", "") == "text"

    def test_default_to_content_type_image(self):
        # .bin 不在已知扩展名中，但 Content-Type 是 image/png
        assert _classify_file("http://x.com/file.bin", "image/png") == "image"

    def test_default_to_content_type_text(self):
        assert _classify_file("http://x.com/file.bin", "text/plain") == "text"

    def test_default_to_content_type_json(self):
        assert _classify_file("http://x.com/file.bin", "application/json") == "text"

    def test_unknown_returns_unsupported(self):
        assert _classify_file("http://x.com/file.xyz", "application/octet-stream") == "unsupported"

    def test_case_insensitive_extension(self):
        assert _classify_file("http://x.com/a.PNG", "") == "image"
        assert _classify_file("http://x.com/a.TXT", "") == "text"

    def test_extension_with_query_params(self):
        assert _classify_file("http://x.com/image.png?size=large", "") == "image"


# ============================================================================
# extract_file_urls_from_content
# ============================================================================

class TestExtractFileUrlsFromContent:
    def test_extracts_single_url(self):
        content = "描述这张图\n[FILE_URL:http://x.com/a.png]"
        urls = extract_file_urls_from_content(content)
        assert urls == ["http://x.com/a.png"]

    def test_extracts_multiple_urls(self):
        content = "[FILE_URL:http://x.com/a.png]\n[FILE_URL:http://x.com/b.jpg]"
        urls = extract_file_urls_from_content(content)
        assert urls == ["http://x.com/a.png", "http://x.com/b.jpg"]

    def test_no_urls_returns_empty(self):
        assert extract_file_urls_from_content("plain text") == []

    def test_empty_content(self):
        assert extract_file_urls_from_content("") == []
        assert extract_file_urls_from_content(None) == []

    def test_url_with_special_chars(self):
        content = "[FILE_URL:http://x.com/file%20name.txt]"
        urls = extract_file_urls_from_content(content)
        assert urls == ["http://x.com/file%20name.txt"]

    def test_non_http_url_ignored(self):
        content = "[FILE_URL:ftp://x.com/a.png]"
        urls = extract_file_urls_from_content(content)
        assert urls == []


# ============================================================================
# strip_file_url_markers
# ============================================================================

class TestStripFileUrlMarkers:
    def test_strips_single_marker(self):
        content = "描述图片\n[FILE_URL:http://x.com/a.png]"
        assert strip_file_url_markers(content) == "描述图片"

    def test_strips_multiple_markers(self):
        content = "图1\n[FILE_URL:http://x.com/a.png]\n图2\n[FILE_URL:http://x.com/b.jpg]"
        assert strip_file_url_markers(content) == "图1\n\n图2"

    def test_no_markers_returns_unchanged(self):
        content = "plain text"
        assert strip_file_url_markers(content) == "plain text"

    def test_empty_content(self):
        assert strip_file_url_markers("") == ""
        assert strip_file_url_markers(None) == ""

    def test_only_marker_returns_empty(self):
        content = "[FILE_URL:http://x.com/a.png]"
        assert strip_file_url_markers(content) == ""


# ============================================================================
# convert_user_message_for_multimodal — 多模态用户消息转换
# ============================================================================

class TestConvertUserMessageForMultimodal:
    def test_no_file_urls_returns_unchanged(self):
        msg = {"role": "user", "content": "hello"}
        result = convert_user_message_for_multimodal(msg)
        assert result == msg

    def test_array_content_returns_unchanged(self):
        msg = {"role": "user", "content": [{"type": "text", "text": "hello"}]}
        result = convert_user_message_for_multimodal(msg)
        assert result == msg

    @patch("service.message_normalizer.process_file_for_multimodal")
    def test_image_file_converts_to_image_url_block(self, mock_process):
        mock_process.return_value = _FileResult("image", "data:image/png;base64,abc123")
        msg = {"role": "user", "content": "描述这张图\n[FILE_URL:http://x.com/a.png]"}
        result = convert_user_message_for_multimodal(msg)

        assert result["role"] == "user"
        assert isinstance(result["content"], list)
        assert len(result["content"]) == 2
        # 第一个是文本块
        assert result["content"][0] == {"type": "text", "text": "描述这张图"}
        # 第二个是图片块
        assert result["content"][1] == {
            "type": "image_url",
            "image_url": {"url": "data:image/png;base64,abc123"},
        }

    @patch("service.message_normalizer.process_file_for_multimodal")
    def test_text_file_converts_to_text_block(self, mock_process):
        mock_process.return_value = _FileResult("text", "file content here")
        msg = {"role": "user", "content": "分析这个文件\n[FILE_URL:http://x.com/doc.txt]"}
        result = convert_user_message_for_multimodal(msg)

        assert isinstance(result["content"], list)
        assert len(result["content"]) == 2
        assert result["content"][0] == {"type": "text", "text": "分析这个文件"}
        # 文本块包含文件名和文件内容
        assert result["content"][1]["type"] == "text"
        assert "doc.txt" in result["content"][1]["text"]
        assert "file content here" in result["content"][1]["text"]

    @patch("service.message_normalizer.process_file_for_multimodal")
    def test_unsupported_file_keeps_reference(self, mock_process):
        mock_process.return_value = None
        msg = {"role": "user", "content": "看看这个文件\n[FILE_URL:http://x.com/unknown.xyz]"}
        result = convert_user_message_for_multimodal(msg)

        assert isinstance(result["content"], list)
        assert len(result["content"]) == 2
        # 第二个块保留了文件名和链接
        assert "unknown.xyz" in result["content"][1]["text"]
        assert "http://x.com/unknown.xyz" in result["content"][1]["text"]
        assert "[附件:" in result["content"][1]["text"]

    @patch("service.message_normalizer.process_file_for_multimodal")
    def test_multiple_files_mixed_types(self, mock_process):
        def side_effect(url, **kwargs):
            if "a.png" in url:
                return _FileResult("image", "data:image/png;base64,img")
            if "doc.txt" in url:
                return _FileResult("text", "file content")
            return None
        mock_process.side_effect = side_effect

        msg = {
            "role": "user",
            "content": "分析\n[FILE_URL:http://x.com/a.png]\n[FILE_URL:http://x.com/doc.txt]\n[FILE_URL:http://x.com/unknown.xyz]",
        }
        result = convert_user_message_for_multimodal(msg)

        assert isinstance(result["content"], list)
        assert len(result["content"]) == 4  # text + image + text + text(reference)
        assert result["content"][1]["type"] == "image_url"
        assert "doc.txt" in result["content"][2]["text"]
        assert "unknown.xyz" in result["content"][3]["text"]

    def test_only_file_no_text(self):
        msg = {"role": "user", "content": "[FILE_URL:http://x.com/doc.txt]"}
        with patch("service.message_normalizer.process_file_for_multimodal") as mock:
            mock.return_value = _FileResult("text", "content")
            result = convert_user_message_for_multimodal(msg)
            # 没有纯文本，只有一个文件文本块
            assert len(result["content"]) == 1
            assert result["content"][0]["type"] == "text"

    @patch("service.message_normalizer.process_file_for_multimodal")
    def test_all_files_fail_falls_back_to_original(self, mock_process):
        mock_process.return_value = None
        msg = {"role": "user", "content": "描述\n[FILE_URL:http://x.com/bad.png]"}
        result = convert_user_message_for_multimodal(msg)
        # 文本 + 一个带附件的文本块（非空）
        assert isinstance(result["content"], list)
        assert len(result["content"]) == 2  # clean text + reference block


# ============================================================================
# convert_dialog_for_multimodal — 对话数组转换
# ============================================================================

class TestConvertDialogForMultimodal:
    def test_converts_user_messages_only(self):
        dialogvo = [
            {"role": "system", "content": "you are helpful"},
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
            {"role": "user", "content": "[FILE_URL:http://x.com/a.png]"},
        ]

        with patch("service.message_normalizer.convert_user_message_for_multimodal") as mock_convert:
            mock_convert.side_effect = lambda msg, **kw: (
                {"role": msg["role"], "content": [{"type": "text", "text": "converted"}]}
                if msg["role"] == "user"
                else msg
            )
            result = convert_dialog_for_multimodal(dialogvo)

        # 系统消息和 assistant 消息保持不变
        assert result[0] == {"role": "system", "content": "you are helpful"}
        assert result[2] == {"role": "assistant", "content": "hi"}
        # 用户消息被转换
        assert isinstance(result[1]["content"], list)
        assert isinstance(result[3]["content"], list)

    def test_empty_dialog(self):
        assert convert_dialog_for_multimodal([]) == []

    def test_no_user_messages(self):
        dialogvo = [
            {"role": "system", "content": "sys"},
            {"role": "assistant", "content": "assistant"},
        ]
        result = convert_dialog_for_multimodal(dialogvo)
        assert result == dialogvo


# ============================================================================
# get_model_type_from_cache / is_multimodal_model
# ============================================================================

class TestGetModelTypeFromCache:
    def test_returns_3_for_multimodal_model(self):
        with patch("conf.runtime.runtime_state") as mock_rs:
            mock_rs.model_cache = {
                "models": [
                    {"id": "gpt-5.5", "model_type": 3},
                    {"id": "gpt-4o", "model_type": 1},
                ]
            }
            assert get_model_type_from_cache("gpt-5.5") == 3

    def test_returns_1_for_text_model(self):
        with patch("conf.runtime.runtime_state") as mock_rs:
            mock_rs.model_cache = {
                "models": [
                    {"id": "gpt-5.5", "model_type": 3},
                    {"id": "deepseek-v4", "model_type": 1},
                ]
            }
            assert get_model_type_from_cache("deepseek-v4") == 1

    def test_unknown_model_returns_1(self):
        with patch("conf.runtime.runtime_state") as mock_rs:
            mock_rs.model_cache = {"models": []}
            assert get_model_type_from_cache("unknown-model") == 1

    def test_empty_cache_returns_1(self):
        with patch("conf.runtime.runtime_state") as mock_rs:
            mock_rs.model_cache = {}
            assert get_model_type_from_cache("gpt-5.5") == 1

    def test_cache_exception_returns_1(self):
        with patch("conf.runtime.runtime_state") as mock_rs:
            mock_rs.model_cache = None
            assert get_model_type_from_cache("gpt-5.5") == 1

    def test_case_insensitive_match(self):
        with patch("conf.runtime.runtime_state") as mock_rs:
            mock_rs.model_cache = {
                "models": [{"id": "GPT-5.5", "model_type": 3}]
            }
            assert get_model_type_from_cache("gpt-5.5") == 3


class TestIsMultimodalModel:
    def test_multimodal_model_returns_true(self):
        with patch("service.message_normalizer.get_model_type_from_cache", return_value=3):
            assert is_multimodal_model("gpt-5.5") is True

    def test_text_model_returns_false(self):
        with patch("service.message_normalizer.get_model_type_from_cache", return_value=1):
            assert is_multimodal_model("deepseek-v4") is False

    def test_image_model_returns_false(self):
        with patch("service.message_normalizer.get_model_type_from_cache", return_value=2):
            assert is_multimodal_model("dall-e-3") is False
