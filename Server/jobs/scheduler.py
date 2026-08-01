from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from jobs.email_jobs import send_weekly_summaries, send_monthly_performance
from jobs.cleanup_jobs import cleanup_security_state, expire_unused_invites
from jobs.reconcile_job import run_daily_reconciliation
from jobs.ai_rebalance import run_auto_rebalance
from jobs.pnl_job import run_daily_pnl_snapshot
from config import settings


scheduler = BackgroundScheduler(timezone=settings.SCHEDULER_TIMEZONE)


def start_scheduler():
    from jobs.migration_job import run_pending_migrations
    run_pending_migrations()

    scheduler.add_job(
        send_weekly_summaries,
        CronTrigger(day_of_week="mon", hour=9, minute=0),
        id="weekly_email_summary",
        replace_existing=True,
    )

    scheduler.add_job(
        send_monthly_performance,
        CronTrigger(day=1, hour=9, minute=0),
        id="monthly_performance_report",
        replace_existing=True,
    )

    scheduler.add_job(
        expire_unused_invites,
        CronTrigger(hour=3, minute=0),
        id="expire_invites_cleanup",
        replace_existing=True,
    )

    scheduler.add_job(
        cleanup_security_state,
        CronTrigger(hour=3, minute=15),
        id="security_state_cleanup",
        replace_existing=True,
    )

    scheduler.add_job(
        run_daily_reconciliation,
        CronTrigger(hour=4, minute=0),
        id="daily_reconciliation",
        replace_existing=True,
    )

    scheduler.add_job(
        run_daily_reconciliation,
        IntervalTrigger(minutes=1),
        id="order_fill_reconciliation",
        replace_existing=True,
    )

    if settings.ENABLE_AUTOMATED_TRADING.lower() == "true":
        scheduler.add_job(
            run_auto_rebalance,
            CronTrigger(day_of_week="sun", hour=10, minute=0),
            id="weekly_auto_rebalance",
            replace_existing=True,
        )

    scheduler.add_job(
        run_daily_pnl_snapshot,
        CronTrigger(hour=22, minute=0),
        id="daily_pnl_snapshot",
        replace_existing=True,
    )

    scheduler.start()


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
