from ReportsMetrica.models import TrafficSourceData

from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import Depends

from database import get_db


async def save_traffic_data(counter_id: str, traffic_data: list, db: AsyncSession = Depends(get_db)
):
    async with db.begin():
        try:
            # Добавляем данные для каждого источника трафика
            traffic_source_data = [
                TrafficSourceData(
                    counter_id=counter_id,
                    traffic_source=item['traffic_source'],
                    total_visits=item['total_visits'],
                    total_users=item['total_users'],
                    avg_bounce_rate=item['avg_bounce_rate'],
                    avg_page_depth=item['avg_page_depth'],
                    avg_visit_duration=item['avg_visit_duration']
                )
                for item in traffic_data
            ]

            db.add_all(traffic_source_data)
            await db.commit()

        except Exception as e:
            await db.rollback()
            raise e