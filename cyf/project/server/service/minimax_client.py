"""MiniMax 官方语音接口：不自动重试付费请求，不跟随凭据跳转。"""
import io
import math
import re
import ipaddress
import socket
from urllib.parse import urlsplit
import wave

import requests

MODELS = (
    "speech-2.8-hd", "speech-2.8-turbo", "speech-2.6-hd", "speech-2.6-turbo",
    "speech-02-hd", "speech-02-turbo", "speech-01-hd", "speech-01-turbo",
)
# 音乐生成只开放文本生音乐模型；翻唱模型需要参考音频，不在文本生音乐的可选范围内。
MUSIC_MODELS = ("music-3.0", "music-2.6")
COVER_MODEL = "music-cover"
COVER_AUDIO_EXTS = ("mp3", "wav", "flac", "m4a", "aac", "ogg")
HOSTS = {"cn": "https://api.minimax.cn", "intl": "https://api.minimax.io"}
# 云端上限 50 MB，本地统一按 20 MB 收口，避免 base64 后超出网关上传限制。
MAX_AUDIO_BYTES = 20 * 1024 * 1024


class VoiceError(Exception):
    def __init__(self, message, status=400, code=None, uncertain=False):
        super().__init__(message)
        self.status, self.code, self.uncertain = status, code, uncertain


def require(condition, message):
    if not condition:
        raise VoiceError(message)


def text_value(data, name, limit, required=True):
    value = data.get(name, "")
    require(isinstance(value, str), f"{name} 必须是文本。")
    value = value.strip()
    require(len(value) <= limit and (bool(value) or not required), f"{name} 不能为空且不能超过 {limit} 字符。")
    return value


def numeric(value, low, high, name, integer=False):
    require(isinstance(value, (float, int)) and not isinstance(value, bool), f"{name} 必须是数字。")
    require(math.isfinite(value) and low <= value <= high, f"{name} 范围应为 {low}–{high}。")
    require(not integer or int(value) == value, f"{name} 必须是整数。")
    return int(value) if integer else value


def read_audio_bytes(file, extensions, label):
    """按扩展名与大小读取音频字节，返回 (扩展名, 内容)。"""
    require(file is not None and file.filename, f"请选择{label}。")
    ext = file.filename.rsplit(".", 1)[-1].lower()
    require(ext in extensions, f"{label}仅支持 {'、'.join(item.upper() for item in extensions)}。")
    content = file.read(MAX_AUDIO_BYTES + 1)
    require(0 < len(content) <= MAX_AUDIO_BYTES, f"{label}不能超过 20 MB。")
    return ext, content


def read_duration(value, message):
    """把浏览器上报的时长转成秒数。"""
    try:
        return float(value)
    except (ValueError, TypeError):
        raise VoiceError(message) from None


def read_sample(file, duration, prompt=False):
    ext, content = read_audio_bytes(file, ("mp3", "m4a", "wav"), "音频")
    if ext == "wav":
        try:
            with wave.open(io.BytesIO(content)) as stream:
                duration = stream.getnframes() / stream.getframerate()
        except (wave.Error, EOFError, ZeroDivisionError):
            raise VoiceError("WAV 文件无效，请使用标准 PCM WAV 或改用 MP3/M4A。") from None
    else:
        if ext == "m4a":
            require(content[4:8] == b"ftyp", "文件内容不是有效的 M4A 容器。")
        else:
            require(content.startswith(b"ID3") or (len(content) > 1 and content[0] == 255 and content[1] & 224 == 224), "文件内容不是有效的 MP3。")
        duration = read_duration(duration, "无法读取音频时长，请重新选择文件。")
    numeric(duration, 0.01, 300, "录音时长")
    require(duration < 8 if prompt else duration >= 10, "示例音频必须短于 8 秒。" if prompt else "复刻录音应为 10 秒至 5 分钟。")
    return ("recording." + ext, content, "application/octet-stream")


def validate_new_voice_id(voice_id):
    require(re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{6,254}[A-Za-z0-9]", voice_id),
            "音色 ID 应为 8–256 位，以字母开头、字母或数字结尾，只能使用字母、数字、下划线和短横线。")


def read_cover_audio(file, duration):
    """校验翻唱参考音频；云端要求 6 秒–6 分钟、最大 50 MB。"""
    _, content = read_audio_bytes(file, COVER_AUDIO_EXTS, "参考音频")
    duration = read_duration(duration, "无法读取参考音频时长，请重新选择文件。")
    numeric(duration, 5.9, 361, "参考音频时长")
    return content


def decode_music_audio(value):
    """兼容 output_format=url 的临时链接和 hex 内联音频，返回 (kind, payload)。"""
    if not isinstance(value, str) or not value.strip():
        return None
    value = value.strip()
    if value.startswith("https://"):
        return "url", value
    if len(value) % 2 or len(value) < 2048:
        return None
    try:
        content = bytes.fromhex(value)
    except ValueError:
        return None
    return ("hex", content) if content else None


class MiniMaxClient:
    def __init__(self, settings, api_key=None, region=None, timeout=None):
        # 独立凭据的能力（如音乐生成）可覆盖密钥、区域和超时；缺省时沿用 settings.minimax_*。
        self.region = region or settings.minimax_region
        require(self.region in HOSTS, "minimax.region 只能配置 cn 或 intl。")
        self.key = api_key if api_key is not None else settings.minimax_api_key
        self.base_url = HOSTS[self.region]
        self.timeout = numeric(settings.minimax_timeout_seconds if timeout is None else timeout, 10, 240, "请求超时")

    @property
    def ready(self):
        return bool(self.key) and not any(mark in self.key for mark in ("<", ">", "填入", "YOUR_"))

    def request(self, endpoint, payload=None, files=None, purpose=None):
        if not self.ready:
            raise VoiceError("请在后端配置的 [minimax] 段填入 API Key，或设置 MINIMAX_API_KEY，然后重启后端。", 409)
        try:
            response = requests.post(
                self.base_url + endpoint,
                headers={"Authorization": "Bearer " + self.key},
                json=payload if files is None else None,
                data={"purpose": purpose} if files is not None else None,
                files=files, timeout=(10, self.timeout), allow_redirects=False,
            )
        except requests.RequestException:
            raise VoiceError("未取得确定的云端结果。复刻或合成可能已执行，请先检查记录，避免立即重复提交。", 502, uncertain=True) from None
        try:
            result = response.json()
        except ValueError:
            raise VoiceError(f"MiniMax 返回 HTTP {response.status_code}，未提供有效 JSON。请核对密钥站点和接口权限。", 502, uncertain=response.status_code >= 500) from None
        base = result.get("base_resp") if isinstance(result, dict) else None
        if not isinstance(base, dict) or "status_code" not in base:
            raise VoiceError("MiniMax 响应缺少业务状态码，请检查密钥权限及接口。", 502, uncertain=True)
        code = base["status_code"]
        if code != 0:
            msg = str(base.get("status_msg", "请求失败"))[:500].replace(self.key, "[已隐藏密钥]")
            hint = {
                1004: "请核对密钥站点、套餐和语音接口权限。",
                2038: "账号无复刻权限，请完成 MiniMax 个人或企业认证并确认权限。",
                1002: "已触发限流，请稍后手动重试。",
                1039: "已触发字符速率限制，请稍后手动重试。",
                1001: "请先检查云端结果，避免重复计费。",
                1008: "账号余额不足，请充值后重试。",
                1026: "内容未通过官方审核，请调整描述或歌词。",
                2013: "入参不符合接口要求，请检查风格描述、歌词长度和音频格式。",
                2153: "该密钥为新用户账号，官方已停止向新用户提供音乐与歌词生成接口，需改用历史付费账号的密钥。",
            }.get(code, "请检查套餐权限、额度和请求参数。")
            raise VoiceError(f"MiniMax {code}：{msg} {hint}", 502, code, code == 1001)
        if not 200 <= response.status_code < 300:
            raise VoiceError(f"MiniMax 返回 HTTP {response.status_code}。", 502, response.status_code)
        return result

    def upload(self, sample, purpose):
        result = self.request("/v1/files/upload", files={"file": sample}, purpose=purpose)
        file_id = (result.get("file") or {}).get("file_id")
        require(str(file_id).isdigit(), "上传响应缺少 file_id，请检查云端文件记录。")
        return int(file_id)

    def download_audio(self, url):
        # URL 只取自 MiniMax 响应；拒绝内网地址与重定向，不向 CDN 发送 API Key。
        parsed = urlsplit(url)
        require(parsed.scheme == "https" and parsed.hostname and not parsed.username and not parsed.password
                and parsed.port in (None, 443), "MiniMax 音频下载地址格式无效。")
        try:
            addresses = socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)
            require(bool(addresses) and all(ipaddress.ip_address(row[4][0]).is_global for row in addresses), "音频链接不能指向本地或内网地址。")
            with requests.get(url, timeout=(10, self.timeout), stream=True, allow_redirects=False) as response:
                response.raise_for_status()
                require(response.status_code == 200, "音频下载地址返回了重定向。")
                chunks, size = [], 0
                for chunk in response.iter_content(65536):
                    size += len(chunk)
                    require(size <= 64 * 1024 * 1024, "生成音频超过本地保存限制（64 MB）。")
                    chunks.append(chunk)
                content = b"".join(chunks)
                require(bool(content), "音频下载结果为空。")
                return content
        except (requests.RequestException, OSError):
            raise VoiceError("云端音频已生成，但本地下载未完成。音频链接和正文已入库，请在记录中重试下载，无需重新生成。", 502) from None
