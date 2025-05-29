# utils/db.py

import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# --- Load environment variables ---
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable not set")

# --- Print for Debugging (Optional, remove in production) ---
print(f"✅ Loaded DATABASE_URL: {DATABASE_URL}")

# --- SQLAlchemy Setup ---
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
<<<<<<< HEAD

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
=======
Base = declarative_base()
>>>>>>> 8d73dd69d899bcdfd05e62c74345dc04d083c366
