# Performance baseline and ledger

Budget (performance-optimization skill): API p95 ≤ 200 ms. Measure first; only a measured p95 over
budget justifies optimization work. Every attempt, kept or reverted, is logged below.

## Baseline — 2026-11-24 (Phase 7 T11)

- Setup: `docker compose` API container + PostgreSQL 16 on a MacBook (Docker Desktop).
- Command: `python -m scripts.bench --base http://localhost:8000 --documents 200 --requests 50`.
  It builds its own data: 200 contracts of ~3,000 words with 3 versions each, for a new user per run.
- Runs: 3, back to back. The database grows each run (end of run 3: 637 documents, 1,844 versions,
  50.4 MB of version text).

| Endpoint | p50 ms (runs 1 / 2 / 3) | p95 ms (runs 1 / 2 / 3) | Verdict |
|---|---|---|---|
| `GET /documents` (page of 20) | 5.5 / 6.5 / 7.8 | 9.4 / 7.9 / 9.1 | within budget |
| `GET /documents?q=indemnity` | 67.5 / 69.6 / 71.2 | 70.5 / 117.2 / 75.4 | within budget; **scaling risk, see below** |
| `GET /documents/{id}` | 3.8 / 3.7 / 3.8 | 5.5 / 5.9 / 5.1 | within budget |
| `GET /documents/{id}/versions` | 3.3 / 3.2 / 3.7 | 4.0 / 4.2 / 4.3 | within budget |
| `GET /documents/{id}/compare?v1=1&v2=3` | 6.0 / 5.8 / 5.9 | 7.7 / 9.0 / 6.6 | within budget |
| `POST /documents/upload` (5-page PDF, n=10) | 226.5 / 216.1 / 216.5 | 283.1 / 251.0 / 227.0 | **over budget, accepted trade-off** |

## Findings

### 1. Search time grows with every document in the system, not with the user's own documents

`EXPLAIN (ANALYZE, BUFFERS)` of the search query (bench user 9, `q=indemnity`, run 3):

- The planner hash-joins **all** 637 documents with their latest version and evaluates `ILIKE` on
  that content (`Hash Right Join … actual rows=442`, 74 ms of the 77 ms total).
- Only then does it check membership (`Index Scan using document_members_pkey … loops=442`).
- So the cost is proportional to the whole corpus across all users. Today it is ~75 ms, within
  budget. At ~10× the data it would likely exceed it.

Not optimized (p95 is within budget). Candidate fixes, to be measured when the budget is at risk:
1. Restrict to the caller's documents first (membership as a semi-join/CTE the planner can't push
   below the text filter).
2. A `pg_trgm` GIN index on the latest version's content for `ILIKE '%term%'`; it needs the
   `pg_trgm` extension and adds write cost on every version.

### 2. Upload p95 is over budget because of the parse worker's start-up

- Each PDF/DOCX parse starts a fresh, confined Python process (Phase 7 T6, review finding R5).
- Measured start-up plus a 1-page parse in the Linux container: 0.215 s (LOG.md entry 014).
- The upload p95 of 227–283 ms is almost entirely that cost.
- Accepted: the isolation (time, CPU, memory and write limits, no secrets, killable) is worth
  ~0.2 s on an infrequent, user-initiated action.
- If it matters later: a pre-forked, recycled worker pool. That is more complex in
  security-critical code, so it should only be done with a measured need.

## Ledger

| Date | Idea | Baseline → result | Verdict | Why |
|---|---|---|---|---|
| — | none yet | — | — | baseline only |
