# Smart Legal Document Manager

Smart Legal Document Manager is a backend-first FastAPI application for law-focused document tracking. It preserves full document version history, supports precise comparisons between versions, suppresses notifications for trivial formatting changes, and keeps metadata changes separate from versioned legal content.

## Features

- Create legal documents with an automatic initial version snapshot.
- Store every substantive update as a new immutable document version.
- Reject identical uploads to prevent version clutter.
- Compare any two versions using `difflib` unified diff output.
- Update document titles without creating new versions.
- Delete individual versions or entire documents with explicit confirmation.
- Trigger background notifications only for meaningful text changes.
- Expose OpenAPI docs through FastAPI Swagger UI for future frontend integration.

## Architecture

The project follows a modular backend structure:

```text
smart-legal-document-manager/
├── app/
│   ├── config.py
│   ├── main.py
│   ├── database/
│   ├── notifications/
│   ├── routers/
│   ├── schemas/
│   ├── services/
│   └── utils/
├── migrations/
├── tests/
├── README.md
├── USER_GUIDE.md
└── requirements.txt
```

Key design choices:

- `routers/` contains HTTP endpoints only.
- `services/` contains business logic for versioning, metadata updates, and diff orchestration.
- `database/` defines SQLAlchemy models and DB session management.
- `utils/diff_utils.py` centralizes text normalization and diff generation.
- `notifications/notification_service.py` keeps asynchronous notification behavior isolated and swappable.

## Tech Stack

- Python 3.11+
- FastAPI
- SQLAlchemy 2.0
- PostgreSQL
- Alembic
- `difflib`
- pytest

## Setup

1. Create and activate a Python virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Configure environment variables:

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

Swagger UI will be available at `http://127.0.0.1:8000/docs`.

## Docker Setup

For a full local stack with PostgreSQL:

```bash
docker compose up --build
```

This starts:

- PostgreSQL on `localhost:5432`
- FastAPI on `http://127.0.0.1:8000`

The API container automatically runs `alembic upgrade head` before starting the server.

## Data Model

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

Each document stores complete text snapshots in `document_versions`, which guarantees traceability and avoids destructive overwrites.

## API Endpoints

### Users

- `POST /users`
- `GET /users`

### Documents

- `POST /documents`
- `GET /documents`
- `GET /documents/{id}`
- `PATCH /documents/{id}/title`
- `DELETE /documents/{id}?confirm=true`

### Versions

- `POST /documents/{id}/versions`
- `GET /documents/{id}/versions`
- `DELETE /documents/{id}/versions/{version}`

### Comparison

- `GET /documents/{id}/compare?v1=1&v2=2`

## Comparison Logic

Version comparison uses Python’s built-in `difflib.unified_diff`:

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

The API response includes:

- `before`: full text from version 1
- `after`: full text from version 2
- `changes`: unified diff lines
- `has_meaningful_changes`: boolean derived from normalized content

Meaningful-change detection removes formatting-only differences by collapsing whitespace before comparison. That allows the system to keep the version history accurate while suppressing noisy notifications.

## Notification System

When a new version is created:

1. The latest saved version is compared with the submitted content.
2. If the content is identical, the API returns `"No changes detected"` and no version is created.
3. If the content differs only by formatting or whitespace, a new version is created but no notification is emitted.
4. If the content changes meaningfully, FastAPI `BackgroundTasks` schedules a notification log event immediately after the response is prepared.

The current implementation logs notifications, which makes it easy to swap in email, webhook, or audit-stream integrations later.

## Testing

Run the test suite with:

```bash
pytest
```

CI also runs this suite automatically on pushes to `main` and on pull requests through GitHub Actions.

The tests use SQLite for isolation and cover:

- document creation and initial versioning
- identical content handling
- version comparison output
- title updates without version creation
- trivial-change notification suppression
- version and document deletion flows

## Future Enhancements

- full audit event table
- pagination and search
- authentication and authorization
- richer diff rendering for frontend UIs
