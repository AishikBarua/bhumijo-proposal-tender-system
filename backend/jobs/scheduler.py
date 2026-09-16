"""
The night shift. Runs the jobs on a timer inside the server process, so
nothing depends on anyone remembering to start a script.

Deliberately simple — a thread and a clock. No extra dependency, and it does
the one thing needed: run these jobs once a day at roughly the right hour.
"""

from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta

from ..config import get_logger
from . import backup, deadline_alerts, weekly_digest

log = get_logger("jobs.scheduler")

# hour of the day (24h, local time) -> job
DAILY_JOBS = {
    2: ("nightly backup", backup.run),
    7: ("deadline alerts", deadline_alerts.run),
}
WEEKLY_JOB_DAY = 0        # Monday
WEEKLY_JOB_HOUR = 8

_stop = threading.Event()
_thread: threading.Thread | None = None


def _run_safely(name: str, fn) -> None:
    try:
        log.info("running job: %s", name)
        fn()
    except Exception:  # noqa: BLE001 — a failed job must not kill the server
        log.exception("job failed: %s", name)


def _loop() -> None:
    last_run: dict[str, str] = {}

    while not _stop.is_set():
        now = datetime.now()
        today = now.date().isoformat()

        for hour, (name, fn) in DAILY_JOBS.items():
            if now.hour == hour and last_run.get(name) != today:
                last_run[name] = today
                _run_safely(name, fn)

        if (now.weekday() == WEEKLY_JOB_DAY and now.hour == WEEKLY_JOB_HOUR
                and last_run.get("weekly digest") != today):
            last_run["weekly digest"] = today
            _run_safely("weekly digest", weekly_digest.run)

        # Check every few minutes; precision to the minute is not needed.
        _stop.wait(300)


def start() -> None:
    global _thread
    if _thread is not None and _thread.is_alive():
        return
    _stop.clear()
    _thread = threading.Thread(target=_loop, name="bhumijo-scheduler", daemon=True)
    _thread.start()

    ok, message = backup.verify_destination()
    log.info("scheduler started — backup at 02:00, deadlines at 07:00, digest Mondays 08:00")
    (log.info if ok else log.warning)(message)


def stop() -> None:
    _stop.set()
    if _thread is not None:
        _thread.join(timeout=2)
