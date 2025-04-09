from sqlalchemy import Column, Integer, String, DateTime
from src.database import Base
import datetime


class User(Base):
    __tablename__ = 'users'
    __table_args__ = {"schema": "public"}

    id = Column(Integer, primary_key=True, index=True)
    yandex_id = Column(String, unique=True, index=True)  # ID Яндекса
    login = Column(String, unique=True, nullable=True, index=True)  # login (или login) пользователя
    client_id = Column(String, nullable=True)  # client_id
    display_name = Column(String)  # display_name
    access_token = Column(String, nullable=False)  # access_token
    refresh_token = Column(String, nullable=False)  # refresh_token
    created_at = Column(DateTime, default=datetime.datetime.utcnow)  # Дата создания

    def __repr__(self):
        return f"<User(yandex_id={self.yandex_id}, login={self.login}, display_name={self.display_name})>"
