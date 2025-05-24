from jose import jwt, JWTError
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

load_dotenv()

JWT_SECRET = os.getenv("JWT_SECRET")
JWT_EXPIRY = int(os.getenv("JWT_EXPIRY_SECONDS", 3600))  # default 1 hour


def create_access_token(data: dict, expires_delta: int = JWT_EXPIRY):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(seconds=expires_delta)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET, algorithm="HS256")


def decode_access_token(token: str):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return payload
    except JWTError as e:
        raise Exception("Invalid or expired token")


# For OAuth `state` flow — reuse token logic
def generate_state_token(user_id: str) -> str:
    return create_access_token({"user_id": user_id})


def decode_state_token(token: str) -> dict:
    payload = decode_access_token(token)
    return payload
