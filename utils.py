import httpx
import logging
from typing import Optional


YANDEX_DIRECT_API_URL = "https://api-sandbox.direct.yandex.com/json/v5/"

logger = logging.getLogger(__name__)


async def request_yandex_direct(method: str, token: str, params: Optional[dict] = None) -> Optional[dict]:
    """Отправляет запрос в Яндекс.Директ API."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept-Language": "ru",
    }

    url = f"{YANDEX_DIRECT_API_URL}campaigns"  # Указываем правильный ресурс (campaigns)

    data = {
        "method": method,  # Добавляем method в тело запроса
        "params": params if params else {}
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=data, headers=headers)

            if response.status_code != 200:
                logger.error(f"Ошибка в запросе к Яндекс.Директ: {response.status_code} - {response.text}")
                return None

            return response.json()

    except httpx.RequestError as e:
        logger.error(f"Ошибка при обращении к Яндекс.Директ API: {e}")
        return None
