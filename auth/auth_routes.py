import sys
import requests
import os
from urllib.parse import urlencode
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
from utils.token_store import remove_tokens

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
        "refresh_token": refresh_token,  # Ensure this is included
        "token_type": "bearer"
    }

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    try:
        payload = decode_state_token(token)
        user_id = payload.get("user_id")
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

        user = db.query(User).filter(User.id == int(user_id)).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        return user
    except JWTError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    
    except Exception as e:
        logger.error(f"Error decoding token: {str(e)}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid or expired token: {str(e)}")
@router.get("/auth/me")
def get_logged_in_user(current_user: User = Depends(get_current_user)):
    return {"id": current_user.id, "email": current_user.email, "username": current_user.username}

# ---- Generic OAuth Helper ----
def generate_oauth_redirect_url(base_url, params):
    return f"{base_url}?{urlencode(params)}"

# ---- Google OAuth ----
@router.get("/auth/google")
def auth_google(current_user: User = Depends(get_current_user)):
    state_token = generate_state_token(str(current_user.id))
    url = generate_oauth_redirect_url("https://accounts.google.com/o/oauth2/v2/auth", {
        "client_id": os.getenv("GOOGLE_CLIENT_ID"),
        "redirect_uri": os.getenv("GOOGLE_REDIRECT_URI"),
        "response_type": "code",
        "scope": "https://www.googleapis.com/auth/calendar.events https://www.googleapis.com/auth/userinfo.email",
        "access_type": "offline",
        "state": state_token
    })
    return {"redirect_url": url}

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

    res = requests.post("https://oauth2.googleapis.com/token", data={
        "code": code,
        "client_id": os.getenv("GOOGLE_CLIENT_ID"),
        "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
        "redirect_uri": os.getenv("GOOGLE_REDIRECT_URI"),
        "grant_type": "authorization_code"
    }, headers={"Content-Type": "application/x-www-form-urlencoded"})

    if res.status_code != 200:
        raise HTTPException(status_code=500, detail="Google token exchange failed")

    save_tokens(user_id, {"google": res.json()})
    return {"message": "Google authorized successfully"}

# ---- Zoom OAuth ----
@router.get("/auth/zoom")
def auth_zoom(current_user: User = Depends(get_current_user)):
    state_token = generate_state_token(str(current_user.id))
    url = generate_oauth_redirect_url("https://zoom.us/oauth/authorize", {
        "client_id": os.getenv("ZOOM_CLIENT_ID"),
        "redirect_uri": os.getenv("ZOOM_REDIRECT_URI"),
        "response_type": "code",
        "state": state_token
    })
    return {"redirect_url": url}

@router.get("/auth/zoom/callback")
def zoom_callback(request: Request):
    code = request.query_params.get("code")
    state = request.query_params.get("state")
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state")
    try:
        user_id = decode_state_token(state)
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid state token: {str(e)}")

    res = requests.post("https://zoom.us/oauth/token", headers={
        "Authorization": f"Basic {os.getenv('ZOOM_BASIC_AUTH')}"
    }, data={
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": os.getenv("ZOOM_REDIRECT_URI")
    })

    if res.status_code != 200:
        logger.error("Zoom token response: %s", res.text)
        raise HTTPException(status_code=500, detail="Zoom token exchange failed")

    save_tokens(user_id, {"zoom": res.json()})
    return {"message": "Zoom authorized successfully"}

# ---- Slack OAuth ----
@router.get("/auth/slack")
def auth_slack(current_user: User = Depends(get_current_user)):
    state_token = generate_state_token(str(current_user.id))
    url = generate_oauth_redirect_url("https://slack.com/oauth/v2/authorize", {
        "client_id": os.getenv("SLACK_CLIENT_ID"),
        "scope": "chat:write,channels:read,users:read",
        "redirect_uri": os.getenv("SLACK_REDIRECT_URI"),
        "state": state_token
    })
    return {"redirect_url": url}

@router.get("/auth/slack/callback")
def slack_callback(request: Request):
    code = request.query_params.get("code")
    state = request.query_params.get("state")
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state")
    try:
        user_id = decode_state_token(state)
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid state token: {str(e)}")

    res = requests.post("https://slack.com/api/oauth.v2.access", data={
        "code": code,
        "client_id": os.getenv("SLACK_CLIENT_ID"),
        "client_secret": os.getenv("SLACK_CLIENT_SECRET"),
        "redirect_uri": os.getenv("SLACK_REDIRECT_URI")
    })

    if res.status_code != 200 or not res.json().get("ok"):
        logger.error("Slack token response: %s", res.text)
        raise HTTPException(status_code=500, detail="Slack token exchange failed")

    save_tokens(user_id, {"slack": res.json()})
    return {"message": "Slack authorized successfully"}

# ---- Notion OAuth ----
@router.get("/auth/notion")
def auth_notion(current_user: User = Depends(get_current_user)):
    state_token = generate_state_token(str(current_user.id))
    url = generate_oauth_redirect_url("https://api.notion.com/v1/oauth/authorize", {
        "owner": "user",
        "client_id": os.getenv("NOTION_CLIENT_ID"),
        "redirect_uri": os.getenv("NOTION_REDIRECT_URI"),
        "response_type": "code",
        "state": state_token
    })
    return {"redirect_url": url}

@router.get("/auth/notion/callback")
def notion_callback(request: Request):
    code = request.query_params.get("code")
    state = request.query_params.get("state")
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state")
    try:
        user_id = decode_state_token(state)
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid state token: {str(e)}")

    res = requests.post("https://api.notion.com/v1/oauth/token", headers={
        "Content-Type": "application/json"
    }, json={
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": os.getenv("NOTION_REDIRECT_URI"),
        "client_id": os.getenv("NOTION_CLIENT_ID"),
        "client_secret": os.getenv("NOTION_CLIENT_SECRET")
    })

    if res.status_code != 200:
        raise HTTPException(status_code=500, detail="Notion token exchange failed")

    save_tokens(user_id, {"notion": res.json()})
    return {"message": "Notion authorized successfully"}

# ✅ Phase IV: Token viewer
@router.get("/auth/tokens")
def view_tokens(current_user: User = Depends(get_current_user)):
    token_data = load_tokens(str(current_user.id))
    if not token_data:
        raise HTTPException(status_code=404, detail="No tokens found for current user")
    return {"tokens": token_data}

@router.get("/auth/verify-token")
def verify_token(current_user: User = Depends(get_current_user)):
    return {"valid": True, "user_id": current_user.id}

@router.delete("/auth/delete")
def delete_user(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user_id = current_user.id
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    try:
        # Delete associated tokens
        remove_tokens(user_id)

        # Delete the user
        db.delete(user)
        db.commit()

        logging.info(f"User {user_id} deleted successfully")
        return {"message": "User deleted successfully"}
    except Exception as e:
        db.rollback()
        logging.error(f"Error deleting user {user_id}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete user")

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

@router.put("/auth/change-password")
def change_password(request: ChangePasswordRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user_id = current_user.id
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Verify current password
    if not pwd_context.verify(request.current_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Incorrect current password")

    # Hash the new password
    hashed_password = pwd_context.hash(request.new_password)

   # Update the password
    db.query(User).filter(User.id == user_id).update({"password_hash": str(hashed_password)})
    db.commit()

    logging.info(f"Password changed successfully for user {user_id}")
    return {"message": "Password changed successfully"}
