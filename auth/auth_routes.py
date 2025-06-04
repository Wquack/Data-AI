import os
import requests
import base64
from urllib.parse import urlencode
from fastapi import APIRouter, Request, HTTPException, status, Depends, Body
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session
from utils.db import get_db
from models.user import User
from passlib.context import CryptContext
from utils.jwt_utils import generate_state_token, decode_state_token, create_access_token, create_refresh_token, decode_access_token
from utils.token_store import save_tokens, load_tokens, remove_tokens
from jwt import InvalidTokenError  # Updated import
import logging
from cachetools import TTLCache

router = APIRouter()

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Use argon2 as the primary scheme, with bcrypt as a fallback
pwd_context = CryptContext(schemes=["argon2", "bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# Cache for user lookups (TTL: 5 minutes)
user_cache = TTLCache(maxsize=100, ttl=300)

# Models with validation
class RegisterRequest(BaseModel):
    email: EmailStr = Field(..., max_length=255)
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8, max_length=128)

class LoginRequest(BaseModel):
    identifier: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=1, max_length=128)

class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)

# Endpoints
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

    logger.info(f"User registered successfully: user_id={new_user.id}, email={request.email}")
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
        logger.info(f"Token received in header: {token}")
        payload = decode_access_token(token)
        user_id = payload.get("user_id")
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

        user = db.query(User).filter(User.id == int(user_id)).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        return user
    except Exception as e:
        logger.error(f"Token decode error: {str(e)}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

@router.get("/auth/me")
def get_logged_in_user(current_user: User = Depends(get_current_user)):
    return {"id": current_user.id, "email": current_user.email, "username": current_user.username}

@router.get("/auth/verify-token")
def verify_token(current_user: User = Depends(get_current_user)):
    return {"valid": True, "user_id": current_user.id}

@router.delete("/auth/delete")
def delete_user(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user_id = current_user.id

    try:
        # Delete associated tokens
        remove_tokens(str(user_id))

        # Delete the user
        db.delete(current_user)
        db.commit()

        logger.info(f"User {user_id} deleted successfully")
        return {"message": "User deleted successfully"}
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting user {user_id}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete user")

@router.put("/auth/change-password")
def change_password(request: ChangePasswordRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user_id = current_user.id

    # Verify current password
    if not pwd_context.verify(request.current_password, current_user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Incorrect current password")

    # Hash the new password
    hashed_password = pwd_context.hash(request.new_password)

    # Update the password
    current_user.password_hash = hashed_password
    db.commit()

    logger.info(f"Password changed successfully for user {user_id}")
    return {"message": "Password changed successfully"}

# ---- Generic OAuth Helper ----
def generate_oauth_redirect_url(base_url, params):
    encoded_params = urlencode(params, doseq=False)
    url = f"{base_url}?{encoded_params}"
    logger.debug(f"Generated OAuth redirect URL: {url}")
    return url

# ---- Google OAuth ----
@router.get("/auth/google")
def auth_google(current_user: User = Depends(get_current_user)):
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI")
    if not client_id or not redirect_uri:
        raise HTTPException(status_code=500, detail="GOOGLE_CLIENT_ID or GOOGLE_REDIRECT_URI not configured in environment variables")
    
    state_token = generate_state_token(str(current_user.id))
    logger.info(f"Using GOOGLE_REDIRECT_URI for /auth/google: {redirect_uri}")
    
    url = generate_oauth_redirect_url("https://accounts.google.com/o/oauth2/v2/auth", {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "https://www.googleapis.com/auth/calendar.events https://www.googleapis.com/auth/userinfo.email openid",
        "access_type": "offline",
        "state": state_token
    })
    logger.info(f"Generated Google OAuth URL: {url}")
    return {"redirect_url": url}

# In auth/auth_routes.py - Update your google_callback function

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

    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI")
    
    if not client_id or not client_secret or not redirect_uri:
        raise HTTPException(status_code=500, detail="Google OAuth environment variables not configured")

    logger.info(f"Using GOOGLE_REDIRECT_URI for callback: {redirect_uri}")

    # Exchange code for tokens
    res = requests.post("https://oauth2.googleapis.com/token", data={
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code"
    }, headers={"Content-Type": "application/x-www-form-urlencoded"})

    if res.status_code != 200:
        logger.error(f"Google token exchange failed: {res.status_code} {res.text}")
        raise HTTPException(status_code=500, detail="Google token exchange failed")

    token_data = res.json()
    
    # Ensure we save all required fields
    google_tokens = {
        "access_token": token_data.get("access_token"),
        "refresh_token": token_data.get("refresh_token"),  # This is crucial!
        "token_type": token_data.get("token_type", "Bearer"),
        "scope": token_data.get("scope"),
    }
    
    # Add expiry information if available
    if "expires_in" in token_data:
        from datetime import datetime, timedelta
        expires_at = datetime.utcnow() + timedelta(seconds=int(token_data["expires_in"]))
        google_tokens["expires_at"] = expires_at.isoformat()
    
    # Validate that we got the refresh token
    if not google_tokens["refresh_token"]:
        logger.warning(f"No refresh token received for user {user_id}. User may need to re-authorize.")
    
    save_tokens(user_id, {"google": google_tokens})
    logger.info(f"Successfully stored Google tokens for user {user_id}")
    
    return RedirectResponse(url="https://chat.data-ai.co/connect?google=success")

# ---- Zoom OAuth ----
@router.get("/auth/zoom")
def auth_zoom(current_user: User = Depends(get_current_user)):
    client_id = os.getenv("ZOOM_CLIENT_ID")
    redirect_uri = os.getenv("ZOOM_REDIRECT_URI")
    logger.info(f"Zoom client id {client_id}")
    logger.info(f"Zoom uri {redirect_uri}")
    if not client_id or not redirect_uri:
        raise HTTPException(status_code=500, detail="ZOOM_CLIENT_ID or ZOOM_REDIRECT_URI not configured in environment variables")

    state_token = generate_state_token(str(current_user.id))
    url = generate_oauth_redirect_url("https://zoom.us/oauth/authorize", {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "state": state_token
    })
    return {"redirect_url": url}

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

    client_id = os.getenv("ZOOM_CLIENT_ID")
    client_secret = os.getenv("ZOOM_CLIENT_SECRET")
    redirect_uri = os.getenv("ZOOM_REDIRECT_URI")
    if not client_id or not client_secret or not redirect_uri:
        raise HTTPException(status_code=500, detail="ZOOM_CLIENT_ID, ZOOM_CLIENT_SECRET, or ZOOM_REDIRECT_URI not configured in environment variables")

    auth_str = f"{client_id}:{client_secret}"
    auth_b64 = base64.b64encode(auth_str.encode()).decode()
    headers = {
        "Authorization": f"Basic {auth_b64}",
        "Content-Type": "application/x-www-form-urlencoded"
    }

    res = requests.post("https://zoom.us/oauth/token", headers=headers, data={
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri
    })

    if res.status_code != 200:
        logger.error(f"Zoom token response: {res.status_code} {res.text}")
        raise HTTPException(status_code=500, detail="Zoom token exchange failed")

    save_tokens(user_id, {"zoom": res.json()})
    return RedirectResponse(url="https://chat.data-ai.co/connect?zoom=success")

# ---- Slack OAuth ----
@router.get("/auth/slack")
def auth_slack(current_user: User = Depends(get_current_user)):
    client_id = os.getenv("SLACK_CLIENT_ID")
    redirect_uri = os.getenv("SLACK_REDIRECT_URI")
    if not client_id or not redirect_uri:
        raise HTTPException(status_code=500, detail="SLACK_CLIENT_ID or SLACK_REDIRECT_URI not configured in environment variables")

    state_token = generate_state_token(str(current_user.id))
    url = generate_oauth_redirect_url("https://slack.com/oauth/v2/authorize", {
        "client_id": client_id,
        "scope": "chat:write,channels:read,users:read",
        "redirect_uri": redirect_uri,
        "state": state_token
    })
    return {"redirect_url": url}

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

    client_id = os.getenv("SLACK_CLIENT_ID")
    client_secret = os.getenv("SLACK_CLIENT_SECRET")
    redirect_uri = os.getenv("SLACK_REDIRECT_URI")
    if not client_id or not client_secret or not redirect_uri:
        raise HTTPException(status_code=500, detail="SLACK_CLIENT_ID, SLACK_CLIENT_SECRET, or SLACK_REDIRECT_URI not configured in environment variables")

    res = requests.post("https://slack.com/api/oauth.v2.access", data={
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri
    }, headers={"Content-Type": "application/x-www-form-urlencoded"})

    if res.status_code != 200 or not res.json().get("ok"):
        logger.error(f"Slack token response: {res.status_code} {res.text}")
        raise HTTPException(status_code=500, detail="Slack token exchange failed")

    save_tokens(user_id, {"slack": res.json()})
    return RedirectResponse(url="https://chat.data-ai.co/connect?slack=success")

# ---- Notion OAuth ----
@router.get("/auth/notion")
def auth_notion(current_user: User = Depends(get_current_user)):
    client_id = os.getenv("NOTION_CLIENT_ID")
    redirect_uri = os.getenv("NOTION_REDIRECT_URI")
    if not client_id or not redirect_uri:
        raise HTTPException(status_code=500, detail="NOTION_CLIENT_ID or NOTION_REDIRECT_URI not configured in environment variables")

    state_token = generate_state_token(str(current_user.id))
    url = generate_oauth_redirect_url("https://api.notion.com/v1/oauth/authorize", {
        "owner": "user",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "state": state_token
    })
    return {"redirect_url": url}

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

    client_id = os.getenv("NOTION_CLIENT_ID")
    client_secret = os.getenv("NOTION_CLIENT_SECRET")
    redirect_uri = os.getenv("NOTION_REDIRECT_URI")
    
    if not client_id or not client_secret or not redirect_uri:
        raise HTTPException(status_code=500, detail="NOTION_CLIENT_ID, NOTION_CLIENT_SECRET, or NOTION_REDIRECT_URI not configured")

    auth_str = f"{client_id}:{client_secret}"
    auth_b64 = base64.b64encode(auth_str.encode()).decode()
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Basic {auth_b64}",
        "Notion-Version": "2022-06-28"
    }

    res = requests.post("https://api.notion.com/v1/oauth/token", headers=headers, json={
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri
    })

    if res.status_code != 200:
        logger.error(f"Notion token response: {res.status_code} {res.text}")
        raise HTTPException(status_code=500, detail="Notion token exchange failed")

    token_data = res.json()
    
    # Store the complete token response
    save_tokens(user_id, {"notion": token_data})
    
    logger.info(f"Successfully stored Notion tokens for user {user_id}")
    logger.info(f"User has access to workspace: {token_data.get('workspace_name', 'Unknown')}")
    
    return RedirectResponse(url="https://chat.data-ai.co/connect?notion=success")

# ---- Token Viewer ----
@router.get("/auth/tokens")
def view_tokens(current_user: User = Depends(get_current_user)):
    token_data = load_tokens(str(current_user.id))
    if not token_data:
        logger.info(f"No tokens found for user {current_user.id}")
        raise HTTPException(status_code=404, detail="No tokens found for current user")
    logger.info(f"Retrieved tokens for user {current_user.id}: {list(token_data.keys())}")
    return {"tokens": token_data}