import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers.compare_router import router as compare_router
from app.routers.document_router import router as document_router
from app.routers.user_router import router as user_router
from app.routers.version_router import router as version_router


settings = get_settings()

logging.basicConfig(level=logging.INFO)

app = FastAPI(title=settings.app_name, version=settings.app_version)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
@app.get("/")
def root():
    return {"message": "Smart Legal Document Manager API is running"}

@app.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(document_router)
app.include_router(version_router)
app.include_router(compare_router)
app.include_router(user_router)
