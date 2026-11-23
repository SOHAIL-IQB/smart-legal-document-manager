"""Structured JSON logs with a request ID on every line (Phase 7 T7).

Every line is one JSON object with a stable `event` name and machine-readable fields. Domain
code calls `log_event("login_failed", reason=...)`; the request ID is attached automatically.

Rule: never pass secrets, tokens, passwords, email addresses or request/response bodies as
fields. Fields are allowlisted by the call sites, not copied from requests.
"""

import json
import logging
import sys
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.context import request_id_var
from app.core.errors import error_body
from app.core.metrics import observe

logger = logging.getLogger("sldm")


def log_event(event: str, level: int = logging.INFO, exc_info: bool = False, **fields: Any) -> None:
    request_id = request_id_var.get()
    if request_id is not None:
        fields = {"request_id": request_id, **fields}
    logger.log(level, event, extra={"event": event, "fields": fields}, exc_info=exc_info)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "level": record.levelname.lower(),
            "logger": record.name,
            "event": getattr(record, "event", None) or record.getMessage(),
            **getattr(record, "fields", {}),
        }
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)


def _incoming_request_id(scope: Scope) -> str:
    for name, value in scope["headers"]:
        if name == b"x-request-id":
            try:
                return str(uuid.UUID(value.decode("latin1")))  # only well-formed UUIDs are kept
            except ValueError:
                break
    return str(uuid.uuid4())


def route_template(scope: Scope) -> str:
    """The matched route as a template ("/api/documents/{document_id}"), never the raw path.

    FastAPI 0.165 keeps included routers nested, so the matched route only knows its path
    relative to its own router. The prefix is whatever precedes that route's concrete path in
    the request path.
    """
    route = scope.get("route")
    template = getattr(route, "path", None)
    if not template:
        return "unmatched"
    try:
        concrete = template.format(**scope.get("path_params", {}))
    except (KeyError, IndexError, ValueError):
        return template
    path = scope.get("path", "")
    prefix = path[: -len(concrete)] if concrete and path.endswith(concrete) else ""
    return prefix + template


class RequestContextMiddleware:
    """Assigns the request ID, logs one access line per request, and answers unhandled errors.

    It handles unhandled errors itself (instead of Starlette's outermost error middleware) so the
    500 body and the `unhandled_error` log line carry the same request ID.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = _incoming_request_id(scope)
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        status = 500
        response_started = False

        async def send_with_request_id(message: Message) -> None:
            nonlocal status, response_started
            if message["type"] == "http.response.start":
                response_started = True
                status = message["status"]
                message["headers"] = [
                    *message.get("headers", []),
                    (b"x-request-id", request_id.encode()),
                ]
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        except Exception:
            log_event("unhandled_error", logging.ERROR, exc_info=True)
            if response_started:
                raise
            body = json.dumps(
                error_body("internal_error", "An unexpected error occurred.")
            ).encode()
            await send_with_request_id(
                {
                    "type": "http.response.start",
                    "status": 500,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"content-length", str(len(body)).encode()),
                    ],
                }
            )
            await send({"type": "http.response.body", "body": body})
        finally:
            elapsed = time.perf_counter() - started
            route = route_template(scope)
            observe(scope["method"], route, status, elapsed)
            fields: dict[str, Any] = {
                "method": scope["method"],
                "route": route,
                "status": status,
                "duration_ms": round(elapsed * 1000, 2),
            }
            user_id = scope.get("state", {}).get("user_id")
            if user_id is not None:
                fields["user_id"] = user_id
            log_event("http_request", **fields)
            request_id_var.reset(token)
