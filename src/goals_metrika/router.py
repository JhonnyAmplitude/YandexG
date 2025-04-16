from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel
from datetime import datetime, timedelta
import httpx
import os
from typing import Optional, Annotated
from aiolimiter import AsyncLimiter
from typing import Literal

from sqlalchemy import select
from collections import defaultdict

from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.goals_metrika.models import GoalsStatistic

router = APIRouter(
    prefix="/metrika_days_goals",
    tags=["Yandex Goals"]
)

load_dotenv()

YANDEX_OAUTH_TOKEN = os.getenv("API_TOKEN")
COUNTER_ID = int(os.getenv("COUNTER_ID", 181494))
INTERESTING_GOALS = [183338431, 91705897, 339342936]

yandex_limiter = AsyncLimiter(max_rate=5, time_period=1)


# GoalInfo model to structure goal data
class GoalInfo(BaseModel):
    id: int
    name: str
    type: str
    conversions: int


def get_date_ranges(start_date: datetime, end_date: datetime, group_by: str) -> list[tuple[str, str, str, datetime]]:
    ranges = []
    current = start_date

    if group_by == "month":
        current = current.replace(day=1)

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

    elif group_by == "week":
        current -= timedelta(days=current.weekday())  # Monday
        while current <= end_date:
            week_start = current
            week_end = current + timedelta(days=6)

            from_date = max(week_start, start_date)
            to_date = min(week_end, end_date)

            if from_date <= to_date:
                ranges.append((
                    f"{from_date.strftime('%Y-%m-%d')}_week",
                    from_date.strftime("%Y-%m-%d"),
                    to_date.strftime("%Y-%m-%d"),
                    from_date.date()
                ))

            current = week_end + timedelta(days=1)

    elif group_by == "day":
        while current <= end_date:
            date_str = current.strftime("%Y-%m-%d")
            ranges.append((
                date_str,
                date_str,
                date_str,
                current.date()
            ))
            current += timedelta(days=1)

    return ranges


async def fetch_goals(client: httpx.AsyncClient, counter_id: int) -> list[dict]:
    url = f"https://api-metrika.yandex.net/management/v1/counter/{counter_id}/goals"
    headers = {"Authorization": f"OAuth {YANDEX_OAUTH_TOKEN}"}

    # Check if the token is valid by making a test request
    try:
        async with yandex_limiter:
            response = await client.get(url, headers=headers)
        response.raise_for_status()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            raise HTTPException(status_code=401, detail="Unauthorized: Invalid OAuth token")
        raise HTTPException(status_code=e.response.status_code, detail=f"Yandex API error: {e.response.text}")

    goals = response.json().get("goals", [])
    return [g for g in goals if g["id"] in INTERESTING_GOALS]


async def fetch_goal_stats_by_days(
        client: httpx.AsyncClient,
        counter_id: int,
        goal_id: int,
        date1: str,
        date2: str
) -> dict[str, int]:
    url = "https://api-metrika.yandex.net/stat/v1/data"
    headers = {"Authorization": f"OAuth {YANDEX_OAUTH_TOKEN}"}
    params = {
        "ids": counter_id,
        "metrics": f"ym:s:goal{goal_id}reaches",
        "dimensions": "ym:s:date",
        "date1": date1,
        "date2": date2,
        "accuracy": "full",
    }

    try:
        async with yandex_limiter:
            response = await client.get(url, headers=headers, params=params)
        response.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"Yandex API error: {e.response.text}")

    # Преобразуем даты в полный список
    start = datetime.strptime(date1, "%Y-%m-%d").date()
    end = datetime.strptime(date2, "%Y-%m-%d").date()
    all_dates = {start + timedelta(days=i): 0 for i in range((end - start).days + 1)}

    data = response.json().get("data", [])
    for item in data:
        date_str = item["dimensions"][0]["name"]
        value = int(item["metrics"][0]) if item["metrics"] else 0
        all_dates[datetime.strptime(date_str, "%Y-%m-%d").date()] = value

    return {date.strftime("%Y-%m-%d"): value for date, value in all_dates.items()}


@router.get("/", response_model=dict[str, list[GoalInfo]])
async def get_goals_by_date_range(
        start_date: Annotated[datetime, Query()],
        end_date: Annotated[datetime, Query()],
        group_by: Annotated[Literal["day", "week", "month"], Query()] = "month",
        db: AsyncSession = Depends(get_db)
):
    if start_date > end_date:
        raise HTTPException(status_code=400, detail="Start date must be before end date")

    try:
        async with httpx.AsyncClient() as client:
            # 1. Получаем цели
            goals = await fetch_goals(client, COUNTER_ID)
            goal_ids = [goal["id"] for goal in goals]

            # 2. Формируем диапазоны по нужной группировке
            date_ranges = get_date_ranges(start_date, end_date, group_by)
            if not date_ranges:
                return {}

            # 3. Загружаем все дневные данные из БД за нужный диапазон
            all_needed_dates = set()
            for _, from_date, to_date, _ in date_ranges:
                d1 = datetime.strptime(from_date, "%Y-%m-%d").date()
                d2 = datetime.strptime(to_date, "%Y-%m-%d").date()
                for n in range((d2 - d1).days + 1):
                    all_needed_dates.add(d1 + timedelta(days=n))

            stmt = select(GoalsStatistic).where(
                GoalsStatistic.goal_id.in_(goal_ids),
                GoalsStatistic.date.in_(all_needed_dates),
                GoalsStatistic.granularity == "day"
            )
            result_from_db = await db.execute(stmt)
            existing_stats = result_from_db.scalars().all()
            existing_map = defaultdict(dict)
            for row in existing_stats:
                existing_map[(row.goal_id)][row.date] = row.conversions

            result = defaultdict(list)
            stats_to_add = []

            # 4. Обрабатываем группировку
            for range_key, from_date_str, to_date_str, db_date in date_ranges:
                from_date = datetime.strptime(from_date_str, "%Y-%m-%d").date()
                to_date = datetime.strptime(to_date_str, "%Y-%m-%d").date()

                for goal in goals:
                    conversions_total = 0
                    missing_dates = []

                    for n in range((to_date - from_date).days + 1):
                        day = from_date + timedelta(days=n)
                        conversions = existing_map.get(goal["id"], {}).get(day)
                        if conversions is not None:
                            conversions_total += conversions
                        else:
                            missing_dates.append(day)

                    # Если есть пропущенные даты — запрашиваем из API
                    if missing_dates:
                        api_from = min(missing_dates).strftime("%Y-%m-%d")
                        api_to = max(missing_dates).strftime("%Y-%m-%d")

                        stats_by_day = await fetch_goal_stats_by_days(
                            client, COUNTER_ID, goal["id"], api_from, api_to
                        )

                        for date_str, conv in stats_by_day.items():
                            date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
                            stats_to_add.append(GoalsStatistic(
                                goal_id=goal["id"],
                                goal_name=goal["name"],
                                goal_type=goal["type"],
                                conversions=conv,
                                date=date_obj,
                                granularity="day"
                            ))
                            conversions_total += conv

                    # Добавляем агрегированные данные в ответ
                    result[range_key].append(GoalInfo(
                        id=goal["id"],
                        name=goal["name"],
                        type=goal["type"],
                        conversions=conversions_total
                    ))

        # 5. Сохраняем недостающие дневные данные
        if stats_to_add:
            await db.execute(insert(GoalsStatistic).values([
                {
                    "goal_id": s.goal_id,
                    "goal_name": s.goal_name,
                    "goal_type": s.goal_type,
                    "conversions": s.conversions,
                    "date": s.date,
                    "granularity": s.granularity
                } for s in stats_to_add
            ]))
            await db.commit()

        return result

    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"Yandex API error: {e.response.text}")
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")

