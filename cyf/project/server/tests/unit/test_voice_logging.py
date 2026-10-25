"""语音接口的访问日志不采集录音、正文或临时下载链接。"""
import logging

from flask import Flask

from conf import logging_config
from conf.runtime_logging import request_body_var, response_body_var


def test_voice_payloads_are_omitted_even_at_debug(monkeypatch):
    app = Flask(__name__)
    observed = []
    monkeypatch.setattr(logging_config, "_runtime_level", lambda: logging.DEBUG)
    monkeypatch.setattr(logging.getLogger("llm.access"), "info", lambda *_: observed.append(
        (request_body_var.get(), response_body_var.get())))
    logging_config._register_request_logging(app)

    @app.post("/never_guess_my_usage/voice/echo")
    def voice_echo():
        # 无效 UTF-8 模拟二进制音频，DEBUG 日志也不能将它当作文本读取。
        return b"\xff\xfbPRIVATE_AUDIO", 200, {"Content-Type": "audio/mpeg"}

    response = app.test_client().post("/never_guess_my_usage/voice/echo", json={"text": "PRIVATE_STORY"})
    assert response.status_code == 200
    assert response.data == b"\xff\xfbPRIVATE_AUDIO"
    assert observed == [("", "")]
