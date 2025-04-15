from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel
from datetime import datetime, timedelta
import calendar
import requests
import os
from typing import List, Dict
from sqlalchemy.orm import Session
from src.database import get_db
from .models import GoalStat  # Импорт модели для сохранения в БД

router = APIRouter(
    prefix="/metrika_goals",
    tags=["Yandex Goals"]
)

YANDEX_OAUTH_TOKEN = os.getenv("API_TOKEN")
COUNTER_ID = 181494

# Цели, которые нужно отслеживать
INTERESTING_GOALS = [183338431, 91705897, 339342936]


class GoalInfo(BaseModel):
    id: int
    name: str
    type: str
    conversions: int


def get_goals(counter_id: int) -> list[dict]:
    url = f"https://api-metrika.yandex.net/management/v1/counter/{counter_id}/goals"
    headers = {"Authorization": f"OAuth {YANDEX_OAUTH_TOKEN}"}
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        raise HTTPException(status_code=500, detail="Ошибка получения целей")
    all_goals = r.json().get("goals", [])
    return [goal for goal in all_goals if goal["id"] in INTERESTING_GOALS]


def get_goal_stats(counter_id: int, goal_id: int, date1: str, date2: str) -> int:
    url = "https://api-metrika.yandex.net/stat/v1/data"
    headers = {"Authorization": f"OAuth {YANDEX_OAUTH_TOKEN}"}
    params = {
        "ids": counter_id,
        "metrics": f"ym:s:goal{goal_id}reaches",
        "date1": date1,
        "date2": date2,
        "accuracy": "full"
    }
    r = requests.get(url, headers=headers, params=params)
    if r.status_code != 200:
        raise HTTPException(status_code=500, detail=f"Ошибка получения статистики для цели {goal_id}")
    try:
        return int(r.json()["totals"][0])
    except Exception:
        return 0


def get_month_ranges(start_date: datetime, end_date: datetime) -> List[tuple[str, str, datetime]]:
    """Возвращает список кортежей: (месяц, дата начала, дата конца, дата для записи)"""
    current = datetime(start_date.year, start_date.month, 1)
    result = []

    while current <= end_date:
        year, month = current.year, current.month
        month_str = f"{year}-{month:02d}"
        month_start = datetime(year, month, 1)
        month_end_day = calendar.monthrange(year, month)[1]
        month_end = datetime(year, month, month_end_day)

        from_date = max(month_start, start_date).strftime("%Y-%m-%d")
        to_date = min(month_end, end_date).strftime("%Y-%m-%d")

        result.append((month_str, from_date, to_date, month_start.date()))
        current = (month_start + timedelta(days=32)).replace(day=1)

    return result


from sqlalchemy.ext.asyncio import AsyncSession

@router.get("/", response_model=Dict[str, List[GoalInfo]])
async def get_goals_by_date_range(
    start_date: datetime = Query(..., description="Формат: YYYY-MM-DD"),
    end_date: datetime = Query(..., description="Формат: YYYY-MM-DD"),
    db: AsyncSession = Depends(get_db)  # AsyncSession!
):
    if start_date > end_date:
        raise HTTPException(status_code=400, detail="start_date не может быть позже end_date")

    goals = get_goals(COUNTER_ID)
    result: Dict[str, List[GoalInfo]] = {}

    for month_str, from_date, to_date, date_for_db in get_month_ranges(start_date, end_date):
        month_goals = []
        for goal in goals:
            conversions = get_goal_stats(COUNTER_ID, goal['id'], from_date, to_date)

            goal_stat = GoalStat(
                goal_id=goal['id'],
                goal_name=goal['name'],
                goal_type=goal['type'],
                conversions=conversions,
                date=date_for_db
            )
            db.add(goal_stat)

            month_goals.append(GoalInfo(
                id=goal['id'],
                name=goal['name'],
                type=goal['type'],
                conversions=conversions
            ))
        await db.commit()  # <-- обязательно await
        result[month_str] = month_goals

    return result

