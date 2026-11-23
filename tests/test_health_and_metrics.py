"""Phase 7 T8: liveness and readiness (audit item B15) and RED metrics.

On-call question 1: is the API up, and can it reach the database? -> /health/live, /health/ready.
On-call question 3: which endpoints are slow or failing, and since when? -> /metrics.
"""

import re

import pytest
from sqlalchemy.exc import OperationalError

from app.core import metrics


def test_liveness_never_touches_the_database(client, monkeypatch):
    def broken(*_args, **_kwargs):
        raise AssertionError("liveness must not query the database")

    monkeypatch.setattr("app.api.routes.health.check_database", broken)
    response = client.get("/api/health/live")
    assert (response.status_code, response.json()) == (200, {"status": "ok"})


def test_readiness_is_ok_when_the_database_answers(client):
    response = client.get("/api/health/ready")
    assert (response.status_code, response.json()) == (200, {"status": "ok", "database": "ok"})


@pytest.mark.parametrize("path", ["/api/health/ready", "/api/health"])
def test_readiness_is_503_when_the_database_is_down(client, monkeypatch, path):
    def down():
        raise OperationalError("SELECT 1", {}, Exception("connection refused"))

    monkeypatch.setattr("app.api.routes.health.check_database", down)
    response = client.get(path)
    assert response.status_code == 503
    body = response.json()
    assert body["error"]["code"] == "unavailable"
    assert "connection refused" not in response.text  # no internals in the reply


def test_health_alias_matches_readiness(client):
    assert client.get("/api/health").json() == client.get("/api/health/ready").json()


# --- metrics -------------------------------------------------------------------------------------


def _sample(text, name, **labels):
    wanted = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
    for line in text.splitlines():
        match = re.match(rf"^{re.escape(name)}\{{(.*)\}} (\S+)$", line)
        if match and ",".join(sorted(match.group(1).split(","))) == wanted:
            return float(match.group(2))
    return 0.0


def test_requests_are_counted_by_route_template_and_status_class(client, alice, make_document):
    document_id = make_document(alice)
    labels = {"method": "GET", "route": "/api/documents/{document_id}", "status_class": "2xx"}
    before = _sample(client.get("/metrics").text, "http_requests_total", **labels)
    client.get(f"/api/documents/{document_id}", headers=alice.headers)
    client.get(f"/api/documents/{document_id}", headers=alice.headers)
    after = _sample(client.get("/metrics").text, "http_requests_total", **labels)
    assert after - before == 2


def test_latency_is_a_histogram_with_buckets(client):
    client.get("/api/health/live")
    text = client.get("/metrics").text
    assert (
        'http_request_duration_seconds_bucket{le="0.1",method="GET",route="/api/health/live"}'
        in (text)
    )
    assert "http_request_duration_seconds_count" in text


def test_labels_never_contain_raw_paths_or_ids(client, alice, make_document):
    document_id = make_document(alice)
    client.get(f"/api/documents/{document_id}", headers=alice.headers)
    client.get("/api/does/not/exist/98765")
    text = client.get("/metrics").text
    routes = set(re.findall(r'route="([^"]*)"', text))
    assert all(not re.search(r"/\d+", route) for route in routes), routes
    assert "unmatched" in routes
    assert not re.search(r'status_class="\d{3}"', text)  # "5xx", never "503"


def test_metrics_can_require_a_token(client, monkeypatch):
    monkeypatch.setattr(metrics, "_token", lambda: "metrics-secret")
    assert client.get("/metrics").status_code == 401
    assert client.get("/metrics", headers={"Authorization": "Bearer wrong"}).status_code == 401
    allowed = client.get("/metrics", headers={"Authorization": "Bearer metrics-secret"})
    assert allowed.status_code == 200
    assert "http_requests_total" in allowed.text


def test_metrics_scrapes_are_not_counted(client):
    for _ in range(3):
        client.get("/metrics")
    assert 'route="/metrics"' not in client.get("/metrics").text


def test_made_up_http_methods_cannot_create_new_label_values(client):
    for method in ("FOOBAR", "XYZZY", "PROPFIND"):
        client.request(method, "/api/health/live")
    text = client.get("/metrics").text
    methods = set(re.findall(r'method="([^"]*)"', text))
    assert {"FOOBAR", "XYZZY", "PROPFIND"}.isdisjoint(methods)
    assert "other" in methods
