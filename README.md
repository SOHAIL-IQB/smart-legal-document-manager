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

The system uses three main tables:

### `users`

- `id`
- `name`
- `email`

### `documents`

- `id`
- `title`
- `created_at`
- `created_by`

### `document_versions`

- `id`
- `document_id`
- `version_number`
- `content`
- `edited_by`
- `created_at`

Relationships:

- One user can create many documents.
- One user can edit many document versions.
- One document can have many versions.
- Each document version stores the full content snapshot, so no previous content is overwritten.

## API Endpoints

### Core Document APIs

- `POST /documents`  
  Creates a new document and stores version `1`.
- `GET /documents`  
  Lists documents for frontend or reviewer access.
- `POST /documents/{id}/versions`  
  Creates a new document version if the content changed.
- `GET /documents/{id}/versions`  
  Returns version history for a document.
- `GET /documents/{id}/compare?v1=1&v2=2`  
  Compares any two versions of the same document.
- `PATCH /documents/{id}/title`  
  Updates document title without creating a new content version.
- `DELETE /documents/{id}/versions/{version}`  
  Deletes one specific version.
- `DELETE /documents/{id}?confirm=true`  
  Deletes the entire document after explicit confirmation.

Additional helper endpoints:

- `POST /users`
- `GET /users`
- `GET /documents/{id}`
- `GET /health`

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

### Local Setup

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Set the database connection:

```bash
export DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5432/smart_legal_document_manager"
```

4. Run migrations:

```bash
alembic upgrade head
```

5. Start the API:

```bash
uvicorn app.main:app --reload
```

### Docker Setup

```bash
docker-compose up --build
```

This starts PostgreSQL and the FastAPI service together for local evaluation.

Additional API usage examples are available in `examples/curl_requests.md`.

## Running Tests

```bash
pytest
```

The automated test suite verifies the main required flows, including creation, versioning, comparison, metadata updates, identical-content handling, and deletion.

## API Documentation

Swagger UI is available at:

`http://localhost:8000/docs`
