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

Users who aren't members get `404`, so document ids can't be probed. Design and threat model:
[`docs/adr/0001-authentication-and-authorization.md`](docs/adr/0001-authentication-and-authorization.md).

## API Endpoints

All endpoints are under `/api`. Interactive docs: `http://localhost:8000/api/docs`.

| Method | Path | Who |
|---|---|---|
| `POST` | `/auth/register`, `/auth/login`, `/auth/logout` | anyone |
| `GET` | `/auth/me` | signed in |
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
| `GET` | `/health` | anyone |

Errors always have the shape `{"error": {"code": "...", "message": "...", "details": ...}}`.

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
- Limit: 10 MB (`MAX_UPLOAD_BYTES`). Oversized requests are refused from their `Content-Length`
  before the body is parsed (`413`).
- Refused with a clear `422`: password-protected or damaged PDFs, PDFs with no selectable text
  (scans; OCR isn't supported), PDFs over 500 pages, non-UTF-8 text, DOCX files over 50 MB
  uncompressed (zip bombs), and files with no text.
- DOCX paragraphs and tables are extracted in document order (table cells joined with ` | `).
  python-docx parses XML with entity resolution off (no XXE).

## Smart Notification System

When a new version is uploaded, the backend compares it with the latest saved version. Notifications run through FastAPI `BackgroundTasks`, so the API returns immediately. A notification is triggered only when the change is meaningful. Pure whitespace or formatting changes do not trigger notifications, which helps reduce noise for legal users.

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
