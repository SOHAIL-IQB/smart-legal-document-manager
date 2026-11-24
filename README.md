# Smart Legal Document Manager

A multi-user document version-control API for legal teams. Every edit is kept as a version,
any two versions can be compared word by word, and each document is shared with owners, editors
and viewers. Members are notified of meaningful changes, and every action is recorded in an
append-only activity log. Contracts can be uploaded as PDF, DOCX or TXT.

Built with FastAPI, SQLAlchemy 2, Alembic and PostgreSQL 16 on Python 3.12. A React frontend is
planned (`PLAN.md`, Phases 8–10).

## Features

- **Version history that can't be rewritten:** numbers are never reused, a deleted version stays
  in the audit trail, restoring creates a new version, and concurrent saves queue instead of
  colliding.
- **Word-level comparison** for a side-by-side view, with change stats and whitespace-only
  detection.
- **Sharing with roles** (owner, editor, viewer). Non-members can't even see that a document exists.
- **Search, filters and pagination** over titles and the latest text.
- **File upload** (PDF, DOCX, TXT). Parsing runs in a confined worker process.
- **Notifications and an activity log**, written in the same transaction as the action.
- **Your data:** export it as JSON, or delete your account.
- **Operations:** liveness and readiness checks, Prometheus metrics, JSON logs with request IDs,
  and security headers.

## Quick Start

Requires Docker.

```bash
docker compose up --build -d
docker compose exec api python -m scripts.seed
```

- API: <http://localhost:8000/api>.
- Interactive docs: <http://localhost:8000/api/docs>.
- The seed creates three demo accounts:
  - emails `asha@demo.example`, `ben@demo.example` and `chloe@demo.example`;
  - password `demo password 2026` for all three.
- A curl walkthrough of every feature: [`USER_GUIDE.md`](USER_GUIDE.md).
- Stop with `docker compose down`; add `-v` to also delete the database volume.

## Architecture

```text
client (browser / curl)
   │  HTTP, JSON under /api
   ▼
app/main.py         middleware, outermost first: security headers → request ID + access log
                    + metrics → CORS → body-size limit
app/api/routes/     thin routes: parse input, resolve access (app/api/deps.py), call a service
app/services/       business rules; one transaction per action, including its activity
                    event and notifications
app/db/             SQLAlchemy models and session ──▶ PostgreSQL 16 (Alembic: migrations/)
app/core/           config, errors (one error shape), security, limits, logging, metrics
app/utils/          diff engine; text extraction ──▶ parse_worker.py in its own process
```

Decisions are recorded as ADRs:
- [0001 — Authentication and authorization](docs/adr/0001-authentication-and-authorization.md):
  JWT in an `httpOnly` cookie or bearer token, roles, CSRF guard, threat model.
- [0002 — API contract](docs/adr/0002-api-contract.md): naming, pagination, error shape, status
  codes, and which writes are safe to retry.

Other records:
- `PLAN.md`: the plan.
- `LOG.md`: what was done, with evidence.
- `CHANGELOG.md`: what changed.
- `PERF.md`: performance baseline.
- `CONSTRAINTS.md`: the enforced quality bar.
- `docs/specs/`: per-phase specs.
- `AGENTS.md`: how to work on this repository.

```text
app/
  api/          routes/, deps.py (auth and access), router.py
  core/         config, errors, headers, limits, logging, metrics, security
  db/           models.py, session.py
  schemas/      pydantic request and response models
  services/     account, activity, documents, members, notifications, users, versions
  utils/        diff, extract, parse_worker
migrations/     Alembic versions (each additive, with a tested downgrade)
scripts/        seed.py, bench.py, floor_guard.py
tests/          pytest (SQLite by default, Postgres with TEST_DATABASE_URL)
docs/           adr/, specs/
```

## Data Model

| Table | Purpose |
|---|---|
| `users` | `id`, `name`, `email` (unique, lowercase), `password_hash` (Argon2id), `created_at`, `deleted_at` (set when the account is deleted and anonymized) |
| `documents` | `id`, `title`, `created_by`, `created_at`, `updated_at` |
| `document_members` | `document_id`, `user_id`, `role` (`owner` / `editor` / `viewer`), `added_at` |
| `document_versions` | `id`, `document_id`, `version_number`, `content`, `content_hash` (SHA-256), `word_count`, `change_note`, `source` (`manual` / `restore` / `upload`), `restored_from`, `edited_by`, `created_at`, `deleted_at`, `deleted_by` |
| `activity_events` | `id`, `document_id`, `actor_id`, `action`, `details` (JSON), `created_at`; append-only |
| `notifications` | `id`, `user_id`, `document_id` (set to NULL when the document is deleted), `actor_id`, `kind`, `message`, `version_number`, `read_at`, `created_at` |

Each version stores a full content snapshot, so earlier content is never overwritten.
Versions are never hard-deleted: "deleting" one hides it but keeps it for the audit trail, its
number is never reused, and a document always keeps at least one live version. Saves to the same
document are serialized with a row lock, so concurrent edits get distinct version numbers.

## Authentication and Permissions

Sign up or log in to get a session. Browsers receive an `httpOnly` cookie; API clients can use
the returned token as `Authorization: Bearer <token>`. Every document has members with a role:

| Action | viewer | editor | owner |
|---|:-:|:-:|:-:|
| Read document, versions, comparisons, members | ✓ | ✓ | ✓ |
| Add or restore a version, rename | | ✓ | ✓ |
| Delete a version or the document, manage members | | | ✓ |

**Your data.** `GET /auth/me/export` downloads your profile, memberships, the versions you wrote,
your activity and your notifications, for the documents you can still access.
`DELETE /auth/me` deletes your account after asking for your password again:
- Documents only you belong to are deleted, and you leave the others.
- It is refused (`409`, with the list) while you are the last owner of a document other people
  still use.
- The account is anonymized rather than removed, because versions and the append-only activity
  log refer to it: it shows as "Deleted user", and its sessions stop working.
- Names already written into past activity details or other people's notifications stay as they
  were.

Users who aren't members get `404`, so document ids can't be probed. Design and threat model:
[`docs/adr/0001-authentication-and-authorization.md`](docs/adr/0001-authentication-and-authorization.md).

## API Endpoints

All endpoints are under `/api`. Interactive docs: `http://localhost:8000/api/docs`.

| Method | Path | Who |
|---|---|---|
| `POST` | `/auth/register`, `/auth/login`, `/auth/logout` | anyone |
| `GET` | `/auth/me` | signed in |
| `GET` | `/auth/me/export` (your data as a JSON download) | signed in |
| `DELETE` | `/auth/me` (body: `{"password": "..."}`) | signed in |
| `GET` / `POST` | `/documents` (`?q=&role=&sort=&order=&limit=&offset=`) | signed in (lists only your documents) |
| `GET` | `/documents/{id}` | viewer+ |
| `PATCH` | `/documents/{id}/title` | editor+ |
| `DELETE` | `/documents/{id}?confirm=true` | owner |
| `GET` / `POST` | `/documents/{id}/versions` (`?include_deleted=true`) | viewer+ / editor+ |
| `GET` | `/documents/{id}/versions/{n}` (full content) | viewer+ |
| `POST` | `/documents/{id}/versions/{n}/restore` | editor+ |
| `DELETE` | `/documents/{id}/versions/{n}` (soft delete) | owner |
| `GET` | `/documents/{id}/compare?v1=&v2=&context=` | viewer+ |
| `POST` | `/documents/upload` (multipart: `file`, `title`) | signed in |
| `POST` | `/documents/{id}/versions/upload` (multipart: `file`, `change_note`) | editor+ |
| `GET` / `POST` | `/documents/{id}/members` | viewer+ / owner |
| `PATCH` / `DELETE` | `/documents/{id}/members/{user_id}` | owner (any member may remove themselves) |
| `GET` | `/documents/{id}/activity` | viewer+ |
| `GET` | `/notifications` (`?unread_only=&limit=&offset=`), `/notifications/unread-count` | signed in |
| `POST` | `/notifications/{id}/read`, `/notifications/read-all` | signed in (own notifications only) |
| `GET` | `/health/live` (process up), `/health/ready` and `/health` (database reachable) | anyone |

Errors always have the shape `{"error": {"code": "...", "message": "...", "details": ..., "request_id": "..."}}`;
`request_id` matches the `X-Request-ID` response header and the server logs. Naming, pagination,
status codes and which writes are safe to retry: [ADR 0002](docs/adr/0002-api-contract.md).

## Comparison Logic

`GET /documents/{id}/compare` aligns the two versions line by line, then compares each changed
line word by word:
1. Lines that occur exactly once in each version anchor the alignment, the idea behind
   patience diff. Real contracts are mostly unique paragraphs, so a 2 MB document with
   scattered edits compares in a few hundredths of a second.
2. The gaps between anchors are matched exactly with Python's `difflib`, with auto-junk off, so
   repeated headings and signature lines still align.

Matching has a fixed budget per request. A version made to be slow to compare (many repeated
lines with dense edits) can't tie up the server: once the budget is spent, the remaining region is
shown as one replaced block and the response says `"approximate": true`.

The response contains:

- `rows`: side-by-side rows of type `equal`, `insert`, `delete`, `replace` or `skip`, with line
  numbers for each side. `replace` rows carry `old_segments` / `new_segments`
  (`{"op": "equal" | "delete" | "insert", "text": ...}`) that rebuild each line exactly, and a
  `whitespace_only` flag.
- `stats`: lines added / removed / changed and words added / removed.
- `context=N` keeps N unchanged lines around each change and collapses the rest into `skip` rows.
- `has_meaningful_changes`, `approximate`, plus `before`, `after` and a unified diff in `changes`.

## Searching and Listing

`GET /documents` returns `{items, total, limit, offset}` for documents you belong to. `q` searches
titles and the latest live version's text (case-insensitive; `%` and `_` match literally).
Filter with `role`, sort by `updated_at` (default), `created_at` or `title`, and page with
`limit` (1–100, default 20) and `offset`. Each item includes the owner's name, your role, the
latest version, the number of live versions and the latest word count.

## File Upload

Documents and new versions can be created from **PDF, DOCX or TXT** files; only the extracted text
is stored (as a version with `source: "upload"` and the original `source_filename`).

- The type is detected from the file's bytes and must match the extension; the browser's
  Content-Type is ignored.
- Limit: 10 MB (`MAX_UPLOAD_BYTES`); every other request body: 9 MB (`MAX_JSON_BYTES`, enough for
  the 2,000,000-character content limit). Bodies are counted while they stream in, with or without a
  `Content-Length`, and refused with `413` before anything parses them, even for signed-out clients.
- Refused with a clear `422`: password-protected or damaged PDFs, PDFs with no selectable text
  (scans; OCR isn't supported), PDFs over 500 pages, non-UTF-8 text, DOCX files over 50 MB
  uncompressed (zip bombs), and files with no text.
- DOCX paragraphs and tables are extracted in document order (table cells joined with ` | `).
  python-docx parses XML with entity resolution off (no XXE).
- PDF and DOCX files are parsed in a separate, short-lived worker process. It gets no secrets
  (a scrubbed environment), runs from `/`, can't write files or start processes, and is stopped
  after 20 s of wall time or 20 s of CPU, with a 1 GiB memory limit on Linux. A file that takes
  too long is a `422`. At most 4 files are parsed at once; when all 4 slots stay busy for 5 s, the
  upload gets `503 busy` and can be retried. Size the container for 4 workers (about 4 GiB plus
  the API) or lower `PARSE_MAX_CONCURRENT` in `app/utils/extract.py`.

## Notifications and Activity Log

Both are written **in the same database transaction** as the action that causes them, so a
failed action never leaves a half-recorded event or a notification about something that didn't
happen.

**Activity log** (`GET /documents/{id}/activity`, any member): an append-only timeline of
`document.created`, `version.created`, `version.restored`, `version.deleted`, `document.renamed`,
`member.added`, `member.role_changed` and `member.removed`, each with the actor and details
(version number, source, file name, change note, old and new title or role). The ORM refuses to
update or delete events, and there is no API to change them. History from before this feature
was backfilled from the versions table (`"backfilled": true`).

**Notification inbox** (`GET /notifications`, `/notifications/unread-count`,
`POST /notifications/{id}/read`, `POST /notifications/read-all`):

| Event | Who is notified |
|---|---|
| A meaningful new version (typed, uploaded or restored) | every other member; whitespace-only edits notify nobody |
| Document shared with you / your role changed / you were removed | that member (not when you leave yourself) |
| Document deleted | every other member; the notification outlives the document |

## Commands

Local development uses Python 3.12 in `.venv` and Postgres from Docker (host port 5434).

| Purpose | Command |
|---|---|
| Set up | `python3.12 -m venv .venv && source .venv/bin/activate && pip install -r requirements-dev.txt && cp .env.example .env` |
| Start the database | `docker compose up -d db` |
| Migrate | `alembic upgrade head` |
| Run the API (reloads on change) | `uvicorn app.main:app --reload` |
| Demo data | `python -m scripts.seed` |
| Lint and format check | `ruff check . && ruff format --check .` |
| Tests on SQLite, with coverage | `pytest --cov` |
| Create the Postgres test database (once) | `docker compose exec db createdb -U postgres sldm_test` |
| Tests on PostgreSQL | `TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5434/sldm_test pytest` |
| Quality floor (weakened tests, new suppressions) | `python scripts/floor_guard.py --base origin/main` |
| Latency baseline (API running) | `python -m scripts.bench --base http://localhost:8000` |

CI (`.github/workflows/ci.yml`) runs three jobs:
- lint and the SQLite suite, with the coverage floor of 97.5%;
- a migration round trip and the full suite on PostgreSQL;
- `pip-audit`, `gitleaks` and the floor guard.

The rules each check enforces are in [`CONSTRAINTS.md`](CONSTRAINTS.md).

## Operations

### Health checks

| Endpoint | Checks | Use for |
|---|---|---|
| `GET /api/health/live` | the process answers; never touches the database | liveness probe (restart if failing) |
| `GET /api/health/ready` (also `/api/health`) | `SELECT 1` on the database; `503 unavailable` if it fails | readiness probe (stop routing traffic) |

### Logs

Logs are JSON, one object per line, on stdout. Every request writes one `http_request` line with
`request_id`, `method`, the route template, `status`, `duration_ms` and `user_id`. Named events:
- `login_failed`, `login_rate_limited`;
- `upload_rejected` (with a reason code);
- `version_conflict`;
- `account_deleted`, `account_delete_refused`, `account_delete_rate_limited`;
- `unhandled_error` (with the traceback).

Fields are allowlisted: no tokens, passwords, emails or request bodies.

Every response carries an `X-Request-ID`, and every error body repeats it. To find a user's
failed request in the logs, search for that ID. A valid incoming UUID is kept, so a proxy's ID
carries through.

### Metrics

`GET /metrics` serves Prometheus metrics. It is not under `/api` and not in the API docs.
- `http_requests_total{method, route, status_class}`
- `http_request_duration_seconds{method, route}`

Labels use route templates and fixed sets only, so clients can't create new series. Set
`METRICS_TOKEN` to require `Authorization: Bearer <token>`; without it, the endpoint is open.

### Environment variables

Read from the environment or a local `.env` (see `.env.example`).

| Variable | Default | Notes |
|---|---|---|
| `ENVIRONMENT` | `development` | `production` turns on secure cookies and HSTS, and refuses the checks marked below |
| `DATABASE_URL` | Postgres on `localhost:5434` | SQLAlchemy URL, e.g. `postgresql+psycopg://user:pass@host:5432/db` |
| `SECRET_KEY` | development placeholder | **Production refuses** the default or anything under 32 characters |
| `CORS_ORIGINS` | `["http://localhost:5173"]` | JSON list; `*` is refused because the API uses cookies |
| `ACCESS_TOKEN_MINUTES` | `720` | Session length, 5 minutes to 7 days |
| `LOGIN_MAX_FAILURES`, `LOGIN_WINDOW_SECONDS` | `10`, `900` | Failed sign-ins (and wrong passwords on account deletion) before `429` |
| `LOGIN_MAX_FAILURES_PER_IP` | `100` | Failed sign-ins from one IP across all emails in the same window, so one address can't spray a password at every account |
| `MAX_UPLOAD_BYTES` | `10485760` (10 MB) | Set the same limit on any reverse proxy |
| `MAX_JSON_BYTES` | `9437184` (9 MB) | Every other request body |
| `FORWARDED_ALLOW_IPS` | `127.0.0.1,::1` | Proxies trusted for `X-Forwarded-For`. **Production refuses `*`**, which would let clients forge their IP |
| `METRICS_TOKEN` | unset | Bearer token for `/metrics` |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING` or `ERROR` |

### Deploying

- **Container:** the image runs as a non-root user. It applies migrations on start and serves with
  `--proxy-headers` and no `Server` header.
- **Behind a proxy:** set `FORWARDED_ALLOW_IPS` to the proxy's address, so the sign-in rate limit
  sees real client IPs.
- **Single process:** the sign-in rate limiter and the parse-slot limit are in memory, per
  process. Run one worker process, or add a shared store first (ADR 0001).
- **Memory:** size the container for 4 parse workers of up to 1 GiB each plus the API (about 5 GiB),
  or lower `PARSE_MAX_CONCURRENT` in `app/utils/extract.py`.
