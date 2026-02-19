from fastapi import APIRouter
from app.api import health
from app.api.api_v1.endpoints import login, users, widgets

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(login.router, tags=["login"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(widgets.router, prefix="/widgets", tags=["widgets"])
