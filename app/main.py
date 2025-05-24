from fastapi import FastAPI
from app.routes import router as app_routes
from auth.auth_routes import router as auth_routes

app = FastAPI()

# Mount all routers
app.include_router(app_routes)
app.include_router(auth_routes)
