from pydantic import BaseModel
from datetime import date

class GoalStatSchema(BaseModel):
    id: int
    goal_name: str
    goal_type: str
    conversions: int
    date: date

    class Config:
        from_attributes = True
        alias_generator = lambda string: string if string == "id" else string.lower()
