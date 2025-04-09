import os

import requests
from dotenv import load_dotenv
from fastapi import HTTPException

load_dotenv()

API_TOKEN = os.getenv("API_METRICA_URL")
API_URL = os.getenv("API_METRICA_TOKEN")

async def get_metrika_data(counter_id: str, date1: str, date2: str):
    params = {
        'ids': counter_id,
        'date1': date1,
        'date2': date2,
        'metrics': 'ym:s:visits,ym:s:users,ym:s:bounceRate,ym:s:pageDepth,ym:s:avgVisitDurationSeconds',
        'dimensions': 'ym:s:trafficSource',
        'accuracy': 'full'
    }

    headers = {'Authorization': f'OAuth {API_TOKEN}'}
    response = requests.get(API_URL, params=params, headers=headers)

    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.text)

    data = response.json()
    return data['data']
