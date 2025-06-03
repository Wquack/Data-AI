# middleware/compatible_middleware.py - Works with your existing setup
import time
import logging
from typing import Dict
from collections import defaultdict, deque
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import asyncio

logger = logging.getLogger(__name__)

class SimpleRateLimiter:
    """Simple rate limiter compatible with your system"""
    
    def __init__(self, max_requests: int = 100, window_seconds: int = 3600):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[str, deque] = defaultdict(deque)
    
    def is_allowed(self, identifier: str) -> bool:
        """Check if request is allowed"""
        now = time.time()
        window_start = now - self.window_seconds
        
        # Clean old requests
        user_requests = self.requests[identifier]
        while user_requests and user_requests[0] < window_start:
            user_requests.popleft()
        
        # Check if under limit
        if len(user_requests) < self.max_requests:
            user_requests.append(now)
            return True
        
        return False

class BasicRateLimitMiddleware(BaseHTTPMiddleware):
    """Basic rate limiting that works with your existing middleware"""
    
    def __init__(self, app):
        super().__init__(app)
        self.limiter = SimpleRateLimiter(max_requests=100, window_seconds=3600)
        self.exempt_paths = {"/ping", "/health", "/docs", "/openapi.json"}
    
    def get_client_ip(self, request: Request) -> str:
        """Get client IP address"""
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()
        
        client_ip = request.client.host if request.client else "unknown"
        return client_ip
    
    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for exempt paths
        if request.url.path in self.exempt_paths:
            return await call_next(request)
        
        # Check rate limit
        client_ip = self.get_client_ip(request)
        if not self.limiter.is_allowed(client_ip):
            logger.warning(f"Rate limit exceeded for {client_ip} on {request.url.path}")
            return JSONResponse(
                status_code=429,
                content={"error": "Rate limit exceeded", "message": "Too many requests"}
            )
        
        return await call_next(request)

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Simple request logging compatible with your system"""
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # Log request
        logger.info(f"{request.method} {request.url.path} - Started")
        
        try:
            response = await call_next(request)
            
            # Calculate duration
            duration = time.time() - start_time
            duration_ms = round(duration * 1000, 2)
            
            # Add response time header
            response.headers["X-Response-Time"] = f"{duration_ms}ms"
            
            # Log response
            log_level = "ERROR" if response.status_code >= 400 else "INFO"
            logger.log(
                getattr(logging, log_level),
                f"{request.method} {request.url.path} - {response.status_code} in {duration_ms}ms"
            )
            
            return response
            
        except Exception as e:
            duration = time.time() - start_time
            duration_ms = round(duration * 1000, 2)
            
            logger.error(f"{request.method} {request.url.path} - ERROR in {duration_ms}ms: {str(e)}")
            raise

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Basic security headers that work with your CORS setup"""
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # Add security headers (compatible with your CORS)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        
        # Only add HSTS for HTTPS
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        
        return response