from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel
from datetime import datetime, timedelta
import httpx
import os
from typing import Optional, Annotated
from aiolimiter import AsyncLimiter


from sqlalchemy import select
from collections import defaultdict

from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from .models import GoalStat

router = APIRouter(
    prefix="/metrika_goals",
    tags=["Yandex Goals"]
)

YANDEX_OAUTH_TOKEN = os.getenv("API_TOKEN")
COUNTER_ID = int(os.getenv("COUNTER_ID", 181494))
INTERESTING_GOALS = [183338431, 91705897, 339342936]

yandex_limiter = AsyncLimiter(max_rate=5, time_period=1)


if not YANDEX_OAUTH_TOKEN or not COUNTER_ID:
    raise RuntimeError("Missing required environment variables")


class GoalInfo(BaseModel):
    id: int
    name: str
    type: str
    conversions: int


async def fetch_goals(client: httpx.AsyncClient, counter_id: int) -> list[dict]:
    url = f"https://api-metrika.yandex.ru/management/v1/counter/{counter_id}/goals"
    headers = {"Authorization": f"OAuth {YANDEX_OAUTH_TOKEN}"}

    async with yandex_limiter:
        response = await client.get(url, headers=headers)
    response.raise_for_status()
    goals = response.json().get("goals", [])
    return [g for g in goals if g["id"] in INTERESTING_GOALS]


async def fetch_goal_stats(client: httpx.AsyncClient, counter_id: int, goal_id: int, date1: str, date2: str) -> int:
    url = "https://api-metrika.yandex.ru/stat/v1/data"
    headers = {"Authorization": f"OAuth {YANDEX_OAUTH_TOKEN}"}
    params = {
        "ids": counter_id,
        "metrics": f"ym:s:goal{goal_id}reaches",
        "date1": date1,
        "date2": date2,
        "dimensions": "ym:s:date",
        "accuracy": "full"
    }

    async with yandex_limiter:
        response = await client.get(url, headers=headers, params=params)
    response.raise_for_status()

    try:
        return int(response.json().get("totals", [0])[0])
    except (IndexError, ValueError, KeyError):
        return 0


def get_month_ranges(start_date: datetime, end_date: datetime) -> list[tuple[str, str, str, datetime]]:
    current = start_date.replace(day=1)
    ranges = []

    while current <= end_date:
        month_start = current
        month_end = (current + timedelta(days=32)).replace(day=1) - timedelta(days=1)

        from_date = max(month_start, start_date)
        to_date = min(month_end, end_date)

        if from_date <= to_date:
            ranges.append((
                current.strftime("%Y-%m"),
                from_date.strftime("%Y-%m-%d"),
                to_date.strftime("%Y-%m-%d"),
                current.date()
            ))

        current = (month_end + timedelta(days=1)).replace(day=1)

    return ranges


@router.get("/", response_model=dict[str, list[GoalInfo]])
async def get_goals_by_date_range(
        start_date: Annotated[datetime, Query()],
        end_date: Annotated[datetime, Query()],
        db: AsyncSession = Depends(get_db)
):
    if start_date > end_date:
        raise HTTPException(status_code=400, detail="Start date must be before end date")

    try:
        async with httpx.AsyncClient() as client:
            goals = await fetch_goals(client, COUNTER_ID)
            month_ranges = get_month_ranges(start_date, end_date)

            if not month_ranges:
                return {}

            # Список всех дат и ID целей
            all_dates = [date for _, _, _, date in month_ranges]
            goal_ids = [goal["id"] for goal in goals]

            # Получаем уже сохранённые значения из базы
            stmt = select(GoalStat).where(
                GoalStat.goal_id.in_(goal_ids),
                GoalStat.date.in_(all_dates)
            )
            result_from_db = await db.execute(stmt)
            existing_stats = result_from_db.scalars().all()
            existing_map = {(row.goal_id, row.date): row for row in existing_stats}

            result = defaultdict(list)
            stats_to_add = []

            for month_str, from_date, to_date, db_date in month_ranges:
                month_data = []

                for goal in goals:
                    key = (goal["id"], db_date)

                    if key in existing_map:
                        # Уже есть в базе — не запрашиваем повторно
                        row = existing_map[key]
                        month_data.append(GoalInfo(
                            id=row.goal_id,
                            name=row.goal_name,
                            type=row.goal_type,
                            conversions=row.conversions
                        ))
                    else:
                        # Нет в базе — делаем запрос
                        conversions = await fetch_goal_stats(client, COUNTER_ID, goal["id"], from_date, to_date)

                        stats_to_add.append(GoalStat(
                            goal_id=goal["id"],
                            goal_name=goal["name"],
                            goal_type=goal["type"],
                            conversions=conversions,
                            date=db_date
                        ))

                        month_data.append(GoalInfo(
                            id=goal["id"],
                            name=goal["name"],
                            type=goal["type"],
                            conversions=conversions
                        ))

                result[month_str] = month_data

        # Добавляем в базу только то, чего ещё не было
        if stats_to_add:
            await db.execute(insert(GoalStat).values([
                {
                    "goal_id": s.goal_id,
                    "goal_name": s.goal_name,
                    "goal_type": s.goal_type,
                    "conversions": s.conversions,
                    "date": s.date
                } for s in stats_to_add
            ]))
            await db.commit()

        return result

    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"Yandex API error: {e.response.text}")
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")

