from pydantic import BaseModel
from datetime import date

class GoalInfo(BaseModel):
    id: int
    name: str
    type: str
    conversions: int

    class Config:
        from_attributes = True
        alias_generator = lambda string: string if string == "id" else string.lower()
