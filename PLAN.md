# PLAN — Smart Legal Document Manager (portfolio rebuild)

> The source of truth for **what** we are building and **in what order**.
> `LOG.md` records **what actually happened**. Every claim in LOG.md must point to evidence
> (a command run, a test result, a file path). If PLAN and code disagree, stop and reconcile.

> **Resume point (2026-11-27):** Phase 8 (design direction) done and approved: product named Inkstep, visual world the Folding Sequence. **Phase 9 Slice A done (F0–F3) and `GET /auth/session`; Slice B F4 landing, F5 sign in/up and F6 documents index done (finish reviews: ship); next: F9 `DESIGN.md` (due after F4 and one app screen), then F7 document workspace.** Details: LOG.md entries 019–034; `docs/specs/phase-9-frontend-build.md`.

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

### Phase 3 — Versioning correctness `[x]` (LOG 006)
- [x] Soft delete; numbers from `MAX(version_number)` incl. deleted; block deleting last live version (B2, B3)
- [x] Lock document row (`SELECT … FOR UPDATE`) when creating a version; 409 if a unique clash still happens (B4)
- [x] Fetch latest version with one query, not by loading all (B8) — done during Phase 1/2, confirmed by grep
- [x] Version metadata: change_note, content_hash, word_count, source, restored_from
- [x] Restore endpoint (creates a new version from an old one) + `GET /versions/{n}`; history list omits content
- [x] Migration `0003` (the plan said 0002; 0002 was used by Phase 2)
- [x] Tests: regression tests for B2, B3, B4 written **first** and shown failing on old code
- [x] CI: added a Postgres job (migration round-trip + full suite) so B4 runs in CI — *pulled forward from Phase 7*
- **Verify:** 133 passed on Postgres; 132 + 1 skipped (B4, needs Postgres) on SQLite, 98% cov; 7/7 mutations caught

### Phase 4 — Diff, search, pagination `[x]` (LOG 007)
- [x] Diff engine: line opcodes + word-level segments inside changed lines + stats (added/removed/changed); keep `has_meaningful_changes` (B10)
- [x] `context=N` collapses unchanged runs into `skip` rows; `whitespace_only` flag per changed row — *added*
- [x] `GET /documents` with `q`, `role`, `sort`, `order`, `limit`, `offset`, returns `{items, total, limit, offset}` (B6)
- [x] List items (and detail, same query) include owner name, my role, latest live version, live count, word count
- **Verify:** 27 diff unit tests incl. 300 seeded random cases; 185 passed on Postgres; 3 SQL statements per list regardless of size; 12/12 mutations caught after strengthening two tests
- Later: Postgres full-text or `pg_trgm` index if content search gets slow (currently a sequential `ILIKE`).

### Phase 5 — File upload `[x]` (LOG 008)
- [x] `pypdf` + `python-docx`; size limit; extension + magic-byte check; empty-text PDFs → clear 422
- [x] Also: encrypted PDFs, page cap (500), DOCX zip-bomb check (50 MB inflated), non-UTF-8 text, filename sanitizing
- [x] New-document-from-file and new-version-from-file; `source_filename` column (migration `0004`)
- [x] Content-Length middleware rejects oversized uploads before parsing
- **Verify:** 43 upload tests on files generated in code (no binaries in git); 229 passed on Postgres; 10/10 mutations caught; live curl with real PDF/DOCX
- Later: OCR for scanned PDFs (would need Tesseract); keeping the original file (would need object storage).

### Review fixes after Phase 5 `[x]` (LOG 009, 010)
- [x] R1 streaming body-size limit · R2 database cascade on document delete · R3 CSRF tests for every write method · R6 dead alias removed · R7 shared helper moved

### Phase 6 — Notifications & audit log `[x]` (LOG 012)
- [x] `notifications` table; meaningful change → notify every member except actor (B9)
- [x] Also notify on: shared with you, role changed, removed, document deleted (notification outlives the document)
- [x] `activity_events` append-only (ORM refuses update/delete); recorded inside the same transaction as the action; history backfilled
- [x] Endpoints + tests; migration `0006`
- [x] Found and fixed: SQLite returned timestamps without a timezone → `UTCDateTime` column type
- **Verify:** 266 passed on Postgres; 13/13 mutations caught after fixing one test; migration backfill checked on both databases; USER_GUIDE run live

### Phase 7 — Hardening & ops `[x]` (spec: `docs/specs/phase-7-hardening.md`, LOG 013–019)
- [x] R4 (T4): set `FORWARDED_ALLOW_IPS` / `--proxy-headers` for the host's proxy so the login rate limit sees real client IPs (LOG 009)
- [x] R5 (T6): run PDF/DOCX extraction with a CPU time limit (subprocess + timeout) (LOG 009)
- [x] R8 (T3): security headers (`X-Content-Type-Options`, `Referrer-Policy`, `X-Frame-Options`, CSP for the API docs) (LOG 009)
- [x] Security review: OWASP pass, headers, secrets (T2, T3, T13; done without agents at the owner's request)
- [x] Request-ID middleware, JSON logs, `/health` checks DB, RED metrics (B15; T7, T8)
- [x] Seed script with demo users + realistic contracts (T10)
- [x] docker-compose: db + api; CI: ruff, pytest (SQLite + Postgres service), alembic round trip and check (B16). The frontend container and frontend build join when the frontend exists (Phases 9–10).
- [x] Rules file + written quality bar + floor guard (T1); CI dependency audit, secret scan, floor guard (T2); JWT `iss`/`aud` (T5); ADR 0002 API contract (T9); performance baseline in `PERF.md` (T11)
- [x] Account deletion (anonymized) and data export (T15; owner answered open question 2)
- [x] Changelog + README structure, every README command run on a clean clone (T12)
- [x] Backend review (T13): 1 High + 4 Medium found and fixed, trade-offs recorded (LOG 017)
- [x] Simplification pass (T14): 3 behavior-neutral changes, 2 missing floor guard tests added (LOG 018)
- [x] **Owner reviews finished backend**: signed off 2026-11-27 (LOG 019)

### Phase 8 — Design direction `[x]` (spec: `docs/specs/phase-8-design-direction.md`, LOG 019–025)
- [x] Interview and `PRODUCT.md`; product named **Inkstep** after a full name check
- [x] `impeccable` skill: visual world **the Folding Sequence**, direction contract in `.impeccable/surfaces/`. `DESIGN.md` moved to Phase 9 (written from the built screens)
- [x] 21st.dev: component candidates in `docs/design/components.md`
- [x] **Owner approves the look before full build**: approved 2026-11-27

### Phase 9 — Frontend build `[~]` (spec: `docs/specs/phase-9-frontend-build.md`, approved 2026-11-27)
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

All 26 skills, 7 reference checklists and 5 agents were read on 2026-11-23 (LOG 013).

### What was actually used in Phases 0–6 (corrected 2026-11-23)

The earlier version of this table listed skills as used that were never loaded. This is the
accurate record.

| Skill | Loaded and followed | Notes |
|---|---|---|
| using-agent-skills | Phase 0 | |
| git-workflow-and-versioning | every commit since Phase 1 | |
| security-and-hardening | Phase 2 (ADR 0001 threat model) | |
| test-driven-development | Phases 3–6 (failing test first) | |
| code-review-and-quality | review after Phase 5 (LOG 009) | |
| interview-me | **no** | Phase 0 asked 4 questions in one batch; the skill asks one at a time with a guess |
| spec-driven-development, planning-and-task-breakdown | **no** | PLAN.md was written without them; no per-phase spec or approval gate |
| api-and-interface-design | **no** | error shape and pagination happen to match it; naming and retry-safety never decided |
| source-driven-development | **no** | library behavior was checked by reading installed source, not official docs with citations |
| documentation-and-adrs | **no** | ADR 0001 written without it; only one ADR exists |
| debugging-and-error-recovery | **no** | Phase 4 flaky failure: evidence (failing test name) was not preserved |
| incremental-implementation, doubt-driven-development | **no** | no fresh-context reviews of non-trivial decisions |

### Which skill governs which remaining work

| Work | Skills | Agents |
|---|---|---|
| Every phase, before code | spec-driven-development → planning-and-task-breakdown (approval gate each) | |
| Every task | incremental-implementation, test-driven-development, source-driven-development (cite official docs), git-workflow-and-versioning | |
| Non-trivial decisions | doubt-driven-development (cross-model offered each cycle; no Gemini/Codex CLI installed) | fresh-context reviewer |
| Quality bar | constraint-driven-development (`CONSTRAINTS.md`) | |
| Project rules file | context-engineering (`AGENTS.md`) | |
| Phase 7 | security-and-hardening, observability-and-instrumentation, ci-cd-and-automation, api-and-interface-design, documentation-and-adrs, performance-optimization (baseline only), code-simplification | security-auditor, code-reviewer, test-engineer |
| Phase 8 | interview-me (design intent), frontend-ui-engineering + impeccable + 21st | |
| Phase 9 | frontend-ui-engineering, browser-testing-with-devtools (built-in browser pane), test-driven-development | |
| Phase 10 | accessibility-engineering, performance-optimization, shipping-and-launch, documentation-and-adrs | accessibility-auditor, web-performance-auditor, code-reviewer, security-auditor |
| Anything breaks | debugging-and-error-recovery (stop the line, preserve evidence) | |
| Not applicable | idea-refine (scope already decided), deprecation-and-migration (no consumers yet; its expand/contract rules still apply to every migration) | |

## 9. Open items / blockers

- ~~`[!]` Docker daemon not running~~ — resolved 2026-11-22 (Docker 29.2.0); Postgres container `smart-legal-document-manager-db` is up on port 5434.
- Account deletion / data export: done in Phase 7 (T15, LOG 015).
