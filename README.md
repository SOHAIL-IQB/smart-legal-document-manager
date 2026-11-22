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
| `document_versions` | `id`, `document_id`, `version_number`, `content`, `edited_by`, `created_at` |

Each version stores a full content snapshot, so earlier content is never overwritten.

## Authentication and Permissions

Sign up or log in to get a session. Browsers receive an `httpOnly` cookie; API clients can use
the returned token as `Authorization: Bearer <token>`. Every document has members with a role:

| Action | viewer | editor | owner |
|---|:-:|:-:|:-:|
| Read document, versions, comparisons, members | ✓ | ✓ | ✓ |
| Add a version, rename | | ✓ | ✓ |
| Delete a version or the document, manage members | | | ✓ |

Users who aren't members get `404`, so document ids can't be probed. Design and threat model:
[`docs/adr/0001-authentication-and-authorization.md`](docs/adr/0001-authentication-and-authorization.md).

## API Endpoints

All endpoints are under `/api`. Interactive docs: `http://localhost:8000/api/docs`.

| Method | Path | Who |
|---|---|---|
| `POST` | `/auth/register`, `/auth/login`, `/auth/logout` | anyone |
| `GET` | `/auth/me` | signed in |
| `GET` / `POST` | `/documents` | signed in (lists only your documents) |
| `GET` | `/documents/{id}` | viewer+ |
| `PATCH` | `/documents/{id}/title` | editor+ |
| `DELETE` | `/documents/{id}?confirm=true` | owner |
| `GET` / `POST` | `/documents/{id}/versions` | viewer+ / editor+ |
| `DELETE` | `/documents/{id}/versions/{n}` | owner |
| `GET` | `/documents/{id}/compare?v1=&v2=` | viewer+ |
| `GET` / `POST` | `/documents/{id}/members` | viewer+ / owner |
| `PATCH` / `DELETE` | `/documents/{id}/members/{user_id}` | owner (any member may remove themselves) |
| `GET` | `/health` | anyone |

Errors always have the shape `{"error": {"code": "...", "message": "...", "details": ...}}`.

## Comparison Logic

The comparison feature uses Python's `difflib` library. The system splits document versions into lines and uses `unified_diff` to detect added, removed, and modified lines. The output is formatted to clearly show before and after changes so lawyers can easily review modifications.

Implementation approach:

```python
old_lines = old_text.splitlines()
new_lines = new_text.splitlines()

diff = difflib.unified_diff(
    old_lines,
    new_lines,
    fromfile="Before",
    tofile="After",
    lineterm="",
)
```

The response includes:

- `before`
- `after`
- `changes`
- `has_meaningful_changes`

This makes the comparison readable for legal review while preserving the exact text history for auditing.

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
