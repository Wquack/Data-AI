import jwt
from datetime import datetime, timedelta, timezone
import os
import logging
from typing import Dict, Optional, Any

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

JWT_SECRET: str = os.getenv("JWT_SECRET", "your-secret-key")
JWT_ALGORITHM: str = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

def create_access_token(data: Dict[str, Any]) -> str:
    """
    Create an access token with a specified expiration time.

    Args:
        data: Dictionary containing payload data (e.g., user_id).

    Returns:
        A JWT access token as a string.

    Raises:
        ValueError: If the generated token is invalid.
    """
    to_encode = data.copy()
    # Use UTC timezone explicitly to avoid local timezone issues
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
    if len(encoded_jwt.split('.')) != 3:
        logger.error(f"Invalid JWT token generated: {encoded_jwt}")
        raise ValueError("Failed to generate a valid JWT token")
    logger.debug(f"Created access token with expiration in {ACCESS_TOKEN_EXPIRE_MINUTES} minutes: {encoded_jwt}")
    return encoded_jwt

def create_refresh_token(data: Dict[str, Any]) -> str:
    """
    Create a refresh token with a specified expiration time.

    Args:
        data: Dictionary containing payload data (e.g., user_id).

    Returns:
        A JWT refresh token as a string.

    Raises:
        ValueError: If the generated token is invalid.
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
    if len(encoded_jwt.split('.')) != 3:
        logger.error(f"Invalid JWT refresh token generated: {encoded_jwt}")
        raise ValueError("Failed to generate a valid JWT refresh token")
    logger.debug(f"Created refresh token with expiration in {REFRESH_TOKEN_EXPIRE_DAYS} days: {encoded_jwt}")
    return encoded_jwt

def decode_access_token(token: str) -> Dict[str, Any]:
    """
    Decode an access token and return its payload.

    Args:
        token: The JWT token to decode.

    Returns:
        The decoded payload as a dictionary.

    Raises:
        Exception: If the token is invalid or expired.
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return payload
    except Exception as e:
        logger.error(f"Failed to decode access token: {str(e)}")
        raise Exception("Invalid or expired token")

def generate_state_token(data: str) -> str:
    """
    Generate a state token for OAuth flows.

    Args:
        data: The data to encode (e.g., user_id).

    Returns:
        A JWT state token as a string.
    """
    encoded_jwt = jwt.encode({"data": data}, JWT_SECRET, algorithm=JWT_ALGORITHM)
    logger.debug(f"Generated state token: {encoded_jwt}")
    return encoded_jwt

def decode_state_token(token: str) -> Optional[str]:
    """
    Decode a state token and return the embedded data.

    Args:
        token: The JWT state token to decode.

    Returns:
        The decoded data (e.g., user_id) as a string, or None if not present.

    Raises:
        Exception: If the token is invalid.
    """
    try:
        payload = decode_access_token(token)
        return payload.get("data")
    except Exception as e:
        logger.error(f"Failed to decode state token: {str(e)}")
        raise Exception(f"Invalid state token: {str(e)}")