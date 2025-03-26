from fastapi import Depends, HTTPException, APIRouter
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from database import get_db
from Users.models import User
import logging

from utils import request_yandex_direct

router = APIRouter()

# Явный URL для запроса кампаний в Яндекс.Директ
YANDEX_DIRECT_API_URL = "https://api-sandbox.direct.yandex.com/json/v5/"

logger = logging.getLogger(__name__)


@router.get("/yandex/direct/campaigns")
async def get_yandex_campaigns(user_id: int, db: AsyncSession = Depends(get_db)):
    """Получение списка кампаний пользователя в Яндекс.Директ."""

    # Ищем пользователя по ID
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()

    if not user or not user.access_token:
        raise HTTPException(status_code=403, detail="Пользователь не авторизован в Яндексе")

    # Делаем запрос в Яндекс.Директ API
    response = await request_yandex_direct("get", user.access_token, {
        "SelectionCriteria": {},  # Все кампании
        "FieldNames": ["Id", "Name", "Status"]
    })

    if not response:
        raise HTTPException(status_code=500, detail="Ошибка при получении данных из Яндекс.Директ")

    return response
