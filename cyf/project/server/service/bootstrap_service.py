import threading

from conf.runtime import runtime_state
from model.db import init_db
from model.entities import ALL_MODELS, User
from service.host_service import start_blacklist_cleanup_thread
from service.model_service import invalidate_model_cache, seconds_until_next


def initialize_database():
    init_db(ALL_MODELS, User)


def run_model_meta_refresh(logger, reason: str):
    try:
        from init.init_model_meta import init_model_meta_data

        init_model_meta_data()
        invalidate_model_cache(reason=reason, logger=logger)
        logger.info(f"模型元数据定时刷新成功，reason={reason}")
    except Exception as exc:
        logger.error(f"模型元数据定时刷新失败，reason={reason}, err={exc}")


def schedule_next_model_meta_refresh(logger):
    wait_seconds = seconds_until_next(runtime_state.settings.meta_refresh_hour, runtime_state.settings.meta_refresh_minute)
    logger.info(
        f"模型元数据定时任务将在 {wait_seconds}s 后执行，下次时间: "
        f"{runtime_state.settings.meta_refresh_hour:02d}:{runtime_state.settings.meta_refresh_minute:02d}"
    )

    def _job():
        run_model_meta_refresh(logger, "daily_schedule")
        schedule_next_model_meta_refresh(logger)

    timer = threading.Timer(wait_seconds, _job)
    timer.daemon = True
    timer.name = "model-meta-refresh-timer"
    with runtime_state.model_meta_timer_lock:
        runtime_state.model_meta_timer = timer
    timer.start()


def start_model_meta_scheduler(logger):
    if runtime_state.settings.meta_refresh_on_startup:
        run_model_meta_refresh(logger, "startup_refresh")
    schedule_next_model_meta_refresh(logger)


def bootstrap_runtime(logger):
    initialize_database()
    runtime_state.build_clients()
    start_blacklist_cleanup_thread()
    start_model_meta_scheduler(logger)
