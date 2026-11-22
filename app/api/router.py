from fastapi import APIRouter

from app.api.routes import auth, compare, documents, health, members, uploads, versions

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(uploads.router)  # before documents: /documents/upload
api_router.include_router(documents.router)
api_router.include_router(versions.router)
api_router.include_router(compare.router)
api_router.include_router(members.router)
