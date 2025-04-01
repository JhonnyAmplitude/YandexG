from celery import Celery

celery_app = Celery(
    "reports",
    broker="redis://localhost:6379/0",  # Используем Redis как брокер сообщений
    backend="redis://localhost:6379/0"
)

celery_app.conf.task_routes = {"Reports.tasks.*": {"queue": "reports"}}
