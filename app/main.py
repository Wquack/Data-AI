import sys
import os
sys.path.append(os.path.abspath(os.path.dirname(__file__)))
from fastapi import FastAPI
from dotenv import load_dotenv

load_dotenv()

tags_metadata = [
    {
        "name": "Authentication",
        "description": "APIs for user registration, login, logout, and auth token management.",
    },
    {
        "name": "OAuth Integrations",
        "description": "Connect third-party services like Google, Zoom, Notion, and Slack securely using OAuth2.",
    },
    {
        "name": "Chat & Recommendation",
        "description": "Conversational endpoints including AI-powered chat, calendar fetch, suggestion logic.",
    },
    {
        "name": "Task Execution",
        "description": "Execute automated actions such as scheduling meetings, posting to Slack, or writing to Notion.",
    },
    {
        "name": "Utilities",
        "description": "General purpose utilities like ping, file downloads, and token viewers.",
    },
]
from fastapi.middleware.cors import CORSMiddleware
from app.routes import router as app_routes
from auth.auth_routes import router as auth_routes
from utils.db import Base, engine, SessionLocal
from sqlalchemy import create_engine
from models import user, user_token
from fastapi.middleware.cors import CORSMiddleware

DATABASE_URL = os.environ.get("DATABASE_URL")
if DATABASE_URL is None:
    raise ValueError("DATABASE_URL environment variable not set")

print("Loaded DATABASE_URL:", DATABASE_URL)

engine = create_engine(DATABASE_URL)

Base.metadata.create_all(bind=engine)

# --- DB Dependency ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()



app = FastAPI(
    title="Smart Productivity Assistant",
    description="This assistant integrates your calendar, notes, and communication tools.",
    version="1.0.0",
    openapi_tags=tags_metadata
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount all routers
try:
    app.include_router(app_routes, tags=["Chat & Recommendation", "Task Execution", "Utilities"])
except Exception as e:
    print(f"Error including app_routes: {str(e)}")
    raise
app.include_router(auth_routes, tags=["Authentication", "OAuth Integrations"])
