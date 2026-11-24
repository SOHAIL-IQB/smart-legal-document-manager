"""Latency baseline for the main read and write paths (Phase 7 T11, performance-optimization).

    python -m scripts.bench --base http://localhost:8000 [--documents 200] [--requests 50]

Builds its own dataset through the API (one bench user, N contracts of ~3,000 words with three
versions each), then times each endpoint sequentially and prints p50 / p95 / max in milliseconds.
Measure, don't optimize: numbers go to PERF.md, and only a p95 over budget (200 ms) justifies work.
"""

import argparse
import random
import statistics
import time
import uuid

import httpx

from tests.files import make_pdf

WORDS = [
    "agreement",
    "party",
    "parties",
    "term",
    "clause",
    "notice",
    "obligation",
    "confidential",
    "information",
    "payment",
    "invoice",
    "liability",
    "indemnity",
    "warranty",
    "termination",
    "breach",
    "remedy",
    "jurisdiction",
    "governing",
    "law",
    "assignment",
    "amendment",
    "waiver",
    "severability",
    "counterparts",
    "force",
    "majeure",
    "dispute",
    "arbitration",
]


def contract_text(seed: int, words: int = 3000) -> str:
    rng = random.Random(seed)  # noqa: S311  [W5]
    lines = []
    for clause in range(1, words // 60 + 1):
        lines.append(f"{clause}. " + " ".join(rng.choice(WORDS) for _ in range(60)) + ".")
    return "\n\n".join(lines)


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(fraction * (len(ordered) - 1)))]


def timed(client: httpx.Client, method: str, url: str, **kwargs) -> float:
    started = time.perf_counter()
    response = client.request(method, url, **kwargs)
    elapsed = (time.perf_counter() - started) * 1000
    response.raise_for_status()
    return elapsed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", default="http://localhost:8000")
    parser.add_argument("--documents", type=int, default=200)
    parser.add_argument("--requests", type=int, default=50)
    args = parser.parse_args()

    client = httpx.Client(base_url=f"{args.base}/api", timeout=60)
    email = f"bench-{uuid.uuid4().hex[:8]}@bench.example"
    token = client.post(
        "/auth/register", json={"name": "Bench", "email": email, "password": "bench password 1"}
    ).json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"

    print(f"Building {args.documents} documents x 3 versions ...", flush=True)
    ids = []
    for n in range(args.documents):
        text = contract_text(n)
        doc = client.post("/documents", json={"title": f"Contract {n:04d}", "content": text})
        document_id = doc.raise_for_status().json()["document_id"]
        for edit in (1, 2):
            changed = text.replace(f"{edit}. ", f"{edit}. amended {edit} ", 1)
            client.post(f"/documents/{document_id}/versions", json={"content": changed})
            text = changed
        ids.append(document_id)

    rng = random.Random(7)  # noqa: S311  [W5]
    pdf = make_pdf(*[contract_text(i, 400) for i in range(5)])
    cases = {
        "GET /documents (page of 20)": lambda: ("GET", "/documents", {}),
        "GET /documents?q=indemnity": lambda: ("GET", "/documents", {"params": {"q": "indemnity"}}),
        "GET /documents/{id}": lambda: ("GET", f"/documents/{rng.choice(ids)}", {}),
        "GET /documents/{id}/versions": lambda: (
            "GET",
            f"/documents/{rng.choice(ids)}/versions",
            {},
        ),
        "GET /documents/{id}/compare?v1=1&v2=3": lambda: (
            "GET",
            f"/documents/{rng.choice(ids)}/compare",
            {"params": {"v1": 1, "v2": 3}},
        ),
        "POST /documents/upload (5-page PDF)": lambda: (
            "POST",
            "/documents/upload",
            {"files": {"file": ("bench.pdf", pdf, "application/pdf")}},
        ),
    }

    print("\n| Endpoint | n | p50 ms | p95 ms | max ms |\n|---|---|---|---|---|")
    for name, make in cases.items():
        count = args.requests if "upload" not in name else max(10, args.requests // 5)
        timed(client, *make()[:2], **make()[2])  # warm-up, not counted
        samples = [timed(client, m, u, **kw) for m, u, kw in (make() for _ in range(count))]
        print(
            f"| {name} | {count} | {statistics.median(samples):.1f} | "
            f"{percentile(samples, 0.95):.1f} | {max(samples):.1f} |"
        )


if __name__ == "__main__":
    main()
