# models/user_token.py
from models import Base
from sqlalchemy import Column, String, DateTime
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class UserToken(Base):
    __tablename__ = "user_tokens"

    user_id = Column(String, primary_key=True)
    service = Column(String, primary_key=True)
    access_token = Column(String, nullable=False)
    refresh_token = Column(String, nullable=True)
    expires_at = Column(DateTime, nullable=True)
