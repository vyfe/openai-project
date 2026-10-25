"""音色保活定时器：复刻音色 7 天内没有正式调用会被官方删除，每日补一次短文本合成。"""
import threading

from service.minimax_voice_service import MiniMaxVoiceService
from service.time_utils import seconds_until_next

_TIMER = None
_LOCK = threading.Lock()


def _run_and_reschedule(logger):
    delay = 3600
    try:
        service = MiniMaxVoiceService()
        status = service.keepalive_status()
        if status["enabled"]:
            result = service.run_keepalive()
            if result["attempted"]:
                logger.info("音色保活完成，本次激活 %s 个音色", result["attempted"])
        delay = seconds_until_next(status["hour"], status["minute"])
        logger.info("下次音色保活将在 %s 秒后执行", delay)
    except Exception as exc:
        logger.error("音色保活任务失败: %s", exc)
    _schedule(delay, logger)


def _schedule(delay, logger):
    global _TIMER
    with _LOCK:
        if _TIMER:
            _TIMER.cancel()
        _TIMER = threading.Timer(delay, _run_and_reschedule, args=(logger,))
        _TIMER.daemon = True
        _TIMER.name = "minimax-keepalive-timer"
        _TIMER.start()


def start_keepalive_scheduler(logger):
    try:
        status = MiniMaxVoiceService().keepalive_status()
    except Exception as exc:
        logger.error("音色保活定时器启动失败: %s", exc)
        return
    delay = seconds_until_next(status["hour"], status["minute"])
    logger.info("音色保活定时任务将在 %s 秒后执行", delay)
    _schedule(delay, logger)
