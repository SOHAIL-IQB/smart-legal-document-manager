"""RED metrics (rate, errors, duration) in Prometheus format (Phase 7 T8).

Docs: https://prometheus.github.io/client_python/ (an isolated CollectorRegistry; Counter and
Histogram with label names). Labels come only from small fixed sets, per the observability skill:
HTTP method (unknown methods become "other"), route *template* and status class ("5xx").

`/metrics` is open by default for local scraping. Set METRICS_TOKEN to require
`Authorization: Bearer <token>`, or keep the path private at the proxy.
"""

import hmac

from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, Histogram
from prometheus_client import generate_latest as _generate_latest

from app.core.config import get_settings

REGISTRY = CollectorRegistry(auto_describe=True)

REQUESTS = Counter(
    "http_requests",  # exposed as http_requests_total
    "HTTP requests handled, by method, route template and status class.",
    ["method", "route", "status_class"],
    registry=REGISTRY,
)
LATENCY = Histogram(
    "http_request_duration_seconds",
    "Time to handle a request, by method and route template.",
    ["method", "route"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 25.0),
    registry=REGISTRY,
)

_KNOWN_METHODS = {"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"}
METRICS_PATH = "/metrics"


def observe(method: str, route: str, status: int, seconds: float) -> None:
    if route == METRICS_PATH:
        return  # scrapes would otherwise dominate the numbers
    method = method if method in _KNOWN_METHODS else "other"
    REQUESTS.labels(method=method, route=route, status_class=f"{status // 100}xx").inc()
    LATENCY.labels(method=method, route=route).observe(seconds)


def _token() -> str | None:
    return get_settings().metrics_token


def authorized(authorization_header: str | None) -> bool:
    token = _token()
    if not token:
        return True
    expected = f"Bearer {token}"
    return hmac.compare_digest((authorization_header or "").encode(), expected.encode())


def exposition() -> tuple[bytes, str]:
    return _generate_latest(REGISTRY), CONTENT_TYPE_LATEST
