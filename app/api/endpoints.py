# app/api/endpoints.py
from fastapi import APIRouter

# import feature routers
from app.api.status import router as status_router
from app.api.meetings import router as meetings_router

router = APIRouter()
router.include_router(status_router)
router.include_router(meetings_router)

# If later you add more: router.include_router(users_router), etc.
