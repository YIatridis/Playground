from fastapi import APIRouter

from app.routers import auth, users, scans, subscriptions


api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(scans.router, prefix="/scans", tags=["scans"])
api_router.include_router(subscriptions.router, prefix="/subscriptions", tags=["subscriptions"])
