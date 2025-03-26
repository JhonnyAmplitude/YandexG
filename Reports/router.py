import httpx
import logging
import asyncio
import json
from fastapi import Depends, HTTPException, APIRouter
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from datetime import datetime
from database import get_db
from Users.models import User

YANDEX_DIRECT_API_URL = "https://api-sandbox.direct.yandex.com/json/v5/reports"

logger = logging.getLogger(__name__)
router = APIRouter()

def parse_tsv_report(report_text):
    """
    Разбирает ответ в формате TSV и возвращает список словарей.
    """
    try:
        lines = report_text.strip().split("\n")  # Разбиваем текст по строкам
        if len(lines) < 3:
            raise ValueError("Ответ содержит недостаточно строк.")

        headers = lines[1].split("\t")  # Вторая строка — заголовки колонок
        data_rows = lines[2:-1]  # Данные, кроме заголовка и итоговой строки

        parsed_data = []
        for row in data_rows:
            values = row.split("\t")
            parsed_data.append(dict(zip(headers, values)))

        return parsed_data
    except Exception as e:
        logger.error(f"Ошибка при разборе TSV: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при обработке отчета")

@router.get("/yandex-reports/{user_id}", summary="Получить отчет из Яндекс.Директ")
async def get_yandex_reports(user_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()

    if not user or not user.access_token:
        logger.error("Пользователь не авторизован в Яндексе или access_token отсутствует")
        raise HTTPException(status_code=403, detail="Пользователь не авторизован в Яндексе")

    logger.info(f"Используем access_token: {user.access_token}")

    report_name = f"report_{datetime.now().strftime('%Y%m%d%H%M%S')}"

    request_params = {
        "params": {
            "ReportName": report_name,
            "SelectionCriteria": {},
            "FieldNames": ["CampaignId","Date", "CampaignName", "Impressions", "Clicks", "Cost"],
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

    logger.info(f"Параметры запроса: {json.dumps(request_params, indent=4, ensure_ascii=False)}")

    # --- Запрос отчета ---
    async with httpx.AsyncClient() as client:
        response = await client.post(YANDEX_DIRECT_API_URL, headers=headers, json=request_params)

    if response.status_code == 400:
        logger.error(f"Ошибка 400: {response.text}")
        raise HTTPException(status_code=400, detail="Некорректные параметры запроса")

    elif response.status_code == 200:
        logger.info("Отчет готов и получен мгновенно")
        return parse_tsv_report(response.text)  # Парсим TSV

    elif response.status_code in (201, 202):
        retry_in = int(response.headers.get("retryIn", 60))
        request_id = response.headers.get("RequestId", "Нет данных")
        logger.info(f"Отчет поставлен в очередь. RequestId: {request_id}. Повторный запрос через {retry_in} секунд.")
    else:
        logger.error(f"Неизвестный статус-код: {response.status_code}, ответ: {response.text}")
        raise HTTPException(status_code=500, detail="Ошибка в API Яндекса")

    # --- Ожидание готовности отчета ---
    for attempt in range(10):  # До 10 попыток
        await asyncio.sleep(retry_in)
        async with httpx.AsyncClient() as client:
            status_response = await client.post(YANDEX_DIRECT_API_URL, headers=headers, json=request_params)

        if status_response.status_code == 200:
            logger.info("Отчет успешно сформирован в режиме онлайн")
            return parse_tsv_report(status_response.text)  # Парсим TSV
        elif status_response.status_code == 202:
            retry_in = int(status_response.headers.get("retryIn", 60))
            logger.info(f"Отчет еще формируется, ждем {retry_in} секунд...")
        else:
            logger.error(f"Ошибка при проверке статуса отчета: {status_response.text}")
            raise HTTPException(status_code=500, detail="Ошибка при получении статуса отчета")

    raise HTTPException(status_code=500, detail="Отчет не был обработан в течение времени ожидания")
