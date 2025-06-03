# main.py - Enhanced version compatible with your existing code
import sys
import os
import time
import logging
from fastapi import FastAPI
from dotenv import load_dotenv

load_dotenv()

# Your existing path setup
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

# Your existing tags metadata (keep as-is)
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

# Your existing FastAPI middleware imports
from fastapi.middleware.cors import CORSMiddleware
from app.routes import router as app_routes
from auth.auth_routes import router as auth_routes

# Your existing database setup (keep as-is)
from utils.db import Base, engine, SessionLocal
from sqlalchemy import create_engine
from models import user, user_token

# Your existing database configuration
DATABASE_URL = os.environ.get("DATABASE_URL")
if DATABASE_URL is None:
    raise ValueError("DATABASE_URL environment variable not set")

print("Loaded DATABASE_URL:", DATABASE_URL)

# Keep your existing engine creation
engine = create_engine(DATABASE_URL)
Base.metadata.create_all(bind=engine)

# Your existing DB dependency (keep as-is)
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Enhanced FastAPI app (your existing setup + improvements)
app = FastAPI(
    title="Smart Productivity Assistant",
    description="This assistant integrates your calendar, notes, and communication tools.",
    version="1.0.0",
    openapi_tags=tags_metadata
)

# Your existing CORS setup (keep as-is)
origins = [
    "http://localhost:5173",
    "http://localhost:5174",
    "https://chat.data-ai.co"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Your existing permissive setting
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# NEW: Add compatible middleware (safe to add)
try:
    from middleware.compatible_middleware import (
        SecurityHeadersMiddleware,
        RequestLoggingMiddleware,
        BasicRateLimitMiddleware
    )
    
    # Add new middleware (safe additions)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(BasicRateLimitMiddleware)
    
    print("✅ Enhanced middleware loaded successfully")
except ImportError:
    print("⚠️ Enhanced middleware not found - using basic setup")

# Your existing route mounting (keep as-is)
try:
    app.include_router(app_routes, tags=["Chat & Recommendation", "Task Execution", "Utilities"])
except Exception as e:
    print(f"Error including app_routes: {str(e)}")
    raise

app.include_router(auth_routes, tags=["Authentication", "OAuth Integrations"])

# NEW: Add health check endpoints (safe additions)
app_start_time = time.time()

@app.get("/health", tags=["Utilities"])
async def health_check():
    """Enhanced health check endpoint"""
    try:
        # Test database connection using your existing setup
        db = SessionLocal()
        db.execute("SELECT 1")
        db.close()
        db_healthy = True
        db_error = None
    except Exception as e:
        db_healthy = False
        db_error = str(e)
    
    uptime = time.time() - app_start_time
    
    return {
        "healthy": db_healthy,
        "uptime_seconds": round(uptime, 2),
        "version": "1.0.0",
        "database": {
            "healthy": db_healthy,
            "error": db_error
        },
        "timestamp": time.time()
    }

@app.get("/metrics", tags=["Utilities"])
async def get_metrics():
    """Basic metrics endpoint"""
    uptime = time.time() - app_start_time
    
    return {
        "uptime_seconds": round(uptime, 2),
        "version": "1.0.0",
        "environment": "development" if os.getenv("DEBUG", "false").lower() == "true" else "production",
        "database_url_configured": bool(DATABASE_URL),
        "middleware_enabled": True
    }

# NEW: Enhanced error handling (safe addition)
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Better validation error responses"""
    errors = []
    for error in exc.errors():
        errors.append({
            "field": " -> ".join(str(x) for x in error["loc"][1:]),
            "message": error["msg"],
            "type": error["type"]
        })
    
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "message": "Validation failed",
            "errors": errors
        }
    )

@app.exception_handler(500)
async def internal_server_error_handler(request: Request, exc: Exception):
    """Global error handler"""
    logging.error(f"Unhandled error on {request.url.path}: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": "Internal server error",
            "support": "Contact support if this error persists"
        }
    )

# Your existing startup message
if __name__ == "__main__":
    print("🚀 Enhanced Smart Productivity Assistant API starting...")
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )