# import jwt
# from datetime import datetime, timedelta, timezone
# import os
# import logging
# from typing import Dict, Optional, Any

# # Force reload environment variables to ensure latest values
# from dotenv import load_dotenv
# load_dotenv()

# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger(__name__)

# JWT_SECRET: str = os.getenv("JWT_SECRET", "your-secret-key")
# JWT_ALGORITHM: str = "HS256"
# ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
# REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

# logger.info(f"Loaded JWT_SECRET: {JWT_SECRET[:10]}... (first 10 chars for security)")
# logger.info(f"Loaded ACCESS_TOKEN_EXPIRE_MINUTES: {ACCESS_TOKEN_EXPIRE_MINUTES}")
# logger.info(f"Loaded REFRESH_TOKEN_EXPIRE_DAYS: {REFRESH_TOKEN_EXPIRE_DAYS}")

# def create_access_token(data: Dict[str, Any]) -> str:
#     to_encode = data.copy()
#     expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
#     logger.info(f"Setting access token expiration to {expire} (UTC)")
#     to_encode.update({"exp": expire, "type": "access"})
#     logger.debug(f"Using JWT_SECRET for encoding: {JWT_SECRET[:10]}...")
#     encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
#     if len(encoded_jwt.split('.')) != 3:
#         logger.error(f"Invalid JWT token generated: {encoded_jwt}")
#         raise ValueError("Failed to generate a valid JWT token")
#     logger.debug(f"Created access token with expiration in {ACCESS_TOKEN_EXPIRE_MINUTES} minutes: {encoded_jwt}")
#     return encoded_jwt

# def create_refresh_token(data: Dict[str, Any]) -> str:
#     to_encode = data.copy()
#     expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
#     logger.info(f"Setting refresh token expiration to {expire} (UTC)")
#     to_encode.update({"exp": expire, "type": "refresh"})
#     logger.debug(f"Using JWT_SECRET for encoding: {JWT_SECRET[:10]}...")
#     encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
#     if len(encoded_jwt.split('.')) != 3:
#         logger.error(f"Invalid JWT refresh token generated: {encoded_jwt}")
#         raise ValueError("Failed to generate a valid JWT refresh token")
#     logger.debug(f"Created refresh token with expiration in {REFRESH_TOKEN_EXPIRE_DAYS} days: {encoded_jwt}")
#     return encoded_jwt

# def decode_access_token(token: str) -> Dict[str, Any]:
#     try:
#         logger.debug(f"Using JWT_SECRET for decoding: {JWT_SECRET[:10]}...")
#         payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
#         return payload
#     except Exception as e:
#         logger.error(f"Failed to decode access token: {str(e)}")
#         raise Exception("Invalid or expired token")

# def generate_state_token(data: str) -> str:
#     logger.debug(f"Using JWT_SECRET for encoding: {JWT_SECRET[:10]}...")
#     encoded_jwt = jwt.encode({"data": data}, JWT_SECRET, algorithm=JWT_ALGORITHM)
#     logger.debug(f"Generated state token: {encoded_jwt}")
#     return encoded_jwt

# def decode_state_token(token: str) -> dict:
#     try:
#         payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
#         return payload
#     except JWTError as e:
#         raise e

import jwt
from datetime import datetime, timedelta, timezone
import os
import logging
from typing import Dict, Optional, Any
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

JWT_SECRET: str = os.getenv("JWT_SECRET", "your-secret-key")
JWT_ALGORITHM: str = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

def create_access_token(data: Dict[str, Any]) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)

def create_refresh_token(data: Dict[str, Any]) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)

def decode_access_token(token: str) -> Dict[str, Any]:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except Exception as e:
        logger.error(f"Failed to decode access token: {str(e)}")
        raise Exception("Invalid or expired token")

def generate_state_token(user_id: str) -> str:
    return jwt.encode({"user_id": user_id}, JWT_SECRET, algorithm=JWT_ALGORITHM)

def decode_state_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except Exception as e:
        logger.error(f"Failed to decode state token: {str(e)}")
        raise Exception("Invalid or expired token")
