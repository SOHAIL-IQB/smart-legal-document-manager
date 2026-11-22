from fastapi import APIRouter

from app.api.routes import compare, documents, health, users, versions

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(users.router)
api_router.include_router(documents.router)
api_router.include_router(versions.router)
api_router.include_router(compare.router)
