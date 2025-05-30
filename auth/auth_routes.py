import sys
import requests
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from fastapi import APIRouter, Request, HTTPException, status, Depends, Body
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from utils.db import SessionLocal
from models.user import User
from passlib.context import CryptContext
from utils.jwt_utils import generate_state_token, decode_state_token, create_access_token, create_refresh_token
from utils.token_store import save_tokens, load_tokens
from jose import JWTError
import logging
from cachetools import TTLCache

router = APIRouter()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Use argon2 as the primary scheme, with bcrypt as a fallback
pwd_context = CryptContext(schemes=["argon2", "bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# Cache for user lookups (TTL: 5 minutes)
user_cache = TTLCache(maxsize=100, ttl=300)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class RegisterRequest(BaseModel):
    email: EmailStr
    username: str  # Added username field
    password: str
class LoginRequest(BaseModel):
    identifier: str  # Can be either email or username
    password: str

@router.get("/ping")
def ping():
    return {"message": "pong"}

@router.post("/auth/register")
def register_user(request: RegisterRequest, db: Session = Depends(get_db)):
    # Check if email already exists
    existing_user_by_email = db.query(User).filter(User.email == request.email).first()
    if existing_user_by_email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already exists")

    # Check if username already exists
    existing_user_by_username = db.query(User).filter(User.username == request.username).first()
    if existing_user_by_username:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already exists")

    hashed_password = pwd_context.hash(request.password)
    new_user = User(email=request.email, username=request.username, password_hash=hashed_password)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {"message": "User registered successfully", "user_id": new_user.id}

@router.post("/auth/login")
def login_user(request: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(
        (User.email == request.identifier) | (User.username == request.identifier)
    ).first()
    if not user or not pwd_context.verify(request.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    access_token = create_access_token({"user_id": user.id})
    refresh_token = create_refresh_token({"user_id": user.id})
    logger.info(f"Generated access token for user {user.id}: {access_token}")
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }
def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    try:
        if not token:
            logger.error("No token provided in Authorization header")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No token provided")

        # Log the token for debugging
        logger.debug(f"Received token: {token}")

        payload = decode_state_token(token)
        if payload is None:
            logger.error("Token payload is None after decoding")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token: payload is None")

        user_id = payload if isinstance(payload, str) else payload.get("user_id")
        if not user_id:
            logger.error("Token payload does not contain user_id")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token: missing user_id")

        cache_key = f"user_{user_id}"
        if cache_key in user_cache:
            logger.info(f"Returning cached user for user_id {user_id}")
            return user_cache[cache_key]

        user = db.query(User).filter(User.id == int(user_id)).first()
        if not user:
            logger.error(f"User not found for user_id {user_id}")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        user_cache[cache_key] = user
        return user
    except Exception as e:
        logger.error(f"Error decoding token: {str(e)}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid or expired token: {str(e)}") 

@router.get("/auth/me")
def get_logged_in_user(current_user: User = Depends(get_current_user)):
    return {"id": current_user.id, "email": current_user.email, "username": current_user.username}

@router.get("/auth/google_meet")
def auth_google_meet(current_user: User = Depends(get_current_user)):
    state_token = generate_state_token(str(current_user.id))
    auth_url = (
        f"https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={os.getenv('GOOGLE_CLIENT_ID')}&"
        f"redirect_uri={os.getenv('GOOGLE_REDIRECT_URI')}&"
        f"response_type=code&"
        f"scope=https://www.googleapis.com/auth/calendar.events https://www.googleapis.com/auth/userinfo.email&"
        f"access_type=offline&"
        f"state={state_token}"
    )
    return RedirectResponse(auth_url)

@router.get("/auth/google_meet/callback")
def google_meet_callback(request: Request, db: Session = Depends(get_db)):
    code = request.query_params.get("code")
    state = request.query_params.get("state")

    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state")

    try:
        user_id = decode_state_token(state)
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid state token: {str(e)}")

    token_url = "https://oauth2.googleapis.com/token"
    payload = {
        "code": code,
        "client_id": os.getenv("GOOGLE_CLIENT_ID"),
        "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
        "redirect_uri": os.getenv("GOOGLE_REDIRECT_URI"),
        "grant_type": "authorization_code"
    }

    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    res = requests.post(token_url, data=payload, headers=headers)

    if res.status_code != 200:
        raise HTTPException(status_code=500, detail="Google token exchange failed")

    token_data = res.json()
    save_tokens(user_id, {"google_meet": token_data})

    return {"message": "Google Meet authorized successfully", "details": token_data}

@router.post("/auth/logout")
def logout_user():
    return {"message": "Successfully logged out"}

@router.get("/auth/zoom")
def auth_zoom(current_user: User = Depends(get_current_user)):
    state_token = generate_state_token(str(current_user.id))
    zoom_auth_url = f"https://zoom.us/oauth/authorize?response_type=code&client_id={os.getenv('ZOOM_CLIENT_ID')}&redirect_uri={os.getenv('ZOOM_REDIRECT_URI')}&state={state_token}"
    return RedirectResponse(zoom_auth_url)

@router.get("/auth/zoom/callback")
def zoom_callback(request: Request, db: Session = Depends(get_db)):
    code = request.query_params.get("code")
    state = request.query_params.get("state")

    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state")

    try:
        user_id = decode_state_token(state)
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid state token: {str(e)}")

    token_url = "https://zoom.us/oauth/token"
    headers = {"Authorization": f"Basic {os.getenv('ZOOM_BASIC_AUTH')}"}
    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": os.getenv("ZOOM_REDIRECT_URI")
    }

    res = requests.post(token_url, headers=headers, data=payload)
    logger.info("Exchanging token for Zoom for user_id: %s", user_id)
    if res.status_code != 200:
        logger.error("Zoom token response: %s", res.text)
        raise HTTPException(status_code=500, detail="Zoom token exchange failed")

    token_data = res.json()
    logger.info("Zoom token data: %s", token_data)
    save_tokens(user_id, {"zoom": token_data})
    return {"message": "Zoom authorized successfully", "details": token_data}

@router.get("/auth/slack")
def auth_slack(current_user: User = Depends(get_current_user)):
    state_token = generate_state_token(str(current_user.id))
    slack_auth_url = f"https://slack.com/oauth/v2/authorize?client_id={os.getenv('SLACK_CLIENT_ID')}&scope=chat:write,channels:read,users:read&redirect_uri={os.getenv('SLACK_REDIRECT_URI')}&state={state_token}"
    return RedirectResponse(slack_auth_url)

@router.get("/auth/slack/callback")
def slack_callback(request: Request, db: Session = Depends(get_db)):
    code = request.query_params.get("code")
    state = request.query_params.get("state")

    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state")

    try:
        user_id = decode_state_token(state)
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid state token: {str(e)}")

    token_url = "https://slack.com/api/oauth.v2.access"
    payload = {
        "code": code,
        "client_id": os.getenv("SLACK_CLIENT_ID"),
        "client_secret": os.getenv("SLACK_CLIENT_SECRET"),
        "redirect_uri": os.getenv("SLACK_REDIRECT_URI")
    }

    res = requests.post(token_url, data=payload)
    logger.info("Exchanging token for Slack for user_id: %s", user_id)
    if res.status_code != 200 or not res.json().get("ok"):
        logger.error("Slack token response: %s", res.text)
        raise HTTPException(status_code=500, detail="Slack token exchange failed")

    token_data = res.json()
    logger.info("Slack token data: %s", token_data)
    save_tokens(user_id, {"slack": token_data})
    return {"message": "Slack authorized successfully", "details": token_data}

@router.get("/auth/google")
def auth_google(current_user: User = Depends(get_current_user)):
    state_token = generate_state_token(str(current_user.id))
    google_auth_url = (
        f"https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={os.getenv('GOOGLE_CLIENT_ID')}&"
        f"redirect_uri={os.getenv('GOOGLE_REDIRECT_URI')}&"
        f"response_type=code&"
        f"scope=https://www.googleapis.com/auth/calendar.events https://www.googleapis.com/auth/userinfo.email&"
        f"access_type=offline&"
        f"state={state_token}"
    )
    return RedirectResponse(google_auth_url)

@router.get("/auth/google/callback")
def google_callback(request: Request, db: Session = Depends(get_db)):
    code = request.query_params.get("code")
    state = request.query_params.get("state")

    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state")

    try:
        user_id = decode_state_token(state)
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid state token: {str(e)}")

    token_url = "https://oauth2.googleapis.com/token"
    payload = {
        "code": code,
        "client_id": os.getenv("GOOGLE_CLIENT_ID"),
        "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
        "redirect_uri": os.getenv("GOOGLE_REDIRECT_URI"),
        "grant_type": "authorization_code"
    }

    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    res = requests.post(token_url, data=payload, headers=headers)
    logger.info("Exchanging token for Google for user_id: %s", user_id)

    if res.status_code != 200:
        logger.error("Google token response: %s", res.text)
        raise HTTPException(status_code=500, detail="Google token exchange failed")

    token_data = res.json()
    logger.info("Google token data: %s", token_data)
    save_tokens(user_id, {"google": token_data})

    return {"message": "Google authorized successfully", "details": token_data}

@router.get("/auth/notion")
def auth_notion(current_user: User = Depends(get_current_user)):
    state_token = generate_state_token(str(current_user.id))
    notion_auth_url = (
        f"https://api.notion.com/v1/oauth/authorize?"
        f"owner=user&client_id={os.getenv('NOTION_CLIENT_ID')}&"
        f"redirect_uri={os.getenv('NOTION_REDIRECT_URI')}&"
        f"response_type=code&state={state_token}"
    )
    return RedirectResponse(notion_auth_url)

@router.get("/auth/notion/callback")
def notion_callback(request: Request, db: Session = Depends(get_db)):
    code = request.query_params.get("code")
    state = request.query_params.get("state")

    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state")

    try:
        user_id = decode_state_token(state)
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid state token: {str(e)}")

    token_url = "https://api.notion.com/v1/oauth/token"
    headers = {"Content-Type": "application/json"}
    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": os.getenv("NOTION_REDIRECT_URI"),
        "client_id": os.getenv("NOTION_CLIENT_ID"),
        "client_secret": os.getenv("NOTION_CLIENT_SECRET")
    }

    res = requests.post(token_url, json=payload, headers=headers)

    if res.status_code != 200:
        raise HTTPException(status_code=500, detail="Notion token exchange failed")

    token_data = res.json()
    save_tokens(user_id, {"notion": token_data})

    return {"message": "Notion authorized successfully", "details": token_data}

@router.get("/auth/tokens")
def view_tokens(current_user: User = Depends(get_current_user)):
    tokens = load_tokens(str(current_user.id))
    if not tokens:
        raise HTTPException(status_code=404, detail="No tokens found")
    for provider in tokens:
        token = tokens[provider]
        if "access_token" in token:
            token["access_token"] = "****" + token["access_token"][-4:]
        if "refresh_token" in token:
            token["refresh_token"] = "****" + token["refresh_token"][-4:]
    return {"tokens": tokens}

@router.post("/auth/refresh")
async def refresh_token(refresh_token: str = Body(...)):
    try:
        payload = decode_state_token(refresh_token)
        user_id = payload if isinstance(payload, str) else payload.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid refresh token")
        
        user = db.query(User).filter(User.id == int(user_id)).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        new_access_token = create_access_token({"user_id": user_id})
        return {
            "access_token": new_access_token,
            "token_type": "bearer"
        }
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid or expired refresh token: {str(e)}")