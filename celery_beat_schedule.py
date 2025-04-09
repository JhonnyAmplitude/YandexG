from celery.schedules import crontab
from src.ReportsDirect import celery_app

celery_app.conf.beat_schedule = {
    "update_reports_cache_daily": {
        "task": "update_reports_cache",
        "schedule": crontab(hour=0, minute=0),  # Запускать каждый день в 00:00
    },
}
