"""
APScheduler Setup
-----------------
Runs background jobs on a schedule. Currently:
  - Nightly deadline check at 8:00 AM UTC (start/stop tied to FastAPI lifespan)

Usage in main.py:
    from backend.services.scheduler import start_scheduler, stop_scheduler

    @asynccontextmanager
    async def lifespan(app):
        start_scheduler()
        yield
        stop_scheduler()
"""
import logging
import asyncio
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

_scheduler = BackgroundScheduler(timezone="UTC")


def _run_async(coro):
    """Run an async coroutine from a sync APScheduler job."""
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(coro)
    finally:
        loop.close()


def start_scheduler() -> None:
    from backend.services.notifications import run_nightly_check

    _scheduler.add_job(
        func=lambda: _run_async(run_nightly_check()),
        trigger=CronTrigger(hour=8, minute=0),   # 8:00 AM UTC daily
        id="nightly_deadline_check",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info("Scheduler started — nightly check at 08:00 UTC.")


def stop_scheduler() -> None:
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped.")
