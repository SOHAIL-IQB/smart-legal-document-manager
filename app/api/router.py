from fastapi import APIRouter

from app.api.routes import auth, compare, documents, health, members, versions

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(documents.router)
api_router.include_router(versions.router)
api_router.include_router(compare.router)
api_router.include_router(members.router)
