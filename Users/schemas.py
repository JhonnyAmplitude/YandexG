from datetime import datetime

from pydantic import BaseModel
from typing import Optional

class UserResponseSchema(BaseModel):
    id: int
    yandex_id: str
    login: Optional[str] = None
    client_id: str
    display_name: Optional[str] = None
    access_token: str
    refresh_token: str
    created_at: datetime

    class Config:
        orm_mode = True  # Это нужно, чтобы можно было использовать схему с SQLAlchemy
