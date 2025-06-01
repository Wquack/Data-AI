from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, JSON
from sqlalchemy.sql import func
from utils.db import Base

class ConversationHistory(Base):
    """Store conversation history for each user"""
    __tablename__ = "conversation_history"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(50), index=True, nullable=False)
    message = Column(Text, nullable=False)
    response = Column(Text, nullable=False)
    intent = Column(String(50), nullable=True)
    confidence = Column(String(10), nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    session_id = Column(String(100), nullable=True)  # For grouping conversations

class UserProfile(Base):
    """Store user communication preferences and patterns"""
    __tablename__ = "user_profiles"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(50), unique=True, index=True, nullable=False)
    communication_style = Column(String(20), default="neutral")  # casual, formal, neutral
    preferred_response_length = Column(String(10), default="medium")  # short, medium, long
    personality_traits = Column(JSON, default={})  # Store analyzed traits
    interaction_count = Column(Integer, default=0)
    last_active = Column(DateTime(timezone=True), server_default=func.now())
    preferred_services = Column(JSON, default=[])  # Most used services
    common_intents = Column(JSON, default={})  # Track frequent intent patterns