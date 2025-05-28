from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import router as app_routes
from auth.auth_routes import router as auth_routes
from utils.db import Base, engine, SessionLocal
from models import user, user_token  # Ensure this imports all models
import os

# --- Create Tables ---
Base.metadata.create_all(bind=engine)

# --- DB Dependency ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- FastAPI App ---
app = FastAPI()

# --- CORS Setup ---
origins = [
    "http://localhost:5173",
    "https://chat.data-ai.co"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Include Routers ---
app.include_router(app_routes)
app.include_router(auth_routes)
