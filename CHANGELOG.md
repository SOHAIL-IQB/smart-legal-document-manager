# Changelog

All notable changes to this project. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). `B1`–`B16` are the defects found in the
original code (`PLAN.md` §4, `LOG.md` 002); `R1`–`R8` are findings of the backend review
(`LOG.md` 009).

## [Unreleased]

The rebuild of the original submission (2026-11-22 to 2026-11-24). The API reports version
`0.2.0`. Not yet tagged.

### Breaking

- Every route moved under `/api`; interactive docs are at `/api/docs`.
- Requests no longer carry a `user_id`: the caller comes from a signed session (B1).
- `GET /documents` returns `{items, total, limit, offset}` instead of a bare list (B6).
- Errors have one shape, `{"error": {"code", "message", "details", "request_id"}}`.
- `GET /users`, which listed every account, was removed.

### Added

- **Accounts and sharing:**
  - registration, sign-in, sign-out and `GET /auth/me`, with a JWT in an `httpOnly` cookie
    for browsers or a bearer token for API clients;
  - `GET /auth/session`, which answers 200 with `{"user": null}` when signed out, so a browser's
    first check on each visit isn't logged as a failed request;
  - per-document roles owner, editor and viewer, with endpoints to share, change roles and
    remove members. A document always keeps an owner.
- **Version history:**
  - fetch one version, and restore an old version as a new one;
  - every version has a SHA-256 hash, word count, optional change note and source
    (`manual`, `restore`, `upload`).
- **Comparison:** a word-level, side-by-side diff with per-line segments, a whitespace-only flag,
  add/remove/change stats and optional context collapsing (B10).
- **Search and listing:** search over titles and the latest text, a role filter, sorting and
  pagination; list items include the owner's name, live version count and word count (B6).
- **File upload:**
  - new documents and new versions from PDF, DOCX and TXT;
  - the type is detected from the file's bytes, and only the extracted text is stored, with the
    original file name.
- **Activity and notifications:**
  - an append-only activity log per document;
  - an in-app notification inbox (unread count, mark read, mark all read), written in the same
    transaction as the action (B9).
- **Your data:** `GET /auth/me/export` downloads your data as JSON. `DELETE /auth/me` deletes
  (anonymizes) your account after a password check, and is refused while you are the last owner
  of a shared document.
- **Operations:**
  - `/api/health/live` and `/api/health/ready` (checks the database; B15);
  - Prometheus metrics at `/metrics`, with an optional token;
  - an `X-Request-ID` on every response and in every error body;
  - one JSON log line per request, plus named events.
- **Demo and measurement:** `python -m scripts.seed` loads demo users and contracts;
  `scripts/bench.py` and `PERF.md` record a latency baseline.
- **Project records:**
  - `PLAN.md` and `LOG.md`;
  - ADR 0001 (authentication and authorization) and ADR 0002 (API contract and retry safety);
  - the Phase 7 spec;
  - `AGENTS.md`, and `CONSTRAINTS.md` with a floor guard that blocks weakened tests or silenced
    checks.
- **Frontend (Inkstep, in progress):** the landing page. Its sheet shows the sample agreement's real
  history; the margin column folds through the versions with the keyboard, a drag or Replay; and
  the turned-back corner opens a private demo workspace.
- **CI:**
  - lint and a coverage floor (97.5%);
  - a PostgreSQL job that round-trips the migrations and runs the full suite;
  - a dependency audit (pip-audit), a secret scan (gitleaks) and the floor guard;
  - Dependabot (B16).

### Changed

- Code is split into `api/routes` (thin), `services` (rules and transactions), `core`, `db`,
  `schemas` and `utils`.
- Deleting a version hides it (`deleted_at`, `deleted_by`) instead of removing it. Fetching,
  comparing or restoring it returns `410`.
- Concurrent saves to one document queue on a row lock instead of colliding.
- Deleting a document cascades in the database instead of loading every version first (R2).
- Titles are trimmed, and content is stored exactly as sent.
- Timestamps come from the application clock and are always returned in UTC with a timezone.
- Dependencies upgraded for Python 3.12+; test and lint tools moved to `requirements-dev.txt`
  (B11).
- The Docker image uses Python 3.12 and runs as a non-root user without a `Server` header.
- The database URL is read only from settings, defaulting to the compose port 5434 (B12).

### Fixed

- Version numbers were reused after deleting the latest version (B2).
- Deleting the only version left a document that could never be edited again (B3); the last live
  version can no longer be deleted.
- Concurrent version saves raised an unhandled 500 (B4).
- Blank titles, names and content were accepted (B5).
- `ValueError` was treated as "not found" everywhere (B7).
- Saving a version loaded every version's full content (B8).
- A duplicate-email race on sign-up returned 500 instead of 409 (B14).
- The comparison reported hundreds of changed lines for one edit in documents with repeated
  headings (`difflib` auto-junk is off).
- `/health` answered "ok" with the database down (B15).

### Security

- **Passwords and sessions:**
  - passwords are hashed with Argon2id, and failed sign-ins are rate limited per IP and email;
  - tokens carry and require an issuer and audience;
  - production refuses a weak `SECRET_KEY`;
  - cookie-authenticated writes must send `X-Requested-With` (CSRF guard).
- **Access:** non-members get `404`, so document ids can't be probed.
- **CORS:** `*` origins are refused, because the API allows credentials (B13).
- **Request bodies:** capped while they stream in, before anything parses them. An unauthenticated
  300 MB body had pushed the server from 149 MB to 1,094 MB (R1).
- **PDF/DOCX parsing** runs in a confined worker process (R5):
  - a scrubbed environment, so no secrets;
  - 20 s CPU and wall-clock limits, and 1 GiB of memory on Linux;
  - no file writes and no new processes;
  - at most 4 at once.

  Other upload protections: encrypted, damaged, scanned and oversized PDFs are refused, and DOCX
  archives are size-checked before they are inflated.
- **Security headers:** `nosniff`, frame denial, referrer and permissions policies, COOP/CORP and a
  strict CSP for the API. HSTS is sent in production (R8).
- **Forwarded headers** are trusted only from `FORWARDED_ALLOW_IPS`; production refuses `*`, which
  would let clients forge their IP and dodge the sign-in limit (R4).
- **Logs** carry an allowlist of fields: no tokens, passwords, emails or bodies.
- **Account deletion** asks for the password again and has its own rate limit. Deleted accounts'
  tokens stop working.

## [0.1.0] — 2026-03-17

The original submission:
- a FastAPI backend with documents, versions, a unified-diff comparison and log-only
  notifications;
- Docker, a CI job that ran pytest on SQLite, a README and a user guide.
