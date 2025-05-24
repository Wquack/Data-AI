from fastapi import FastAPI
from app.routes import router as app_routes
from auth.auth_routes import router as auth_routes
from utils.db import Base, engine, SessionLocal
import os
from sqlalchemy import create_engine
from models import user, user_token

DATABASE_URL = os.environ.get("DATABASE_URL")
if DATABASE_URL is None:
    raise ValueError("DATABASE_URL environment variable not set")

engine = create_engine(DATABASE_URL)

Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

app = FastAPI()

# Mount all routers
app.include_router(app_routes)
app.include_router(auth_routes)
