import httpx
import logging
import json
import redis.asyncio as redis
import asyncio

from datetime import datetime, timedelta
from fastapi import Depends, HTTPException, APIRouter, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from src.database import get_db
from src.Users.models import User

YANDEX_DIRECT_API_URL = "https://api.direct.yandex.com/json/v5/reports"
CACHE_TTL = 86400  # 24 часа

logger = logging.getLogger(__name__)
router = APIRouter()


async def get_redis():
    try:
        return redis.Redis(host="localhost", port=6380, decode_responses=True)
    except redis.exceptions.ConnectionError as e:
        logger.error(f"Ошибка подключения к Redis: {e}")
        raise HTTPException(status_code=500, detail="Ошибка подключения к Redis")


async def get_cached_report(redis_client, user_id):
    cache_key = f"yandex_report_{user_id}"
    metadata_key = f"yandex_report_metadata_{user_id}"

    cached_report = await redis_client.get(cache_key)
    metadata = await redis_client.get(metadata_key)

    if cached_report and metadata:
        last_updated = datetime.fromisoformat(json.loads(metadata)["last_updated"])
        now = datetime.utcnow()
        if now - last_updated < timedelta(hours=24):
            logger.info("Данные загружены из кэша")
            return json.loads(cached_report)

    return None


async def update_cache(redis_client, user_id, report_data):
    cache_key = f"yandex_report_{user_id}"
    metadata_key = f"yandex_report_metadata_{user_id}"

    now = datetime.utcnow().isoformat()
    metadata = {"last_updated": now}

    await redis_client.setex(cache_key, CACHE_TTL, json.dumps(report_data))
    await redis_client.setex(metadata_key, CACHE_TTL, json.dumps(metadata))


async def fetch_yandex_report(user):
    request_params = {
        "params": {
            "ReportName": f"report_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "SelectionCriteria": {},
            "FieldNames": ["CampaignId", "Date", "CampaignName", "Impressions", "Clicks",
                           "Cost"],
            "ReportType": "CAMPAIGN_PERFORMANCE_REPORT",
            "DateRangeType": "LAST_30_DAYS",
            "Format": "TSV",
            "IncludeVAT": "NO",
            "IncludeDiscount": "NO",
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
    elif response.status_code in (201, 202):
        retry_in = response.headers.get("retryIn", 60)
        if retry_in:
            retry_in = int(retry_in)
        else:
            retry_in = 60  # Значение по умолчанию

        for _ in range(20):
            await asyncio.sleep(retry_in)
            async with httpx.AsyncClient() as client:
                status_response = await client.post(YANDEX_DIRECT_API_URL, headers=headers, json=request_params)

            if status_response.status_code == 200:
                return status_response.text

        logger.error(f"Отчет не был обработан вовремя. Ответ: {response.text}")
        raise HTTPException(status_code=500, detail="Отчет не был обработан вовремя")

    logger.error(f"Ошибка API Яндекса: {response.status_code}, Ответ: {response.text}")
    raise HTTPException(status_code=response.status_code, detail="Ошибка API Яндекса")


@router.get("/yandex-reports/{user_id}", summary="Получить отчет из Яндекс.Директ")
async def get_yandex_reports(user_id: int, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()

    if not user or not user.access_token:
        raise HTTPException(status_code=403, detail="Пользователь не авторизован в Яндексе")

    redis_client = await get_redis()
    cached_report = await get_cached_report(redis_client, user_id)

    if cached_report:
        background_tasks.add_task(refresh_cache_task, user_id, user)
        return cached_report

    try:
        raw_report = await fetch_yandex_report(user)
        parsed_report = parse_tsv_report(raw_report)
        await update_cache(redis_client, user_id, parsed_report)
        return parsed_report
    except Exception as e:
        logger.error(f"Ошибка при получении отчета: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при получении отчета")


@router.get("/yandex-reports-cache/{user_id}", summary="Получить отчет из кеша Redis")
async def get_yandex_report_from_cache(user_id: int):
    redis_client = await get_redis()
    cached_report = await get_cached_report(redis_client, user_id)

    if cached_report:
        return cached_report

    raise HTTPException(status_code=404, detail="Отчет не найден в кеше")


async def refresh_cache_task(user_id, user):
    """
    Фоновая задача для обновления кеша отчета.
    """
    logger.info(f"Фоновое обновление кеша для user_id: {user_id}")
    redis_client = await get_redis()

    try:
        raw_report = await fetch_yandex_report(user)
        parsed_report = parse_tsv_report(raw_report)
        await update_cache(redis_client, user_id, parsed_report)
    except Exception as e:
        logger.error(f"Ошибка при обновлении кеша для user_id {user_id}: {e}")


def parse_tsv_report(report_text):
    try:
        lines = report_text.strip().split("\n")
        if len(lines) < 3:
            raise ValueError("Ответ содержит недостаточно строк для обработки.")

        headers = lines[1].split("\t")
        data_rows = lines[2:-1]

        parsed_data = [dict(zip(headers, row.split("\t"))) for row in data_rows]
        return parsed_data
    except Exception as e:
        logger.error(f"Ошибка при разборе TSV: {e}. Ответ: {report_text}")
        raise HTTPException(status_code=500, detail=f"Ошибка при обработке отчета: {str(e)}")



@router.delete("/yandex-reports-cache/{user_id}", summary="Удалить кеш отчета из Redis")
async def delete_report_cache(user_id: int):
    redis_client = await get_redis()
    await redis_client.delete(f"yandex_report_{user_id}")
    await redis_client.delete(f"yandex_report_metadata_{user_id}")
    return {"message": "Кеш удален"}
