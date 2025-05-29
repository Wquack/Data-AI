from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)  # type: ignore
    email = Column(String, unique=True, index=True, nullable=False)  # type: ignore
    password_hash = Column(String, nullable=False)  # type: ignore