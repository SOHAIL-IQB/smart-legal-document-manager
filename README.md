# Smart Legal Document Manager

## Overview

Smart Legal Document Manager is a backend-first system built for legal teams that need reliable document traceability. It helps lawyers track document changes through version history, compare any two versions, and trigger smart notifications only when meaningful content changes occur. The API is designed for future frontend integration while already providing everything needed for backend evaluation and testing.

## Features

- Document version tracking
- Version comparison (diff)
- Smart notification system
- Metadata management
- Safe data storage with transactions
- Background processing

## Technology Stack

- FastAPI
- PostgreSQL
- SQLAlchemy
- Alembic
- Docker
- GitHub Actions CI
- pytest

## System Architecture

The project follows a modular FastAPI structure so each layer has a clear responsibility.

- `app/routers/` handles REST API endpoints.
- `app/services/` contains business logic such as version creation, comparison orchestration, and delete operations.
- `app/database/` manages SQLAlchemy models and database sessions.
- `app/notifications/` contains background notification logic.
- `app/utils/` contains reusable helper functions such as diff formatting and meaningful-change detection.
- `tests/` contains automated API tests.
- `migrations/` contains Alembic migration files.

## Project Structure

```text
smart-legal-document-manager/

app/
routers/
services/
database/
notifications/
utils/

tests/
migrations/

README.md
USER_GUIDE.md
Dockerfile
requirements.txt
```

## Database Schema

| Table | Purpose |
|---|---|
| `users` | `id`, `name`, `email` (unique, lowercase), `password_hash` (Argon2id), `created_at` |
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

`GET /documents/{id}/compare` aligns the two versions line by line with Python's `difflib`
(auto-junk off, so documents that repeat headings or signature lines still align), then compares
each changed line word by word. The response contains:

- `rows`: side-by-side rows of type `equal`, `insert`, `delete`, `replace` or `skip`, with line
  numbers for each side. `replace` rows carry `old_segments` / `new_segments`
  (`{"op": "equal" | "delete" | "insert", "text": ...}`) that rebuild each line exactly, and a
  `whitespace_only` flag.
- `stats`: lines added / removed / changed and words added / removed.
- `context=N` keeps N unchanged lines around each change and collapses the rest into `skip` rows.
- `has_meaningful_changes`, plus `before`, `after` and a unified diff in `changes`.

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

## Running the Project

Requires Python 3.12+ and Docker.

### Docker (API + PostgreSQL)

```bash
docker compose up --build
```

The API runs at `http://localhost:8000` and applies migrations on start. PostgreSQL is published
on host port `5434`.

### Local development

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
docker compose up -d db
alembic upgrade head
uvicorn app.main:app --reload
```

### Demo data

```bash
python -m scripts.seed                          # local
docker compose exec api python -m scripts.seed  # in the container
```

Creates three demo users (`asha@demo.example`, `ben@demo.example`, `chloe@demo.example`, password
`demo password 2026`) and four sample contracts. The contracts include version history, a restore,
a deleted version, sharing in every role, and the resulting activity and notifications. Running it
again changes nothing, and it refuses to run when `ENVIRONMENT=production`.

Walkthrough of every feature with curl: [`USER_GUIDE.md`](USER_GUIDE.md).

## Running Tests

```bash
pytest --cov                # fast, on SQLite
ruff check . && ruff format --check .
```

To run the same suite against PostgreSQL:

```bash
TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5434/sldm_test pytest
```
