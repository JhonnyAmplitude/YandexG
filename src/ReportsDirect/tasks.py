import json
import httpx
import logging
from datetime import datetime
from src.ReportsDirect.celery import celery_app
from src.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from src.Users.models import User
import redis.asyncio as redis

logger = logging.getLogger(__name__)

YANDEX_DIRECT_API_URL = "https://api.direct.yandex.com/json/v5/reports"

async def get_redis():
    return redis.Redis(host="localhost", port=6379, decode_responses=True)

async def fetch_yandex_report(user):
    request_params = {
        "params": {
            "ReportName": f"report_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "SelectionCriteria": {},
            "FieldNames": ["CampaignId", "Date", "CampaignName", "Impressions", "Clicks", "Cost"],
            "ReportType": "CAMPAIGN_PERFORMANCE_REPORT",
            "DateRangeType": "LAST_30_DAYS",
            "Format": "TSV",
            "IncludeVAT": "NO",
            "IncludeDiscount": "NO"
        }
    }

    headers = {
        "Authorization": f"Bearer {user.access_token}",
        "Client-Login": user.login,
        "Accept-Language": "ru",
        "processingMode": "auto"
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(YANDEX_DIRECT_API_URL, headers=headers, json=request_params)

    if response.status_code == 200:
        return response.text
    else:
        logger.error(f"Ошибка API Яндекса: {response.text}")
        return None

@celery_app.task(name="update_reports_cache")
def update_reports_cache():
    """Обновляет кеш отчетов всех пользователей каждые 24 часа."""
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(update_cache_task())

async def update_cache_task():
    db: AsyncSession = next(get_db())
    redis_client = await get_redis()

    users = await db.execute(select(User))
    users = users.scalars().all()

    for user in users:
        if not user.access_token:
            continue

        report_data = await fetch_yandex_report(user)
        if report_data:
            cache_key = f"yandex_report_{user.id}"
            await redis_client.setex(cache_key, 86400, json.dumps(report_data))
            logger.info(f"Кеш обновлен для пользователя {user.id}")
