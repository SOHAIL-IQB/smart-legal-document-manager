"""Security headers on every response (review finding R8, Phase 7 T3).

Values follow the OWASP HTTP Headers Cheat Sheet:
https://cheatsheetseries.owasp.org/cheatsheets/HTTP_Headers_Cheat_Sheet.html

- The sheet gives no CSP for JSON APIs. `default-src 'none'; frame-ancestors 'none'` is this
  project's choice: an API response should load nothing and never be framed.
- The Swagger UI page (`/api/docs`) is the one HTML page. FastAPI renders it with assets from
  cdn.jsdelivr.net, a favicon from fastapi.tiangolo.com and an inline start-up script
  (fastapi/openapi/docs.py), so its CSP allows exactly those. `'unsafe-inline'` is scoped to
  that page only.
- `Cache-Control: no-store` on API responses: they carry private legal documents.
- HSTS only in production, where the API is served over HTTPS. No `preload`: that needs the domain
  submitted to the browser preload list.
"""

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import get_settings

_ALWAYS = [
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"strict-origin-when-cross-origin"),
    (b"permissions-policy", b"geolocation=(), camera=(), microphone=()"),
    (b"x-xss-protection", b"0"),
    (b"cross-origin-opener-policy", b"same-origin"),
    (b"cross-origin-resource-policy", b"same-site"),
]
_API_CSP = b"default-src 'none'; frame-ancestors 'none'"
_DOCS_CSP = (
    b"default-src 'none'; "
    b"script-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; "
    b"style-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; "
    b"img-src 'self' data: https://fastapi.tiangolo.com; "
    b"connect-src 'self'; "
    b"frame-ancestors 'none'"
)
_HSTS = (b"strict-transport-security", b"max-age=63072000; includeSubDomains")


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        settings = get_settings()
        is_docs = scope["path"] == f"{settings.api_prefix}/docs"

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                present = {name.lower() for name, _ in headers}
                extra = [*_ALWAYS, (b"content-security-policy", _DOCS_CSP if is_docs else _API_CSP)]
                if not is_docs and b"cache-control" not in present:
                    extra.append((b"cache-control", b"no-store"))
                if settings.environment == "production":
                    extra.append(_HSTS)
                headers.extend(h for h in extra if h[0] not in present)
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_headers)
