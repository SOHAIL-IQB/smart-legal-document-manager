# User Guide

This guide shows how to test the main Smart Legal Document Manager features through the API.

Before testing document endpoints, create a user because document creation requires `user_id`.

## Prerequisite: Create a User

Endpoint: `POST /users`

Example request:

```json
{
  "name": "Alice",
  "email": "alice@example.com"
}
```

Example curl:

```bash
curl -X POST http://localhost:8000/users \
  -H "Content-Type: application/json" \
  -d '{"name":"Alice","email":"alice@example.com"}'
```

Use the returned `id` value in later requests as `user_id`.

## 1. Create Document

Endpoint: `POST /documents`

Example request body:

```json
{
  "title": "Employment Agreement",
  "content": "This contract is valid for 1 year.",
  "user_id": 1
}
```

Example curl:

```bash
curl -X POST http://localhost:8000/documents \
  -H "Content-Type: application/json" \
  -d '{"title":"Employment Agreement","content":"This contract is valid for 1 year.","user_id":1}'
```

Expected result:

- a new document is created
- version `1` is stored automatically

## 2. Update Document (Create New Version)

Endpoint: `POST /documents/{id}/versions`

Example request body:

```json
{
  "content": "This contract is valid for 2 years.",
  "user_id": 1
}
```

Example curl:

```bash
curl -X POST http://localhost:8000/documents/1/versions \
  -H "Content-Type: application/json" \
  -d '{"content":"This contract is valid for 2 years.","user_id":1}'
```

Expected result:

- a new version is created
- previous versions remain unchanged
- meaningful changes trigger a background notification

## 3. Compare Versions

Endpoint: `GET /documents/{id}/compare?v1=1&v2=2`

Example curl:

```bash
curl "http://localhost:8000/documents/1/compare?v1=1&v2=2"
```

Expected result:

- the response shows `before`
- the response shows `after`
- the response includes unified diff lines in `changes`

## 4. Update Document Title

Endpoint: `PATCH /documents/{id}/title`

Example request body:

```json
{
  "title": "Updated Employment Agreement"
}
```

Example curl:

```bash
curl -X PATCH http://localhost:8000/documents/1/title \
  -H "Content-Type: application/json" \
  -d '{"title":"Updated Employment Agreement"}'
```

Expected result:

- the title changes
- no new document version is created

## 5. Delete a Version

Endpoint: `DELETE /documents/{id}/versions/{version}`

Example curl:

```bash
curl -X DELETE http://localhost:8000/documents/1/versions/2
```

Expected result:

- the specified version is removed
- the document still exists

## 6. Delete Entire Document

Endpoint: `DELETE /documents/{id}?confirm=true`

Example curl:

```bash
curl -X DELETE "http://localhost:8000/documents/1?confirm=true"
```

Expected result:

- the document and remaining versions are deleted

## Helpful Follow-Up Checks

List documents:

```bash
curl http://localhost:8000/documents
```

List versions:

```bash
curl http://localhost:8000/documents/1/versions
```

Open Swagger UI:

```text
http://localhost:8000/docs
```
