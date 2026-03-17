# User Guide

## Start the Service

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Set the PostgreSQL connection string:

```bash
export DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5432/smart_legal_document_manager"
```

3. Apply migrations:

```bash
alembic upgrade head
```

4. Run the API:

```bash
uvicorn app.main:app --reload
```

## Start with Docker

If you want the API and PostgreSQL together without local database setup:

```bash
docker compose up --build
```

Then open:

- API docs: `http://127.0.0.1:8000/docs`
- API base URL: `http://127.0.0.1:8000`

## How to Test Features

### 1. Create a User

```bash
curl -X POST http://127.0.0.1:8000/users \
  -H "Content-Type: application/json" \
  -d '{"name":"Alice","email":"alice@example.com"}'
```

Use the returned `id` as `user_id` in later requests.

### 2. Create a Document

```bash
curl -X POST http://127.0.0.1:8000/documents \
  -H "Content-Type: application/json" \
  -d '{"title":"Employment Agreement","content":"This contract is valid for 1 year.","user_id":1}'
```

Expected behavior:

- a new document is created
- version `1` is stored automatically

### 3. Update the Document

```bash
curl -X POST http://127.0.0.1:8000/documents/1/versions \
  -H "Content-Type: application/json" \
  -d '{"content":"This contract is valid for 2 years.","user_id":1}'
```

Expected behavior:

- a new version is created
- previous content remains untouched
- meaningful changes trigger a background notification log entry

### 4. Verify Identical Content Handling

```bash
curl -X POST http://127.0.0.1:8000/documents/1/versions \
  -H "Content-Type: application/json" \
  -d '{"content":"This contract is valid for 2 years.","user_id":1}'
```

Expected response:

```json
{
  "message": "No changes detected",
  "document_id": 1,
  "version": null
}
```

### 5. Compare Two Versions

```bash
curl "http://127.0.0.1:8000/documents/1/compare?v1=1&v2=2"
```

The response includes:

- the full `before` content
- the full `after` content
- `changes` as unified diff output
- a `has_meaningful_changes` flag

### 6. List Version History

```bash
curl http://127.0.0.1:8000/documents/1/versions
```

Use this endpoint to feed future frontend history timelines.

### 7. Update Document Title Without Versioning

```bash
curl -X PATCH http://127.0.0.1:8000/documents/1/title \
  -H "Content-Type: application/json" \
  -d '{"title":"Updated Employment Agreement"}'
```

Expected behavior:

- only the document metadata changes
- no additional content version is created

### 8. Delete a Specific Version

```bash
curl -X DELETE http://127.0.0.1:8000/documents/1/versions/2
```

Expected behavior:

- version `2` is removed
- the document record remains available

### 9. Delete an Entire Document

```bash
curl -X DELETE "http://127.0.0.1:8000/documents/1?confirm=true"
```

Expected behavior:

- the document and its remaining versions are deleted
- calling the endpoint without `confirm=true` returns an error

## Automated Test Suite

Run:

```bash
pytest
```

This validates the core PRD flows in an isolated SQLite test database.
