"""按 MiniMax 凭据隔离的本地存储目录、文件锁与 JSON 台账。"""
import fcntl
import hashlib
import os
from contextlib import contextmanager
from pathlib import Path

from service.minimax_client import VoiceError


class MiniMaxStore:
    """同一凭据共享一个根目录；台账读写由调用方注入，语音与音乐各自落库。"""

    def __init__(self, settings, api_key=None, region=None, state_loader=None, state_saver=None):
        root = Path(settings.minimax_storage_dir)
        if not root.is_absolute():
            root = Path(settings.base_dir) / root
        # 凭据指纹决定数据隔离：独立凭据的能力（如音乐）使用自己的 scope 目录。
        credential_region = region or settings.minimax_region
        credential_key = api_key if api_key is not None else settings.minimax_api_key
        self.scope = hashlib.sha256((credential_region + ":" + credential_key).encode()).hexdigest()[:24]
        self.folder = root / self.scope
        self.folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._state_loader = state_loader
        self._state_saver = state_saver

    @contextmanager
    def locked(self, name="state", blocking=True):
        # 分离长时间云端操作锁与短时台账锁；兼容多线程/多 uWSGI 进程。
        fd = os.open(self.folder / (name + ".lock"), os.O_CREAT | os.O_RDWR, 0o600)
        with os.fdopen(fd, "a") as stream:
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
            except BlockingIOError:
                raise VoiceError("另一个云端操作正在执行，请等待完成后再操作。", 409) from None
            try:
                yield
            finally:
                fcntl.flock(stream, fcntl.LOCK_UN)

    def read(self):
        if not self._state_loader:
            raise VoiceError("该存储未绑定台账。", 500)
        with self.locked():
            return self._state_loader(self.scope)

    def update(self, callback):
        if not (self._state_loader and self._state_saver):
            raise VoiceError("该存储未绑定台账。", 500)
        with self.locked():
            state = self._state_loader(self.scope)
            callback(state)
            self._state_saver(self.scope, state)
