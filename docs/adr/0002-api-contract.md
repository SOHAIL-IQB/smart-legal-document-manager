# ADR 0002 — API contract: naming, pagination, errors, retry safety

- Status: accepted (2026-11-23)
- Phase: 7 (task T9)

## Context

The API grew over Phases 1–6 without these conventions being decided in writing. The frontend
(Phase 9) will be the first real consumer, so this is the cheapest moment to fix them: after that,
every observable behavior becomes something a client depends on (Hyrum's law).

## Decision

1. **One version, extended additively.** All endpoints live under `/api`; there is no `/v1`. New
   fields are optional and added, never renamed or removed in place. A breaking change would get
   a new ADR and a migration plan rather than a second version running alongside.
2. **snake_case** for JSON fields and query parameters (`created_at`, `unread_only`). It matches
   Python and the database columns. Changing to camelCase now would touch every endpoint and test
   for no functional gain; the frontend maps names in its API client.
3. **Lists are paginated** with `limit` and `offset` and return
   `{"items": [...], "total": N, "limit": L, "offset": O}`. The order is stable (a tie-breaker on
   `id`), so pages don't overlap.
4. **One error shape** everywhere, including framework and middleware errors:

   ```json
   {"error": {"code": "not_found", "message": "Document 7 was not found.",
              "details": [...], "request_id": "4f6c…"}}
   ```

   `code` is stable and machine-readable; `message` is for people; `details` appears only for
   validation errors; `request_id` matches the `X-Request-ID` header and the server logs.

   | Status | Code | Meaning |
   |---|---|---|
   | 400 | `bad_request` | Malformed request (e.g. delete without `confirm=true`) |
   | 401 | `unauthorized` | Not signed in, or the session is invalid or expired |
   | 403 | `forbidden` | Signed in and a member, but the role is too low; or a missing CSRF header |
   | 404 | `not_found` | Missing, **or not shared with you** (so IDs can't be probed) |
   | 405 | `method_not_allowed` | Path exists, method doesn't |
   | 409 | `conflict` | Duplicate, last owner, last version, simultaneous edit |
   | 410 | `gone` | The version existed and was deleted |
   | 413 | `payload_too_large` | Body over the limit (9 MB JSON, 10 MB uploads) |
   | 415 | `unsupported_media_type` | Upload isn't PDF/DOCX/TXT, or its contents don't match the extension |
   | 422 | `validation_error` / `unreadable_file` | Invalid fields / the file can't be read |
   | 429 | `rate_limited` | Too many failed logins; `details.retry_after` in seconds |
   | 500 | `internal_error` | Unexpected; details only in the logs |
   | 503 | `unavailable` / `busy` | Database unreachable / too many files being read |

5. **Retry safety is documented per state-changing endpoint.** Idempotency keys are not
   implemented; instead, almost every write is naturally safe to retry:

   | Endpoint | Safe to retry? | What a retry does after the first call succeeded |
   |---|---|---|
   | `POST /auth/register` | yes | 409 (account already exists) |
   | `POST /auth/login`, `POST /auth/logout` | yes | signs in / out again |
   | `POST /documents` | **no** | creates a second document |
   | `POST /documents/upload` | **no** | creates a second document |
   | `PATCH /documents/{id}/title` | yes | same title: no change |
   | `DELETE /documents/{id}` | yes | 404 |
   | `POST /documents/{id}/versions` and `/versions/upload` | yes | identical content: 200 "No changes detected" |
   | `POST /documents/{id}/versions/{n}/restore` | yes | identical content: 200 "No changes detected" |
   | `DELETE /documents/{id}/versions/{n}` | yes | 410 |
   | `POST /documents/{id}/members` | yes | 409 (already a member) |
   | `PATCH` / `DELETE /documents/{id}/members/{user_id}` | yes | same role / 404 |
   | `POST /notifications/{id}/read`, `/notifications/read-all` | yes | no change |
   | `DELETE /auth/me` | yes | 401 (the account's tokens no longer work) |

   A client that retries `POST /documents` or `POST /documents/upload` after a network error
   should first check the document list.

## Alternatives considered

- **camelCase JSON:** conventional for JavaScript clients, but a full rename now with no
  functional gain. Rejected for the reasons in decision 2.
- **Idempotency keys** (`Idempotency-Key` header stored with the result): the correct general
  solution, but it needs a key store with a unique constraint and a retention policy. With only two
  non-retry-safe endpoints, both used by a person clicking a button, it was deferred.
- **Page/size pagination** (`page`, `page_size`): friendlier for page numbers, but offset/limit is
  simpler to implement correctly and still lets the UI compute pages from `total`.

## Consequences

- The README endpoint table is checked against the live OpenAPI schema by
  `tests/test_api_docs.py`, so it can't silently drift from the code.
- Adding an idempotency key later is additive: an optional header on the two unsafe endpoints.
- The frontend's API client owns the snake_case ↔ camelCase mapping.
