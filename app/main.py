from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core import metrics
from app.core.config import get_settings
from app.core.errors import error_body, register_exception_handlers
from app.core.headers import SecurityHeadersMiddleware
from app.core.limits import BodySizeLimitMiddleware
from app.core.logging import RequestContextMiddleware, configure_logging

settings = get_settings()

configure_logging(settings.log_level)


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url=f"{settings.api_prefix}/docs",
        openapi_url=f"{settings.api_prefix}/openapi.json",
        redoc_url=None,
    )

    # Added first, so it runs inside CORS: a 413 still carries CORS headers the browser can read.
    # It runs before any route reads the body (review finding R1).
    app.add_middleware(BodySizeLimitMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
    )
    register_exception_handlers(app)
    # Request IDs and access logs wrap CORS and the body limit, so even 413s and preflights get
    # an ID; the security headers wrap everything (added last = outermost).
    app.add_middleware(RequestContextMiddleware)
    # Added last, so it is outermost: every response, including CORS preflights and 413s,
    # gets the security headers (review finding R8).
    app.add_middleware(SecurityHeadersMiddleware)

    app.include_router(api_router, prefix=settings.api_prefix)

    @app.get(metrics.METRICS_PATH, include_in_schema=False)
    def prometheus_metrics(request: Request) -> Response:
        if not metrics.authorized(request.headers.get("authorization")):
            return JSONResponse(
                status_code=401, content=error_body("unauthorized", "Metrics need a valid token.")
            )
        body, content_type = metrics.exposition()
        return Response(content=body, media_type=content_type)

    @app.get("/", include_in_schema=False)
    def root() -> dict[str, str]:
        return {
            "message": f"{settings.app_name} API is running",
            "docs": f"{settings.api_prefix}/docs",
        }

    return app


app = create_app()
