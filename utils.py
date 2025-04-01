import httpx
import logging
from typing import Optional

YANDEX_DIRECT_API_URL = "https://api.direct.yandex.ru/json/v5/"

logger = logging.getLogger(__name__)

async def request_yandex_direct(
    method: str, token: str, resource: str, params: Optional[dict] = None
) -> Optional[dict]:
    """Отправляет запрос в Яндекс.Директ API с динамическим указанием ресурса."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept-Language": "ru",
    }

    url = f"{YANDEX_DIRECT_API_URL}{resource}"

    data = {
        "method": method,
        "params": params if params else {}
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=data, headers=headers)

            logger.info(f"Запрос в Яндекс.Директ: {url}, статус: {response.status_code}")
            logger.debug(f"Заголовки ответа: {response.headers}")

            if response.status_code != 200:
                logger.error(f"Ошибка в запросе к Yandex Direct: {response.status_code} - {response.text}")
                return None

            if not response.text.strip():
                logger.error("Пустой ответ от Yandex Direct")
                return None

            try:
                json_response = response.json()
                logger.debug(f"Ответ от Яндекс.Директ: {json_response}")
                return json_response
            except Exception as e:
                logger.error(f"Ошибка парсинга JSON: {e}, ответ: {response.text}")
                return None

    except httpx.RequestError as e:
        logger.error(f"Ошибка сети при обращении к Yandex Direct API: {e}")
        return None
