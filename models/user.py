from sqlalchemy import Column, Integer, String
from utils.db import Base

class User(Base):
    """
    Model for storing user information.

    Each entry represents a user with a unique email and username.
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, comment="Unique identifier for the user")
    email = Column(String(length=255), unique=True, index=True, nullable=False, comment="User's email address (unique)")
    username = Column(String(length=50), unique=True, index=True, nullable=False, comment="User's username (unique)")
    password_hash = Column(String(length=255), nullable=False, comment="Hashed password of the user")