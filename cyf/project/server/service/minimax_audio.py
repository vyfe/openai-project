"""MiniMax 生成音频的本地缓存：临时链接落盘并回写记录状态。"""
import os
from datetime import datetime

from service.minimax_client import require


def cache_audio(store, client, record, subdir, inline=None):
    """把云端音频写入 <凭据目录>/<subdir> 并标记记录就绪。

    inline 用于 hex 内联音频；为 None 时从云端临时链接下载。
    """
    if inline is None:
        require(record.audio_url and record.url_expires_at and record.url_expires_at > datetime.utcnow(),
                "云端临时链接已过期，且本地尚未保存该音频。")
        audio = client.download_audio(record.audio_url)
    else:
        audio = inline
    folder = store.folder / subdir
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = folder / (record.id + ".mp3")
    temporary = path.with_suffix(".tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(audio)
    os.replace(temporary, path)
    record.size, record.status, record.error_message = len(audio), "ready", None
    record.save()
