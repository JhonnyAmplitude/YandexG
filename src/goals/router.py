import os
from datetime import datetime, date, timedelta
from collections import defaultdict
from typing import Dict, List, Optional

from fastapi import APIRouter, Query, HTTPException, Depends
from httpx import AsyncClient
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from dotenv import load_dotenv

from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.database import get_db
from src.goals.models import GoalStatFinal

load_dotenv()

router = APIRouter(prefix="/yandex_metrika_goals", tags=["Yandex goals"])

YANDEX_API_URL = os.getenv("API_METRICA_URL")
YANDEX_OAUTH_TOKEN = os.getenv("API_TOKEN")

GOAL_IDS = [183338431, 91705897, 339342936]
METRIC_SUFFIXES = ["reaches", "conversionRate", "visits"]

def parse_date_from_group(group_key: str, group_by: str) -> date:
    if group_by == "day":
        return datetime.strptime(group_key, "%Y-%m-%d").date()
    elif group_by == "month":
        return datetime.strptime(group_key, "%Y-%m").date().replace(day=1)
    elif group_by == "week":
        year, week = group_key.split("-W")
        return datetime.strptime(f"{year}-W{week}-1", "%Y-W%W-%w").date()
    raise ValueError("Unsupported group_by value")

async def get_goals(counter_id: str) -> Dict[int, str]:
    url = f"https://api-metrika.yandex.ru/management/v1/counter/{counter_id}/goals"
    headers = {"Authorization": f"OAuth {YANDEX_OAUTH_TOKEN}"}

    async with AsyncClient() as client:
        response = await client.get(url, headers=headers)

    if response.status_code != 200:
        raise HTTPException(
            status_code=response.status_code,
            detail={"error": "Failed to fetch goals from Yandex Metrika", "response": response.text},
        )

    try:
        data = response.json()
    except ValueError:
        raise HTTPException(status_code=500, detail="Failed to parse response JSON")

    if "goals" not in data:
        raise HTTPException(status_code=500, detail="No goals found in the response")

    return {
        goal["id"]: goal["name"]
        for goal in data["goals"]
        if goal.get("id") in GOAL_IDS and goal.get("name")
    }


async def save_goal_stats_final(session: AsyncSession, result, group_by):
    values_to_insert = []

    for item in result:
        period_date = parse_date_from_group(item['date'], group_by)

        for goal in item['goals']:
            values_to_insert.append({
                'goal_id': int(goal['id']),
                'date': period_date,
                'period_type': group_by,
                'reaches': goal['reaches'],
                'conversion_rate': goal['conversion_rate'],
                'visits': goal['visits'],
            })

    try:
        for value in values_to_insert:
            stmt = pg_insert(GoalStatFinal).values(value)
            stmt = stmt.on_conflict_do_update(
                index_elements=['goal_id', 'date', 'period_type'],
                set_={
                    'reaches': stmt.excluded.reaches,
                    'conversion_rate': stmt.excluded.conversion_rate,
                    'visits': stmt.excluded.visits,
                }
            )
            await session.execute(stmt)
        await session.commit()
    except SQLAlchemyError as e:
        await session.rollback()
        print(f"SQLAlchemy error: {e}")
        raise e


@router.get("/statistics", summary="Получить статистики по целям")
async def get_parsed_goal_metrics(
    date1: date = Query(...),
    date2: date = Query(...),
    ids: str = Query("181494"),
    group_by: str = Query("day", pattern="^(day|week|month)$"),
    goal_ids_filter: Optional[List[int]] = Query(None),
    session: AsyncSession = Depends(get_db)
) -> Dict:
    all_goals = await get_goals(ids)
    filtered_goals = {
        gid: name for gid, name in all_goals.items()
        if (goal_ids_filter is None or gid in goal_ids_filter)
    }
    goal_ids = list(filtered_goals.keys())

    if not goal_ids:
        raise HTTPException(status_code=400, detail="No goals found for the given filter")

    metrics = [f"ym:s:goal{goal_id}{suffix}" for goal_id in goal_ids for suffix in METRIC_SUFFIXES]
    params = {
        "ids": ids,
        "metrics": ",".join(metrics),
        "dimensions": "ym:s:date",
        "date1": str(date1),
        "date2": str(date2),
    }

    headers = {"Authorization": f"OAuth {YANDEX_OAUTH_TOKEN}"}

    async with AsyncClient() as client:
        response = await client.get(YANDEX_API_URL, params=params, headers=headers)

    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail={"error": "Failed to fetch Yandex Metrika"})

    try:
        data = response.json()
    except ValueError:
        raise HTTPException(status_code=500, detail="Invalid response from Yandex")

    # Подготовка пустых значений на все дни
    all_dates = {}
    current = date1
    while current <= date2:
        all_dates[str(current)] = {
            str(gid): {"id": str(gid), "reaches": 0, "conversion_rate": 0.0, "visits": 0}
            for gid in goal_ids
        }
        current += timedelta(days=1)

    for row in data.get("data", []):
        date_str = row["dimensions"][0]["name"]
        metrics_values = row["metrics"]
        for i, goal_id in enumerate(goal_ids):
            offset = i * len(METRIC_SUFFIXES)
            all_dates[date_str][str(goal_id)] = {
                "id": str(goal_id),
                "reaches": metrics_values[offset],
                "conversion_rate": round(metrics_values[offset + 1], 2),
                "visits": metrics_values[offset + 2],
            }

    grouped = defaultdict(lambda: defaultdict(lambda: {
        "id": "", "reaches": 0, "conversion_rate_sum": 0.0, "visits": 0, "count": 0
    }))

    for date_str, goals in all_dates.items():
        dt = datetime.strptime(date_str, "%Y-%m-%d").date()

        if group_by == "week":
            group_key = f"{dt.year}-W{dt.isocalendar()[1]}"
        elif group_by == "month":
            group_key = dt.strftime("%Y-%m")
        else:
            group_key = str(dt)

        for goal_id, values in goals.items():
            g = grouped[group_key][goal_id]
            g["id"] = goal_id
            g["reaches"] += values["reaches"]
            g["conversion_rate_sum"] += values["conversion_rate"]
            g["visits"] += values["visits"]
            g["count"] += 1

    month_names_ru = {
        "01": "январь", "02": "февраль", "03": "март", "04": "апрель",
        "05": "май", "06": "июнь", "07": "июль", "08": "август",
        "09": "сентябрь", "10": "октябрь", "11": "ноябрь", "12": "декабрь"
    }

    result = []
    for group_key in sorted(grouped.keys()):
        goals_data = []
        for goal_id, g in grouped[group_key].items():
            goals_data.append({
                "id": goal_id,
                "reaches": g["reaches"],
                "conversion_rate": round(g["conversion_rate_sum"] / g["count"], 2) if g["count"] else 0.0,
                "visits": g["visits"]
            })

        # Генерация label
        if group_by == "month":
            year, month = group_key.split("-")
            label = f"{year} - {month_names_ru[month]}"
        elif group_by == "week":
            year, week = group_key.split("-W")
            year, week = int(year), int(week)
            try:
                monday = date.fromisocalendar(year, week, 1)
                sunday = date.fromisocalendar(year, week, 7)
                label = f"{monday.strftime('%Y-%m-%d')} — {sunday.strftime('%Y-%m-%d')}"
            except ValueError:
                label = f"{year} - {week} неделя"
        else:
            label = group_key

        result.append({
            "date": group_key,
            "label": label,
            "goals": goals_data
        })

    await save_goal_stats_final(session, result, group_by)

    return {
        "goal_meta": [{"id": gid, "name": filtered_goals[gid]} for gid in goal_ids],
        "data": result
    }


@router.get("/info", summary="Получить список целей", response_model=List[dict])
async def get_goal_meta():
    try:
        goals = await get_goals('181494')

        goal_meta = [{"id": goal_id, "name": goal_name} for goal_id, goal_name in goals.items()]
        return goal_meta
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))