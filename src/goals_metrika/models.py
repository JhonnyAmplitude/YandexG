from sqlalchemy import Column, Integer, String, Date, Index
from src.database import Base

class GoalsStatistic(Base):
    __tablename__ = "goal_statistics"

    id = Column(Integer, primary_key=True)
    goal_id = Column(Integer, nullable=False)
    goal_name = Column(String, nullable=False)
    goal_type = Column(String, nullable=False)
    conversions = Column(Integer, nullable=False)
    date = Column(Date, nullable=False)
    granularity = Column(String, nullable=False, default="month")
