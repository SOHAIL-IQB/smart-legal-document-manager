"""Phase 7 T3 (security headers, R8) and T4 (real client IPs behind a proxy, R4).

Header values follow the OWASP HTTP Headers Cheat Sheet
(https://cheatsheetseries.owasp.org/cheatsheets/HTTP_Headers_Cheat_Sheet.html). Proxy behavior is
uvicorn 0.54's ProxyHeadersMiddleware (read from the installed source; the online docs were
unreachable when this was written, see LOG.md).
"""

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.core.config import Settings, get_settings
from app.core.security import login_rate_limiter
from app.main import app

ALWAYS = {
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "referrer-policy": "strict-origin-when-cross-origin",
    "permissions-policy": "geolocation=(), camera=(), microphone=()",
    "x-xss-protection": "0",
    "cross-origin-opener-policy": "same-origin",
    "cross-origin-resource-policy": "same-site",
}


@pytest.mark.parametrize(
    "request_args",
    [
        ("GET", "/api/health"),
        ("GET", "/api/documents"),  # 401
        ("GET", "/api/nope"),  # 404
        ("POST", "/api/auth/login"),  # 422
    ],
)
def test_every_response_carries_the_security_headers(client, request_args):
    response = client.request(*request_args, json={} if request_args[0] == "POST" else None)
    for name, value in ALWAYS.items():
        assert response.headers.get(name) == value, name


def test_api_responses_get_a_locked_down_csp_and_no_store(client, alice):
    response = client.get("/api/documents", headers=alice.headers)
    assert (
        response.headers["content-security-policy"] == "default-src 'none'; frame-ancestors 'none'"
    )
    assert response.headers["cache-control"] == "no-store"


def test_docs_page_csp_allows_only_its_own_assets(client):
    csp = client.get("/api/docs").headers["content-security-policy"]
    assert "script-src 'self' https://cdn.jsdelivr.net" in csp
    assert "frame-ancestors 'none'" in csp
    assert "connect-src 'self'" in csp
    assert "*" not in csp


def test_hsts_only_in_production(client, monkeypatch):
    assert "strict-transport-security" not in client.get("/api/health").headers
    monkeypatch.setattr(get_settings(), "environment", "production")
    assert (
        client.get("/api/health").headers["strict-transport-security"]
        == "max-age=63072000; includeSubDomains"
    )


def test_cors_preflight_still_works_with_headers(client):
    response = client.options(
        "/api/documents",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"},
    )
    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"


# --- T4: client IPs behind a proxy -----------------------------------------------------------


def _login_as(client, ip):
    return client.post(
        "/api/auth/login",
        json={"email": "victim@example.com", "password": "wrong password"},
        headers={"X-Forwarded-For": ip},
    )


def _exhaust_limit(client, ip):
    for _ in range(get_settings().login_max_failures):
        _login_as(client, ip)


def test_trusted_proxy_gives_each_client_its_own_limit():
    # TestClient connects as host "testclient"; trust it like FORWARDED_ALLOW_IPS would.
    proxied = TestClient(ProxyHeadersMiddleware(app, trusted_hosts="testclient"))
    login_rate_limiter.reset()
    _exhaust_limit(proxied, "203.0.113.7")
    assert _login_as(proxied, "203.0.113.7").status_code == 429
    assert _login_as(proxied, "198.51.100.9").status_code == 401  # a different person


def test_forwarded_header_from_an_untrusted_peer_is_ignored():
    # The peer isn't in the trust list, so X-Forwarded-For can't be used to dodge the limit.
    direct = TestClient(ProxyHeadersMiddleware(app, trusted_hosts="10.0.0.1"))
    login_rate_limiter.reset()
    _exhaust_limit(direct, "203.0.113.7")
    assert _login_as(direct, "198.51.100.9").status_code == 429  # same real peer, still blocked


def test_production_refuses_to_trust_every_proxy():
    # With "*", uvicorn takes the left-most X-Forwarded-For entry, which any client can forge.
    with pytest.raises(ValidationError, match="FORWARDED_ALLOW_IPS"):
        Settings(environment="production", secret_key="s" * 48, forwarded_allow_ips="*")


def test_production_accepts_an_explicit_proxy_network():
    settings = Settings(
        environment="production", secret_key="s" * 48, forwarded_allow_ips="10.0.0.0/8"
    )
    assert settings.forwarded_allow_ips == "10.0.0.0/8"
