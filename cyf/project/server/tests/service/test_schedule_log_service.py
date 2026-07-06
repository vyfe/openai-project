import os
import time


def test_cleanup_expired_schedule_logs_uses_quant_retention(test_settings):
    from service.quant.schedule_log_service import cleanup_expired_schedule_logs

    log_dir = test_settings.quant_schedule_log_dir
    os.makedirs(log_dir, exist_ok=True)

    old_log = os.path.join(log_dir, "schedule-run-100-20260101T000000.log")
    old_gz = os.path.join(log_dir, "schedule-run-101-20260101T000000.log.gz")
    fresh_log = os.path.join(log_dir, "schedule-run-102-20260705T000000.log")
    unrelated = os.path.join(log_dir, "manual-note.log")

    for path in (old_log, old_gz, fresh_log, unrelated):
        with open(path, "w", encoding="utf-8") as fp:
            fp.write("test\n")

    old_mtime = time.time() - 3 * 24 * 60 * 60
    fresh_mtime = time.time()
    for path in (old_log, old_gz, unrelated):
        os.utime(path, (old_mtime, old_mtime))
    os.utime(fresh_log, (fresh_mtime, fresh_mtime))

    removed = cleanup_expired_schedule_logs()

    assert removed >= 2
    assert not os.path.exists(old_log)
    assert not os.path.exists(old_gz)
    assert os.path.exists(fresh_log)
    assert os.path.exists(unrelated)
