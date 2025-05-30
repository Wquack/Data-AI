import jwt
from jose import JWTError  # Import JWTError for specific error handling
from datetime import datetime, timedelta, timezone
import os
import logging
from typing import Dict, Optional, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load and validate environment variables
JWT_SECRET: str = os.getenv("JWT_SECRET", "your-secret-key")
JWT_ALGORITHM: str = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

# Validate environment variables
if not JWT_SECRET or JWT_SECRET == "your-secret-key":
    logger.warning("JWT_SECRET not set or using default value, which is insecure")
if not ACCESS_TOKEN_EXPIRE_MINUTES or ACCESS_TOKEN_EXPIRE_MINUTES <= 0:
    raise ValueError("ACCESS_TOKEN_EXPIRE_MINUTES must be a positive integer")
if not REFRESH_TOKEN_EXPIRE_DAYS or REFRESH_TOKEN_EXPIRE_DAYS <= 0:
    raise ValueError("REFRESH_TOKEN_EXPIRE_DAYS must be a positive integer")

logger.info(f"Loaded JWT_SECRET: {JWT_SECRET[:10]}... (first 10 chars for security)")
logger.info(f"Loaded ACCESS_TOKEN_EXPIRE_MINUTES: {ACCESS_TOKEN_EXPIRE_MINUTES}")
logger.info(f"Loaded REFRESH_TOKEN_EXPIRE_DAYS: {REFRESH_TOKEN_EXPIRE_DAYS}")

def create_access_token(data: Dict[str, Any]) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    logger.info(f"Setting access token expiration to {expire} (UTC)")
    to_encode.update({"exp": expire, "type": "access"})
    logger.debug(f"Using JWT_SECRET for encoding: {JWT_SECRET[:10]}...")
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
    if len(encoded_jwt.split('.')) != 3:
        logger.error(f"Invalid JWT token generated: {encoded_jwt}")
        raise ValueError("Failed to generate a valid JWT token")
    logger.debug(f"Created access token with expiration in {ACCESS_TOKEN_EXPIRE_MINUTES} minutes: {encoded_jwt}")
    return encoded_jwt

def create_refresh_token(data: Dict[str, Any]) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    logger.info(f"Setting refresh token expiration to {expire} (UTC)")
    to_encode.update({"exp": expire, "type": "refresh"})
    logger.debug(f"Using JWT_SECRET for encoding: {JWT_SECRET[:10]}...")
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
    if len(encoded_jwt.split('.')) != 3:
        logger.error(f"Invalid JWT refresh token generated: {encoded_jwt}")
        raise ValueError("Failed to generate a valid JWT refresh token")
    logger.debug(f"Created refresh token with expiration in {REFRESH_TOKEN_EXPIRE_DAYS} days: {encoded_jwt}")
    return encoded_jwt

def decode_access_token(token: str) -> Dict[str, Any]:
    try:
        logger.debug(f"Using JWT_SECRET for decoding: {JWT_SECRET[:10]}...")
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError as e:
        logger.error(f"Failed to decode access token: {str(e)}")
        raise Exception("Invalid or expired token")

def generate_state_token(user_id: str) -> str:
    logger.debug(f"Using JWT_SECRET for encoding state token: {JWT_SECRET[:10]}...")
    encoded_jwt = jwt.encode({"user_id": user_id}, JWT_SECRET, algorithm=JWT_ALGORITHM)
    logger.debug(f"Generated state token: {encoded_jwt}")
    return encoded_jwt

def decode_state_token(token: str) -> str:  # Changed from Optional[str] to str
    try:
        payload = decode_access_token(token)
        # Handle both {"data": "<id>"} and {"user_id": "<id>"} formats
        user_id = payload.get("data") or payload.get("user_id")
        if not user_id:
            raise ValueError("State token payload missing 'data' or 'user_id'")
        return str(user_id)  # Ensure the user_id is a string
    except Exception as e:
        logger.error(f"Failed to decode state token: {str(e)}")
        raise Exception(f"Invalid state token: {str(e)}")