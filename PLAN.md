# PLAN — Smart Legal Document Manager (portfolio rebuild)

> The source of truth for **what** we are building and **in what order**.
> `LOG.md` records **what actually happened**. Every claim in LOG.md must point to evidence
> (a command run, a test result, a file path). If PLAN and code disagree, stop and reconcile.

Status legend: `[ ]` not started · `[~]` in progress · `[x]` done and verified · `[!]` blocked

---

## 1. Goal

Turn a backend-only FastAPI assignment into a complete, deployable, portfolio-grade web app:
a secure, multi-user document version-control system for legal teams, with a polished React UI.

## 2. Decisions (confirmed by owner on 2026-11-22)

| # | Decision | Choice |
|---|----------|--------|
| D1 | Location / branch | `~/Desktop/smart-legal-document-manager`, work directly on `main` |
| D2 | Frontend stack | React + Vite + TypeScript SPA in `/frontend` |
| D3 | Auth | Email/password, hashed passwords, JWT; per-document roles owner / editor / viewer; sharing |
| D4 | Extra features | Rich word-level diff + search/filters/pagination + restore · PDF/DOCX/TXT upload · In-app notifications + audit log |
| D5 | Not in scope | AI change summary (declined) |

## 3. Assumptions (correct me if wrong — otherwise these stand)

1. **Python 3.12** is the runtime (local + Docker). Python 3.15 on this Mac cannot install the current pins.
2. **PostgreSQL 16** in production/dev via Docker; **SQLite** stays for the fast unit-test suite. CI also runs tests against real Postgres.
3. **Versions are never hard-deleted.** "Delete version" becomes a soft delete (`deleted_at`), version numbers are never reused, and the last live version cannot be deleted. (Legal audit trail requirement.)
4. **Token transport:** JWT in an `httpOnly`, `SameSite=Lax` cookie for the browser; `Authorization: Bearer` also accepted so Swagger/curl keep working.
5. **Search** uses portable `ILIKE` on title + latest content (works on SQLite and Postgres). Postgres full-text search is a later upgrade if needed.
6. **Uploads**: max 10 MB; `.pdf`, `.docx`, `.txt`; only extracted text is versioned (original file is not stored).
7. **Frontend libs**: Tailwind CSS + shadcn/ui primitives (21st.dev components are built on these), TanStack Query, React Router, react-hook-form + zod.
8. No commits until you ask. Commit messages follow your global rule (no AI attribution).

## 4. Audit — confirmed defects in the original backend

Verified by running probes against the original code (see LOG.md entry 002).

| ID | Defect | Evidence | Fix phase |
|----|--------|----------|-----------|
| B1 | No authentication — any client passes any `user_id` and acts as that user | probe C: 201 | P2 |
| B2 | Deleting the latest version, then adding one, **reuses the version number** (audit trail broken) | probe A: new version = 2 again | P3 |
| B3 | Deleting the only version leaves a document with 0 versions that can **never be edited again** (404) | probe B | P3 |
| B4 | Concurrent version POSTs compute `latest+1` → unique-constraint error → unhandled 500 | code: `version_service.py:60` | P3 |
| B5 | Whitespace-only title/content accepted | probe D: 201 | P1 |
| B6 | No pagination/search; list endpoints return everything | probe E | P4 |
| B7 | `ValueError` used as "404" everywhere — any unrelated ValueError becomes a 404 | `routers/*.py` | P1 |
| B8 | `create_version` loads **all versions' full content** just to read the latest | `version_router.py:35` | P3 |
| B9 | Notifications only go to the server log; no recipients, no persistence | `notification_service.py` | P6 |
| B10 | Diff is a raw unified-diff string list; not usable for a side-by-side UI | `diff_utils.py` | P4 |
| B11 | Pins fail to install on Python ≥3.13 (`psycopg-binary==3.2.13`) | pip error, LOG 002 | P1 |
| B12 | README local setup uses port 5432 but docker-compose exposes 5434; `alembic.ini` hardcodes a URL | files | P1 |
| B13 | CORS `*` together with `allow_credentials=True` | `main.py:19` | P1 |
| B14 | Duplicate-email race on user create → 500 instead of 409 | `user_router.py:15` | P2 |
| B15 | `/health` doesn't check the database; no request IDs / structured logs | `main.py` | P7 |
| B16 | CI runs only pytest on SQLite; no lint, no migration check, no Postgres | `ci.yml` | P7 |

## 5. Target architecture

```
frontend/ (React + Vite + TS)  ──HTTP /api──▶  app/ (FastAPI)
                                                 ├─ api/        routers (thin: parse, authorize, call service)
                                                 ├─ services/   business logic, transactions
                                                 ├─ core/       config, security (JWT, hashing), errors, logging
                                                 ├─ db/         models, session
                                                 ├─ schemas/    pydantic request/response models
                                                 └─ utils/      diff engine, text extraction
                                               PostgreSQL (Alembic migrations)
```

### Data model (after rebuild)

- `users` — id, name, email (unique), password_hash, created_at
- `documents` — id, title, created_by, created_at, updated_at (document delete stays a hard delete: owner only, requires `confirm=true`)
- `document_members` — document_id, user_id, role (`owner|editor|viewer`), added_at · PK(document_id, user_id)
- `document_versions` — id, document_id, version_number, content, content_hash, word_count, change_note, source (`manual|upload|restore`), source_filename, restored_from, edited_by, created_at, deleted_at, deleted_by
- `notifications` — id, user_id, document_id, kind, message, read_at, created_at
- `activity_events` — id, document_id, actor_id, action, details (JSON), created_at — **append-only**

### API (v1, prefix `/api`)

Auth: `POST /auth/register` · `POST /auth/login` · `POST /auth/logout` · `GET /auth/me`
Documents: `GET /documents?q=&role=&sort=&limit=&offset=` · `POST /documents` · `GET /documents/{id}` · `PATCH /documents/{id}` · `DELETE /documents/{id}?confirm=true`
Upload: `POST /documents/upload` (new doc from file) · `POST /documents/{id}/versions/upload`
Versions: `GET /documents/{id}/versions` · `GET /documents/{id}/versions/{n}` · `POST /documents/{id}/versions` · `POST /documents/{id}/versions/{n}/restore` · `DELETE /documents/{id}/versions/{n}` (soft)
Compare: `GET /documents/{id}/compare?v1=&v2=` → structured hunks with word-level segments + stats
Sharing: `GET/POST /documents/{id}/members` · `PATCH/DELETE /documents/{id}/members/{user_id}`
Activity: `GET /documents/{id}/activity`
Notifications: `GET /notifications` · `GET /notifications/unread-count` · `POST /notifications/{id}/read` · `POST /notifications/read-all`
Ops: `GET /health` (checks DB)

Error shape everywhere: `{"error": {"code": "not_found", "message": "...", "request_id": "..."}}`

### Permission matrix

| Action | viewer | editor | owner |
|---|:-:|:-:|:-:|
| Read doc, versions, compare, activity | ✓ | ✓ | ✓ |
| Add version / upload / restore | | ✓ | ✓ |
| Rename | | ✓ | ✓ |
| Soft-delete a version | | | ✓ |
| Manage members, delete document | | | ✓ |

Non-members get **404** (not 403) so document IDs aren't enumerable.

## 6. Quality bar (Definition of Done for every phase)

- Backend: `ruff check` clean · `pytest` green · coverage ≥ 85% on `app/` · `alembic upgrade head` works on fresh Postgres
- Frontend: `tsc --noEmit` clean · `eslint` clean · `vite build` succeeds · no console errors on any page
- Accessibility: WCAG 2.2 AA on all pages (axe: 0 serious/critical), full keyboard use
- Every phase ends with a LOG.md entry containing the commands run and their results
- No test is skipped, deleted, or weakened to get green

## 7. Phases

Checkpoints marked ⏸ are where I stop and ask you to review before continuing.

### Phase 0 — Planning `[x]`
- [x] Clone, read every file, run tests, probe defects
- [x] Confirm decisions with owner
- [x] Write PLAN.md + LOG.md
- ⏸ **Owner approves this plan**

### Phase 1 — Backend foundation `[x]` (LOG 004)
- [x] Upgrade pins to current versions that install on 3.12+; Dockerfile → 3.12 (B11)
- [x] Restructure into `api/ core/ db/ services/ schemas/ utils/` (move, don't rewrite logic)
- [x] Domain exceptions + one global handler + consistent error shape (B7)
- [x] Settings: `.env` driven, explicit CORS origins, alembic reads settings only (B12, B13) — *secret key moved to Phase 2, where it is first used*
- [x] Validation: trim + reject blank title; reject blank content but store it byte-for-byte (B5)
- [x] Add `ruff`, `pytest-cov`; existing 6 tests ported (URL prefix only) and green
- **Verify:** 23 passed · 97% coverage · ruff clean · uvicorn boots and serves `/api/docs`
- Note: README / USER_GUIDE / `examples/` still show the old paths without `/api` and `user_id` bodies. They are rewritten once the API settles (Phase 2 for the auth flow, Phase 10 for everything).

### Phase 2 — Auth & roles `[x]` (LOG 005, ADR 0001)
- [x] `password_hash` on users; register/login/logout/me; JWT cookie + bearer (B1)
- [x] `document_members` + `require_role()` dependency; creator becomes owner
- [x] Remove `user_id` from request bodies — actor always comes from the token
- [x] Sharing endpoints; IntegrityError → 409 on duplicate email (B14)
- [x] Login rate limit (in-memory, per IP + email, 10 failures / 15 min)
- [x] CSRF guard for cookie-authenticated writes (`X-Requested-With`) — *added; not in original plan*
- [x] Tests: auth flows, every cell of the permission matrix, non-member gets 404
- [x] Migration `0002` with owner backfill
- **Verify:** 108 passed on SQLite (98% cov) **and on Postgres 16**; 6/6 security mutations caught; curl flow + USER_GUIDE executed live
- Removed `GET/POST /users` (account list was an information leak; registration replaces create).
- Later options noted in ADR 0001: server-side token revocation; shared-store rate limiter for multi-instance.

### Phase 3 — Versioning correctness `[ ]`
- [ ] Soft delete; numbers from `MAX(version_number)` incl. deleted; block deleting last live version (B2, B3)
- [ ] Lock document row (`SELECT … FOR UPDATE`) when creating a version + retry/409 on conflict (B4)
- [ ] Fetch latest version with one query, not by loading all (B8)
- [ ] Version metadata: change_note, content_hash, word_count, source
- [ ] Restore endpoint (creates a new version from an old one)
- [ ] Migration `0002`
- [ ] Tests: regression tests for B2, B3, B4 written **first** (must fail on old code)
- **Verify:** pytest green; regression tests demonstrably failed before fix

### Phase 4 — Diff, search, pagination `[ ]`
- [ ] Diff engine: line opcodes + word-level segments inside changed lines + stats (added/removed/changed); keep `has_meaningful_changes` (B10)
- [ ] `GET /documents` with `q`, `role`, `sort`, `limit`, `offset`, returns `{items, total}` (B6)
- [ ] Document list items include latest version number, updated_at, my role, word count
- **Verify:** unit tests for diff engine edge cases (empty, identical, reorder, unicode)

### Phase 5 — File upload `[ ]`
- [ ] `pypdf` + `python-docx`; size limit; extension + magic-byte check; empty-text PDFs → clear 422
- [ ] New-document-from-file and new-version-from-file
- **Verify:** tests with small fixture PDF/DOCX/TXT files

### Phase 6 — Notifications & audit log `[ ]`
- [ ] `notifications` table; meaningful change → notify every member except actor (B9)
- [ ] Also notify on: shared with you, role changed
- [ ] `activity_events` append-only; recorded inside the same transaction as the action
- [ ] Endpoints + tests
- **Verify:** pytest green

### Phase 7 — Hardening & ops `[ ]`
- [ ] Security review (security-and-hardening skill + security-auditor agent): OWASP pass, headers, secrets
- [ ] Request-ID middleware, JSON logs, `/health` checks DB (B15)
- [ ] Seed script with demo users + realistic contracts (for portfolio demo)
- [ ] docker-compose: db + api + frontend; CI: ruff, pytest (SQLite + Postgres service), alembic check, frontend build (B16)
- [ ] Code review pass (code-reviewer agent) + simplification
- ⏸ **Owner reviews finished backend**

### Phase 8 — Design direction `[ ]`
- [ ] `impeccable` skill: design brief, direction, tokens (DESIGN.md)
- [ ] 21st.dev: source component candidates (data table, command/search, diff view, notifications popover, upload dropzone, auth forms)
- ⏸ **Owner approves the look before full build**

### Phase 9 — Frontend build `[ ]`
- [ ] Scaffold Vite + TS + Tailwind + shadcn; typed API client; auth context; route guards
- [ ] Pages: Landing · Sign in / Sign up · Documents dashboard (search, filters, pagination) · Document workspace (editor, version timeline, compare side-by-side, activity, sharing) · Notifications · Upload flow · 404
- [ ] Loading / empty / error states for every view
- [ ] Frontend tests (Vitest + Testing Library) for auth, API client, diff view

### Phase 10 — Verification & launch `[ ]`
- [ ] Browser test every flow end-to-end in the built-in browser; zero console errors
- [ ] Accessibility audit (accessibility-auditor agent) + fixes
- [ ] Performance audit (web-performance-auditor agent)
- [ ] README rewrite with screenshots, architecture diagram, run instructions; ADRs in `docs/adr/`
- [ ] Deployment notes (Render/Fly for API + Postgres, Vercel/Netlify for frontend)
- ⏸ **Owner final review; commit/push only on request**

## 8. Skill map

| Phase | Skills / agents |
|---|---|
| 0 | using-agent-skills, interview (questions), spec-driven-development, planning-and-task-breakdown |
| 1–6 | incremental-implementation, api-and-interface-design, test-driven-development, source-driven-development, debugging-and-error-recovery, doubt-driven-development (auth + concurrency) |
| 7 | security-and-hardening, observability-and-instrumentation, ci-cd-and-automation, code-review-and-quality, code-simplification |
| 8–9 | impeccable, 21st-ui (21st MCP), frontend-ui-engineering |
| 10 | browser-testing, accessibility-engineering, performance-optimization, documentation-and-adrs, shipping-and-launch, git-workflow-and-versioning |

## 9. Open items / blockers

- ~~`[!]` Docker daemon not running~~ — resolved 2026-11-22 (Docker 29.2.0); Postgres container `smart-legal-document-manager-db` is up on port 5434.
- Account deletion / data export (privacy) is not planned yet. Candidate for Phase 7.
