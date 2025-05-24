from fastapi import APIRouter, HTTPException, Depends, Request
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr
from models.user import User
from utils.db import SessionLocal
from utils.jwt_utils import create_access_token, decode_access_token
from fastapi.security import OAuth2PasswordBearer

router = APIRouter()

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

@router.post("/auth/register")
def register_user(data: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter_by(email=data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="User already exists")

    hashed_pw = pwd_context.hash(data.password)
    new_user = User(email=data.email, password_hash=hashed_pw)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"message": "User registered successfully"}

@router.post("/auth/login")
def login_user(data: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(email=data.email).first()
    if not user or not pwd_context.verify(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token({"user_id": user.email})
    return {"message": "Login successful", "token": token}

# Middleware Dependency
async def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = decode_access_token(token)
        return payload["user_id"]
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

# Protected test route
@router.get("/auth/protected")
def protected_route(user_id: str = Depends(get_current_user)):
    return {"message": f"Welcome, {user_id}. You have access to protected resources."}
