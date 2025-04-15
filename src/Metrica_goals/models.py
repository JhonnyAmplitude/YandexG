from sqlalchemy import Column, Integer, String, Date, Index
from src.database import Base

class GoalStat(Base):
    __tablename__ = "goal_stats"

    id = Column(Integer, primary_key=True)
    goal_id = Column(Integer, nullable=False)
    goal_name = Column(String, nullable=False)
    goal_type = Column(String, nullable=False)
    conversions = Column(Integer, nullable=False)
    date = Column(Date, nullable=False)

    def __repr__(self):
        return f"<GoalStat(goal_id={self.goal_id}, conversions={self.conversions}, date={self.date})>"
