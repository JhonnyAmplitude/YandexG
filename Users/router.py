import os
import httpx
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from dotenv import load_dotenv
from database import get_db
from Users.models import User
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

router = APIRouter()

YANDEX_CLIENT_ID = os.getenv("YANDEX_CLIENT_ID")
YANDEX_CLIENT_SECRET = os.getenv("YANDEX_CLIENT_SECRET")
YANDEX_REDIRECT_URI = "http://localhost:8000/auth/callback"

YANDEX_AUTH_URL = "https://oauth.yandex.ru/authorize"
YANDEX_TOKEN_URL = "https://oauth.yandex.ru/token"
YANDEX_USER_INFO_URL = "https://login.yandex.ru/info"

@router.get("/auth/login")
def login():
    auth_url = (
        f"{YANDEX_AUTH_URL}?response_type=code"
        f"&client_id={YANDEX_CLIENT_ID}"
        f"&redirect_uri={YANDEX_REDIRECT_URI}"
    )
    logger.info(f"Auth URL generated: {auth_url}")
    return {"auth_url": auth_url}

@router.get("/auth/callback")
async def auth_callback(code: str, db: AsyncSession = Depends(get_db)):
    logger.info(f"Received code: {code}")

    data = {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": YANDEX_CLIENT_ID,
        "client_secret": YANDEX_CLIENT_SECRET,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(YANDEX_TOKEN_URL, data=data, headers=headers)
            if response.status_code != 200:
                logger.error(f"Failed to get token: {response.text}")
                raise HTTPException(status_code=400, detail="Ошибка получения токена")

            tokens = response.json()
            access_token = tokens.get("access_token")
            refresh_token = tokens.get("refresh_token")
            logger.info(f"Access token obtained: {access_token}")

            user_info_response = await client.get(
                YANDEX_USER_INFO_URL, headers={"Authorization": f"OAuth {access_token}"}
            )
            if user_info_response.status_code != 200:
                logger.error(f"Failed to get user info: {user_info_response.text}")
                raise HTTPException(status_code=400, detail="Ошибка получения данных пользователя")

            user_info = user_info_response.json()
            logger.info(f"User info validated: id='{user_info['id']}' display_name='{user_info.get('display_name')}' login='{user_info.get('login')}'")

    except httpx.RequestError as e:
        logger.error(f"An error occurred while requesting data: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при запросе к сервисам Яндекса")

    if not user_info.get("id"):
        logger.error("Missing Yandex user ID.")
        raise HTTPException(status_code=400, detail="Отсутствует ID пользователя Яндекса")

    if not access_token or not refresh_token:
        logger.error("Missing access or refresh token.")
        raise HTTPException(status_code=400, detail="Отсутствуют токены доступа")

    try:
        # Проверяем, есть ли пользователь в базе
        existing_user_result = await db.execute(select(User).where(User.yandex_id == user_info["id"]))
        existing_user = existing_user_result.scalars().first()

        login = user_info.get("login", "")
        display_name = user_info.get("display_name", "")

        if existing_user:
            logger.info(f"Existing user found: {existing_user}")

            # Проверяем, есть ли у пользователя пустые поля и обновляем их
            updated = False
            if not existing_user.login and login:
                existing_user.login = login
                updated = True
            if not existing_user.display_name and display_name:
                existing_user.display_name = display_name
                updated = True
            if not existing_user.access_token or existing_user.access_token != access_token:
                existing_user.access_token = access_token
                updated = True
            if not existing_user.refresh_token or existing_user.refresh_token != refresh_token:
                existing_user.refresh_token = refresh_token
                updated = True

            if updated:
                await db.commit()
                await db.refresh(existing_user)
                logger.info("User data updated in database.")

            return {"message": "Пользователь уже авторизован.", "user": user_info}

        # Если пользователя нет, создаем нового
        new_user = User(
            yandex_id=user_info["id"],
            client_id=user_info.get("client_id", ""),
            login=login,
            display_name=display_name,
            access_token=access_token,
            refresh_token=refresh_token,
            created_at=datetime.now(),
        )

        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
        logger.info(f"New user saved: {new_user}")

    except Exception as e:
        logger.error(f"Error while handling database transaction: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Ошибка при сохранении данных пользователя")

    return {
        "user": user_info,
        "access_token": access_token,
        "message": "Пользователь успешно авторизован и сохранен в базе данных."
    }
