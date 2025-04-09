from fastapi import HTTPException, Query, APIRouter
import requests
from dotenv import load_dotenv
from  datetime import date

import os

router = APIRouter()

load_dotenv()

API_URL = os.getenv("API_METRICA_URL")
API_COUNTER_URL = os.getenv("API_METRICA_COUNTER_URL")
API_TOKEN = os.getenv("API_TOKEN")

COUNTER_IDS = [181494, 72372934]


@router.get("/metrika_chart/")
async def get_metrika_data():
    headers = {'Authorization': f'OAuth {API_TOKEN}'}
    results = {}

    for counter_id in COUNTER_IDS:
        params = {
            'ids': counter_id,
            'date1': '2025-03-01',
            'date2': '2025-03-31',
            'metrics': 'ym:s:visits,ym:s:users,ym:s:bounceRate,ym:s:pageDepth,ym:s:avgVisitDurationSeconds',
            'dimensions': 'ym:s:trafficSource,ym:s:date',
            'group': 'Day',
            'accuracy': 'full',
            'limit': 100
        }

        response = requests.get(API_URL, params=params, headers=headers)

        if response.status_code == 200:
            try:
                data = response.json()
                cleaned_data = []

                for item in data.get("data", []):
                    traffic_source = item["dimensions"][0]["name"]
                    date = item["dimensions"][1]["name"]  # Сохраняем дату
                    metrics = item["metrics"]

                    # Преобразуем секунды в формат MM:SS для "avgVisitDurationSeconds"
                    seconds = metrics[4]
                    minutes = int(seconds // 60)
                    sec = int(seconds % 60)
                    metrics[4] = f"{minutes}:{sec:02d}"  # Формат MM:SS

                    cleaned_data.append({
                        "date": date,  # Добавляем дату
                        "traffic_source": traffic_source,
                        "visits": metrics[0],
                        "users": metrics[1],
                        "bounce_rate": metrics[2],
                        "page_depth": metrics[3],
                        "avg_visit_duration": metrics[4]
                    })

                # Сортировка данных по дате
                sorted_data = sorted(cleaned_data, key=lambda x: x["date"])

                # Сохраняем отсортированные данные в результат
                results[counter_id] = sorted_data
                return results
            except ValueError:
                return {"error": "Ошибка при разборе JSON-ответа", "response_text": response.text}
        else:
            return {
                "error": "Ошибка получения данных",
                "status_code": response.status_code,
                "response_text": response.text
            }
    return results


@router.get("/metrika_summary/")
async def get_metrika_summary(
        date1: str = Query(default=str(date.today().replace(day=1)), description="Начальная дата (YYYY-MM-DD)"),
        date2: str = Query(default=str(date.today()), description="Конечная дата (YYYY-MM-DD)")
):
    headers = {'Authorization': f'OAuth {API_TOKEN}'}
    results = {}

    for counter_id in COUNTER_IDS:
        params = {
            'ids': counter_id,
            'date1': date1,
            'date2': date2,
            'metrics': 'ym:s:visits,ym:s:users,ym:s:bounceRate,ym:s:pageDepth,ym:s:avgVisitDurationSeconds',
            'dimensions': 'ym:s:trafficSource',
            'accuracy': 'full'
        }

        response = requests.get(API_URL, params=params, headers=headers)

        if response.status_code == 200:
            try:
                data = response.json()

                if "data" not in data or not data["data"]:
                    results[counter_id] = {"error": "Нет данных за указанный период"}
                    continue

                summary_data = []

                for item in data["data"]:
                    traffic_source = item["dimensions"][0]["name"]
                    metrics = item["metrics"]

                    total_visits = int(metrics[0])
                    total_users = int(metrics[1])
                    avg_bounce_rate = round(metrics[2], 2)
                    avg_page_depth = round(metrics[3], 2)

                    avg_seconds = metrics[4]
                    minutes = int(avg_seconds // 60)
                    seconds = int(avg_seconds % 60)
                    avg_visit_duration = f"{minutes}:{seconds:02d}"

                    summary_data.append({
                        "traffic_source": traffic_source,
                        "total_visits": total_visits,
                        "total_users": total_users,
                        "avg_bounce_rate": avg_bounce_rate,
                        "avg_page_depth": avg_page_depth,
                        "avg_visit_duration": avg_visit_duration
                    })

                results[counter_id] = summary_data
            except ValueError:
                results[counter_id] = {"error": "Ошибка при разборе JSON-ответа", "response_text": response.text}
        else:
            results[counter_id] = {
                "error": "Ошибка получения данных",
                "status_code": response.status_code,
                "response_text": response.text
            }

    return results


@router.get("/get_counters")
async def get_counters():
    headers = {
        "Authorization": f"OAuth {API_TOKEN}"
    }

    # Выполнение запроса к API
    response = requests.get(API_COUNTER_URL, headers=headers)

    # Выводим тело ответа для диагностики
    if response.status_code != 200:
        raise HTTPException(
            status_code=response.status_code,
            detail=f"Ошибка при получении счетчиков: {response.text}"
        )

    # Возвращаем список счетчиков
    counters = response.json().get("counters", [])
    result = [
        {
            "id": counter["id"],
            "name": counter.get("name", "Без имени"),
            "site": counter.get("site", "Не указан")
        }
        for counter in counters
    ]

    return {"counters": result}