import sys
import requests
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from fastapi import APIRouter, Request, HTTPException, status, Depends
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from utils.db import SessionLocal
from models.user import User
from passlib.context import CryptContext
from utils.jwt_utils import generate_state_token, decode_state_token, create_access_token
from utils.token_store import save_tokens
from jose import JWTError
import logging

router = APIRouter()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

@router.get("/ping")
def ping():
    return {"message": "pong"}

@router.post("/auth/register")
def register_user(request: RegisterRequest, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.email == request.email).first()
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User already exists")

    hashed_password = pwd_context.hash(request.password)
    new_user = User(email=request.email, password_hash=hashed_password)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {"message": "User registered successfully", "user_id": new_user.id}

@router.post("/auth/login")
def login_user(request: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == request.email).first()
    if not user or not pwd_context.verify(request.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    access_token = create_access_token({"user_id": user.id})
    return {"access_token": access_token, "token_type": "bearer"}

# Middleware to get the current user from the token
def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    try:
        payload = decode_state_token(token)
        user_id = payload if isinstance(payload, str) else payload.get("user_id")
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        user = db.query(User).filter(User.id == int(user_id)).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        return user
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

@router.get("/auth/me")
def get_logged_in_user(current_user: User = Depends(get_current_user)):
    return {"id": current_user.id, "email": current_user.email}

@router.post("/auth/logout")
def logout_user():
    return {"message": "Successfully logged out"}

# ✅ Zoom OAuth state-secure auth redirect
@router.get("/auth/zoom")
def auth_zoom(current_user: User = Depends(get_current_user)):
    state_token = generate_state_token(current_user.id)
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

    # Exchange code for access token
    token_url = "https://zoom.us/oauth/token"
    headers = {"Authorization": f"Basic {os.getenv('ZOOM_BASIC_AUTH')}"}  # base64 encoded client_id:client_secret
    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": os.getenv("ZOOM_REDIRECT_URI")
    }

    res = requests.post(token_url, headers=headers, data=payload)
    if res.status_code != 200:
        raise HTTPException(status_code=500, detail="Zoom token exchange failed")

    token_data = res.json()
    save_tokens(user_id, {"zoom": token_data})
    return {"message": "Zoom authorized successfully", "details": token_data}


# ✅ Slack OAuth state-secure auth redirect
@router.get("/auth/slack")
def auth_slack(current_user: User = Depends(get_current_user)):
    state_token = generate_state_token(current_user.id)
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

    # Exchange code for token
    token_url = "https://slack.com/api/oauth.v2.access"
    payload = {
        "code": code,
        "client_id": os.getenv("SLACK_CLIENT_ID"),
        "client_secret": os.getenv("SLACK_CLIENT_SECRET"),
        "redirect_uri": os.getenv("SLACK_REDIRECT_URI")
    }

    res = requests.post(token_url, data=payload)
    if res.status_code != 200 or not res.json().get("ok"):
        raise HTTPException(status_code=500, detail="Slack token exchange failed")

    token_data = res.json()
    save_tokens(user_id, {"slack": token_data})
    return {"message": "Slack authorized successfully", "details": token_data}
