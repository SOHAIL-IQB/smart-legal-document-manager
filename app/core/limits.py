"""Cap request body size while it streams in (review finding R1, LOG 009).

FastAPI reads and parses the whole body before dependencies such as authentication run, so
without a cap anyone could make the server buffer arbitrarily large bodies.

FastAPI's built-in `max_body_size` isn't used: its middleware sits outside every user
middleware and answers a declared oversized body with plain text, which would break the API's
`{"error": {...}}` format. This middleware does the same job and keeps the format:
- a declared `Content-Length` over the limit is refused before anything is read;
- bytes are counted as they arrive (covers `Transfer-Encoding: chunked`). Past the limit it
  raises Starlette's `HTTPException(413)`, which FastAPI re-raises unchanged while parsing the
  body, so the normal error handler formats the reply.
"""

import json

from starlette.exceptions import HTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import get_settings
from app.core.errors import error_body

# Room for multipart boundaries and form fields on top of the file itself.
MULTIPART_OVERHEAD = 64 * 1024
_BODYLESS_METHODS = {"GET", "HEAD", "OPTIONS"}


def body_limit_for(path: str) -> int:
    settings = get_settings()
    if path.endswith("/upload"):
        return settings.max_upload_bytes + MULTIPART_OVERHEAD
    return settings.max_json_bytes


def _too_large_message(limit: int) -> str:
    return f"The request body is larger than {limit / (1024 * 1024):.3g} MB."


class BodySizeLimitMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] in _BODYLESS_METHODS:
            await self.app(scope, receive, send)
            return

        limit = body_limit_for(scope["path"])
        declared = dict(scope["headers"]).get(b"content-length", b"")
        if declared.isdigit() and int(declared) > limit:
            body = json.dumps(error_body("payload_too_large", _too_large_message(limit))).encode()
            await send(
                {
                    "type": "http.response.start",
                    "status": 413,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"content-length", str(len(body)).encode()),
                        (b"connection", b"close"),
                    ],
                }
            )
            await send({"type": "http.response.body", "body": body})
            return

        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    raise HTTPException(status_code=413, detail=_too_large_message(limit))
            return message

        await self.app(scope, limited_receive, send)
