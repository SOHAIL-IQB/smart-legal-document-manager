import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import get_settings
from app.core.errors import error_body, register_exception_handlers

settings = get_settings()

# Room for multipart boundaries and form fields on top of the file itself.
_MULTIPART_OVERHEAD = 64 * 1024

logging.basicConfig(level=logging.INFO)


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url=f"{settings.api_prefix}/docs",
        openapi_url=f"{settings.api_prefix}/openapi.json",
        redoc_url=None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
    )
    register_exception_handlers(app)

    @app.middleware("http")
    async def reject_oversized_uploads(request: Request, call_next):  # type: ignore[no-untyped-def]
        """Refuse big uploads from the Content-Length header, before the body is parsed.

        Uploads without a Content-Length are still capped when the route reads the file.
        """
        if request.method == "POST" and request.url.path.endswith("/upload"):
            limit = get_settings().max_upload_bytes + _MULTIPART_OVERHEAD
            declared = request.headers.get("content-length", "")
            if declared.isdigit() and int(declared) > limit:
                megabytes = get_settings().max_upload_bytes / (1024 * 1024)
                return JSONResponse(
                    status_code=413,
                    content=error_body(
                        "payload_too_large", f"Files can be at most {megabytes:g} MB."
                    ),
                )
        return await call_next(request)

    app.include_router(api_router, prefix=settings.api_prefix)

    @app.get("/", include_in_schema=False)
    def root() -> dict[str, str]:
        return {
            "message": f"{settings.app_name} API is running",
            "docs": f"{settings.api_prefix}/docs",
        }

    return app


app = create_app()
