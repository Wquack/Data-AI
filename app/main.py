import sys
import os
sys.path.append(os.path.abspath(os.path.dirname(__file__)))
from fastapi import FastAPI
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

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()



app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount all routers
try:
    app.include_router(app_routes)
except Exception as e:
    print(f"Error including app_routes: {str(e)}")
    raise
app.include_router(auth_routes)