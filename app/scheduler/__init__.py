from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.config import settings
from app.scheduler.jobs import (
    detect_calendar_conflicts_job,
    evaluate_due_items,
    scan_inbox_job,
    send_daily_digest,
    sync_transactions_job,
)

_scheduler: BackgroundScheduler | None = None


def start_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    jobstores = {"default": SQLAlchemyJobStore(url="sqlite:///./scheduler.db")}
    scheduler = BackgroundScheduler(jobstores=jobstores, timezone=settings.timezone)
    scheduler.add_job(
        evaluate_due_items,
        trigger=IntervalTrigger(minutes=15),
        id="evaluate_due_items",
        replace_existing=True,
    )
    scheduler.add_job(
        send_daily_digest,
        trigger=CronTrigger(hour=7, minute=0),
        id="send_daily_digest",
        replace_existing=True,
    )
    scheduler.add_job(
        sync_transactions_job,
        trigger=IntervalTrigger(hours=1),
        id="sync_transactions_job",
        replace_existing=True,
    )
    scheduler.add_job(
        scan_inbox_job,
        trigger=IntervalTrigger(minutes=30),
        id="scan_inbox_job",
        replace_existing=True,
    )
    scheduler.add_job(
        detect_calendar_conflicts_job,
        trigger=IntervalTrigger(hours=1),
        id="detect_calendar_conflicts_job",
        replace_existing=True,
    )
    scheduler.start()
    _scheduler = scheduler
    return scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
