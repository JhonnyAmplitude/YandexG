from sqlalchemy import Column, Integer, String, DateTime, Float
from database import Base
from datetime import datetime



class TrafficSourceData(Base):
    __tablename__ = 'traffic_source_data'
    __table_args__ = {"schema": "public"}

    id = Column(Integer, primary_key=True, index=True)
    counter_id = Column(String, index=True)
    traffic_source = Column(String)
    total_visits = Column(Integer)
    total_users = Column(Integer)
    avg_bounce_rate = Column(Float)
    avg_page_depth = Column(Float)
    avg_visit_duration = Column(String)
    date = Column(DateTime, default=datetime.utcnow)


