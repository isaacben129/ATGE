"""APScheduler: daily generation, hourly publish, performance ingestion, weekly review."""
import logging
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from atg_engine.config.settings import (
    DAILY_GENERATION_CRON,
    PERFORMANCE_INTERVAL_HOURS,
    PUBLISHING_INTERVAL_HOURS,
    TRENDING_CONTENT_CRON,
    WEEKLY_REVIEW_CRON,
)

# Configure logging - Railway-friendly (500 logs/sec limit)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger(__name__)


def _parse_cron(cron_str: str) -> dict:
    """Parse 'min hour * * *' or 'min hour * * dow' into CronTrigger kwargs."""
    parts = cron_str.strip().split()
    if len(parts) < 5:
        return {"minute": "0", "hour": "8", "day_of_week": "*"}
    return {
        "minute": parts[0],
        "hour": parts[1],
        "day": parts[2] if len(parts) > 2 else "*",
        "month": parts[3] if len(parts) > 3 else "*",
        "day_of_week": parts[4] if len(parts) > 4 else "*",
    }


def run_daily_job():
    from atg_engine.pipelines.daily_generation import run
    logger.info("Starting daily generation job...")
    try:
        result = run()
        # Log summary only (not full result to avoid log spam)
        if result:
            result_lines = result.split('\n')
            summary = result_lines[0] if result_lines else "Completed"
            logger.info("Daily generation completed: %s", summary[:200])  # Limit length
    except Exception as e:
        logger.exception("Daily generation failed: %s", e)


def run_publish_job():
    from atg_engine.pipelines.publishing import run
    logger.info("Starting publishing job...")
    try:
        result = run()
        # Log summary only (not full result to avoid log spam)
        if result:
            result_lines = result.split('\n')
            summary = result_lines[0] if result_lines else "Completed"
            logger.info("Publishing completed: %s", summary[:200])  # Limit length
    except Exception as e:
        logger.exception("Publishing failed: %s", e)


def run_analytics_job():
    from atg_engine.pipelines.performance_ingestion import run
    logger.info("Starting analytics/performance ingestion job...")
    try:
        result = run()
        # Log summary only (not full result to avoid log spam)
        if result:
            result_lines = result.split('\n')
            summary = result_lines[0] if result_lines else "Completed"
            logger.info("Analytics ingestion completed: %s", summary[:200])  # Limit length
    except Exception as e:
        logger.exception("Performance ingestion failed: %s", e)


def run_weekly_job():
    from atg_engine.pipelines.weekly_review import run
    logger.info("Starting weekly review job...")
    try:
        result = run()
        # Log summary only (not full result to avoid log spam)
        if result:
            result_lines = result.split('\n')
            summary = result_lines[0] if result_lines else "Completed"
            logger.info("Weekly review completed: %s", summary[:200])  # Limit length
    except Exception as e:
        logger.exception("Weekly review failed: %s", e)


def run_trending_job():
    from atg_engine.pipelines.trending_content_pipeline import run
    logger.info("Starting trending content discovery job...")
    try:
        result = run()
        # Log summary only (not full result to avoid log spam)
        if result:
            result_lines = result.split('\n')
            summary = result_lines[0] if result_lines else "Completed"
            logger.info("Trending content discovery completed: %s", summary[:200])  # Limit length
    except Exception as e:
        logger.exception("Trending content discovery failed: %s", e)


def start_scheduler():
    """Start the blocking scheduler with all pipeline jobs."""
    from atg_engine.db.init_db import init_db
    try:
        init_db()
    except Exception:
        logger.exception("DB init failed, scheduler starting anyway.")
    # Pre-import CrewAI in main thread so its telemetry can register signal handlers (avoids "signal only works in main thread" when jobs run in worker threads)
    import crewai  # noqa: F401
    scheduler = BlockingScheduler()
    c = _parse_cron(DAILY_GENERATION_CRON)
    scheduler.add_job(run_daily_job, CronTrigger(minute=c["minute"], hour=c["hour"], day_of_week=c["day_of_week"]))
    scheduler.add_job(run_publish_job, IntervalTrigger(hours=PUBLISHING_INTERVAL_HOURS))
    scheduler.add_job(run_analytics_job, IntervalTrigger(hours=PERFORMANCE_INTERVAL_HOURS))
    w = _parse_cron(WEEKLY_REVIEW_CRON)
    scheduler.add_job(run_weekly_job, CronTrigger(minute=w["minute"], hour=w["hour"], day_of_week=w["day_of_week"]))
    t = _parse_cron(TRENDING_CONTENT_CRON)
    scheduler.add_job(run_trending_job, CronTrigger(minute=t["minute"], hour=t["hour"], day_of_week=t["day_of_week"]))
    logger.info("Scheduler started: daily=%s, publish=%sh, analytics=%sh, weekly=%s, trending=%s",
                DAILY_GENERATION_CRON, PUBLISHING_INTERVAL_HOURS, PERFORMANCE_INTERVAL_HOURS, WEEKLY_REVIEW_CRON, TRENDING_CONTENT_CRON)
    try:
        scheduler.start()
    except Exception:
        logger.exception("Scheduler failed to start or stopped with an error.")
        raise
