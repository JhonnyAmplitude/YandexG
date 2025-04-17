from sqlalchemy import Column, Integer, String, Date, Index, BigInteger, UniqueConstraint, Float
from src.database import Base


class GoalStatFinal(Base):
    __tablename__ = "goal_stats_final"

    id = Column(Integer, primary_key=True)
    goal_id = Column(BigInteger, nullable=False)
    date = Column(Date, nullable=False)  # День, как базовая единица
    period_type = Column(String, nullable=False)  # 'day', 'week', 'month'

    reaches = Column(Integer, nullable=False, default=0)
    conversion_rate = Column(Float, nullable=False, default=0.0)
    visits = Column(Integer, nullable=False, default=0)

    __table_args__ = (
        UniqueConstraint("goal_id", "date", "period_type", name="uix_counter_goal_date_period"),
    )