from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from datetime import datetime, timedelta
import calendar
import requests
import os
from typing import List, Dict

router = APIRouter(
    prefix="/goals",
    tags=["Yandex Goals"]
)

YANDEX_OAUTH_TOKEN = os.getenv("API_TOKEN")

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
    return r.json().get("goals", [])

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
        return int(r.json()['totals'][0])
    except Exception:
        return 0

def get_month_ranges(start_date: datetime, end_date: datetime) -> List[tuple[str, str, str]]:
    """Возвращает список кортежей (month_str, from_date, to_date)"""
    current = datetime(start_date.year, start_date.month, 1)
    result = []

    while current <= end_date:
        year = current.year
        month = current.month
        month_str = f"{year}-{month:02d}"

        month_start = datetime(year, month, 1)
        month_end_day = calendar.monthrange(year, month)[1]
        month_end = datetime(year, month, month_end_day)

        from_date = max(month_start, start_date).strftime("%Y-%m-%d")
        to_date = min(month_end, end_date).strftime("%Y-%m-%d")

        result.append((month_str, from_date, to_date))
        current = (month_start + timedelta(days=32)).replace(day=1)

    return result

@router.get("/{counter_id}", response_model=Dict[str, List[GoalInfo]])
def get_goals_by_date_range(
    counter_id: int,
    start_date: datetime = Query(..., description="Формат: YYYY-MM-DD"),
    end_date: datetime = Query(..., description="Формат: YYYY-MM-DD"),
):
    if start_date > end_date:
        raise HTTPException(status_code=400, detail="start_date не может быть позже end_date")

    goals = get_goals(counter_id)
    result: Dict[str, List[GoalInfo]] = {}

    for month_str, from_date, to_date in get_month_ranges(start_date, end_date):
        month_goals = []
        for goal in goals:
            conversions = get_goal_stats(counter_id, goal['id'], from_date, to_date)
            month_goals.append(GoalInfo(
                id=goal['id'],
                name=goal['name'],
                type=goal['type'],
                conversions=conversions
            ))
        result[month_str] = month_goals

    return result
