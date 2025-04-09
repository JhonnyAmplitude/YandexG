from fastapi import Depends, HTTPException, APIRouter
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from src.database import get_db
from src.Users.models import User
import logging

from src.utils import request_yandex_direct

router = APIRouter()

logger = logging.getLogger(__name__)


@router.get("/yandex/direct/campaigns")
async def get_yandex_campaigns(user_id: int, db: AsyncSession = Depends(get_db), resource: str = "campaigns"):
    """Получение данных из Яндекс.Директ для указанного ресурса (например, кампании)."""

    # Ищем пользователя по ID
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()

    if not user or not user.access_token:
        logger.warning(f"Пользователь {user_id} не найден или не авторизован в Яндексе")
        raise HTTPException(status_code=403, detail="Пользователь не авторизован в Яндексе")

    # Делаем запрос в Яндекс.Директ API с динамическим ресурсом
    response = await request_yandex_direct("get", user.access_token, resource, {
        "SelectionCriteria": {},
        "FieldNames": ["Id", "Name", "Status", "ClientInfo", "ExcludedSites", "NegativeKeywords"]
    })

    if response is None:
        logger.error(f"Ошибка при получении данных из Яндекс.Директ для user_id={user_id}")
        raise HTTPException(status_code=500, detail="Ошибка при получении данных из Яндекс.Директ")

    return response

