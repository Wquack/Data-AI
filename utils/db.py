# utils/db_enhanced.py - Compatible with your existing db.py
import os
import logging
from typing import Generator
from contextlib import asynccontextmanager
from sqlalchemy import create_engine, event, pool
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.exc import DisconnectionError, OperationalError
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Keep your existing setup but enhance it
DATABASE_URL = os.environ.get("DATABASE_URL")
if DATABASE_URL is None:
    raise ValueError("DATABASE_URL environment variable not set")

# Enhanced engine configuration (compatible with your setup)
ENGINE_CONFIG = {
    "poolclass": QueuePool,
    "pool_size": 10,
    "max_overflow": 20,
    "pool_timeout": 30,
    "pool_recycle": 3600,
    "pool_pre_ping": True,
    "echo": False,  # Set to True for debugging
}

# Create enhanced engine
engine = create_engine(DATABASE_URL, **ENGINE_CONFIG)

# Keep your existing SessionLocal
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Keep your existing Base
Base = declarative_base()

# Connection event handlers
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Optimize SQLite if used"""
    if "sqlite" in DATABASE_URL:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

# Enhanced get_db with retry logic (compatible with your signature)
def get_db() -> Generator[Session, None, None]:
    """Enhanced database dependency with retry logic"""
    max_retries = 3 
    for attempt in range(max_retries):
        db = SessionLocal()
        try:
            yield db
            break
        except (DisconnectionError, OperationalError) as e:
            db.close()
            if attempt == max_retries - 1:
                logger.error(f"Database connection failed after {max_retries} attempts: {e}")
                raise
            logger.warning(f"Database attempt {attempt + 1} failed, retrying: {e}")
        except Exception as e:
            logger.error(f"Database session error: {e}")
            raise
        finally:
            db.close()

# Keep your existing create_all functionality
def create_tables():
    """Create all database tables"""
    Base.metadata.create_all(bind=engine)

# Add health check function
def check_database_health() -> dict:
    """Check database connectivity"""
    try:
        db = SessionLocal()
        db.execute("SELECT 1")
        db.close()
        return {"healthy": True}
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {"healthy": False, "error": str(e)}

# Add pool monitoring
def get_pool_status() -> dict:
    """Get connection pool status"""
    pool = engine.pool
    return {
        "size": pool.size(),
        "checked_in": pool.checkedin(),
        "checked_out": pool.checkedout(),
        "overflow": pool.overflow(),
    }