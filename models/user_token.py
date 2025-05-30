from utils.db import Base
from sqlalchemy import Column, String, DateTime

class UserToken(Base):
    """
    Model for storing OAuth tokens for users.

    Each entry represents a token for a specific user and service (e.g., Google, Slack, Zoom).
    The primary key is a composite of user_id and service.
    """
    __tablename__ = "user_tokens"

    user_id = Column(String(length=50), primary_key=True, comment="The ID of the user")
    service = Column(String(length=50), primary_key=True, comment="The service (e.g., google, slack, zoom)")
    access_token = Column(String(length=255), nullable=False, comment="The OAuth access token")
    refresh_token = Column(String(length=255), nullable=True, comment="The OAuth refresh token (optional)")
    expires_at = Column(DateTime, nullable=True, comment="Expiration timestamp in UTC (optional)")