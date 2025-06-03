# utils/jwt_utils.py - Fixed version compatible with your code
import jwt
from jwt import InvalidTokenError, PyJWTError  # Add both for compatibility
from datetime import datetime, timedelta, timezone
import os
import logging
from typing import Dict, Optional, Any
from dotenv import load_dotenv

# Create alias for compatibility
JWTError = InvalidTokenError  # This fixes the import error in routes.py

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Your existing environment variables (keep as-is)
JWT_SECRET: str = os.getenv("JWT_SECRET", "your-secret-key")
JWT_ALGORITHM: str = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

# Add validation (enhancement)
if not JWT_SECRET or JWT_SECRET == "your-secret-key":
    logger.warning("JWT_SECRET not set or using default value, which is insecure")
if len(JWT_SECRET) < 32:
    logger.warning("JWT_SECRET should be at least 32 characters long for security")

logger.info(f"Loaded JWT_SECRET: {JWT_SECRET[:10]}... (first 10 chars for security)")
logger.info(f"Loaded ACCESS_TOKEN_EXPIRE_MINUTES: {ACCESS_TOKEN_EXPIRE_MINUTES}")

# Your existing functions (keep exactly as-is but enhanced)
def create_access_token(data: Dict[str, Any]) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
    
    # Add validation
    if len(encoded_jwt.split('.')) != 3:
        logger.error(f"Invalid JWT token generated")
        raise ValueError("Failed to generate a valid JWT token")
    
    logger.debug(f"Created access token with expiration in {ACCESS_TOKEN_EXPIRE_MINUTES} minutes")
    return encoded_jwt

def create_refresh_token(data: Dict[str, Any]) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
    
    # Add validation
    if len(encoded_jwt.split('.')) != 3:
        logger.error(f"Invalid JWT refresh token generated")
        raise ValueError("Failed to generate a valid JWT refresh token")
    
    logger.debug(f"Created refresh token with expiration in {REFRESH_TOKEN_EXPIRE_DAYS} days")
    return encoded_jwt

def decode_access_token(token: str) -> Dict[str, Any]:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except InvalidTokenError as e:  # Use InvalidTokenError consistently
        logger.error(f"Failed to decode access token: {str(e)}")
        raise Exception("Invalid or expired token")

def generate_state_token(user_id: str) -> str:
    encoded_jwt = jwt.encode({"user_id": user_id}, JWT_SECRET, algorithm=JWT_ALGORITHM)
    logger.debug(f"Generated state token")
    return encoded_jwt

def decode_state_token(token: str) -> str:
    try:
        payload = decode_access_token(token)
        user_id = payload.get("data") or payload.get("user_id")
        if not user_id:
            raise ValueError("State token payload missing 'data' or 'user_id'")
        return str(user_id)
    except InvalidTokenError as e:  # Use InvalidTokenError consistently
        logger.error(f"Failed to decode state token: {str(e)}")
        raise Exception(f"Invalid state token: {str(e)}")