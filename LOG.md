# LOG — Smart Legal Document Manager

> Append-only record of what was actually done. Newest entry at the bottom.
> Every entry lists **what changed**, **commands run**, and **results observed**.
> Nothing is marked verified here unless the output was actually seen.

---

## 001 — 2026-11-22 — Clone and read

- Cloned `https://github.com/SOHAIL-IQB/smart-legal-document-manager` to `~/Desktop/smart-legal-document-manager`, branch `main`, HEAD `76c18e1`.
- Read every tracked file (≈1,574 lines): `app/` (config, main, database, schemas, routers, services, utils, notifications), `migrations/`, `tests/`, Docker, CI, README, USER_GUIDE, examples.
- Toolchain on this Mac: Python 3.15.2 (default), 3.12 and 3.14 also present; Node v26.13.0; npm; uv; Docker CLI present but **daemon not running**.

## 002 — 2026-11-22 — Baseline and defect probes

Commands and results:

| Command | Result |
|---|---|
| `python3 -m venv .venv && pip install -r requirements.txt` (Python 3.15) | **FAIL**: `No matching distribution found for psycopg-binary==3.2.13` |
| `python3.12 -m venv .venv && pip install -r requirements.txt` | OK |
| `pytest -q` (Python 3.12) | **6 passed**, 1 deprecation warning (starlette/anyio) |

Probe script (run outside the repo against SQLite with `TestClient`) — observed results:

| Probe | Observed |
|---|---|
| A. Create v2, delete v2, create new version | new version number = **2** (number reused) |
| B. Delete the only remaining version, then add a version | delete → 200; add → **404**; document shows `version_count: 0` |
| C. Create document passing someone's `user_id`, no credentials | **201** (no auth) |
| D. Title `" "` and content `"   "` | **201** (accepted) |
| E. `GET /documents?limit=1` with 3 documents | returned **3** (no pagination) |

Defects recorded as B1–B16 in PLAN.md §4.

## 003 — 2026-11-22 — Decisions confirmed by owner

- Location: `~/Desktop/smart-legal-document-manager`; work on `main` (no new branch).
- Frontend: React + Vite + TypeScript.
- Auth: JWT + per-document roles (owner/editor/viewer) with sharing.
- Extras: rich diff + search/pagination/restore; PDF/DOCX upload; notifications + audit log. AI summary declined.
- Wrote `PLAN.md` and `LOG.md`. No source code changed yet. Nothing committed.

## 004 — 2026-11-22 — Phase 1: backend foundation

**Housekeeping:** moving the session to Desktop copied an earlier throwaway clone in as a nested
`smart-legal-document-manager/` folder. Diffed it against the repo (only `tests/test.db` differed,
a gitignored test artifact) and deleted it.

**Changed**
- Dependencies: `requirements.txt` (runtime) and `requirements-dev.txt` (pytest 9.2, pytest-cov 7.1,
  httpx, ruff 0.17). Versions taken from `pip index versions` on 2026-11-22: fastapi 0.165.0,
  SQLAlchemy 2.1.9, alembic 1.20.1, psycopg 3.3.9, pydantic-settings 2.16.3, uvicorn 0.54.0.
  `uv pip compile` resolves on Python 3.12 and 3.15 (B11). Installed and tested on 3.12 only.
- Layout (`git mv`, history kept): `app/core/{config,errors}.py`, `app/db/{models,session}.py`,
  `app/api/router.py` + `app/api/routes/{health,users,documents,versions,compare}.py`,
  `app/services/{users,documents,versions}.py`, `app/schemas/{common,user,document}.py`,
  `app/utils/diff.py`. Removed `app/services/diff_service.py` (folded into `services/versions.py`).
- Errors (B7): `AppError` → `NotFoundError` / `ConflictError` / `PermissionDeniedError` /
  `AuthenticationError`. One set of handlers returns `{"error": {"code", "message", "details"?}}`
  for domain errors, validation errors, HTTP errors and unexpected errors (generic 500, details only in logs).
- Transactions: replaced the `begin_nested()/begin()` pattern with one `commit()` per service call;
  `get_db` rolls back on exceptions. SQLite now enforces foreign keys, as Postgres does.
- Config (B12, B13): DB URL default matches compose port 5434; `alembic.ini` no longer contains a URL
  (`migrations/env.py` reads settings); `CORS_ORIGINS` containing `*` is rejected at startup;
  CORS methods and headers are listed explicitly.
- Validation (B5): blank or whitespace-only titles, names and content → 422. Titles are trimmed.
  Content is stored exactly as sent. Content capped at 2,000,000 characters.
- Docker: Python 3.12, non-root user, runs migrations then the server; compose sets env explicitly
  instead of loading `.env.example`; `.dockerignore` added.
- CI: Python 3.12, installs dev requirements, `ruff check`, `ruff format --check`, `pytest --cov-fail-under=85`.
- `pyproject.toml`: ruff (incl. bandit `S` rules), pytest, coverage config.

**Behaviour changes (intentional)**
- All endpoints are now under `/api` (e.g. `/api/documents`); Swagger is at `/api/docs`.
- Emails are stored lowercase; duplicate check is case-insensitive.
- Adding a version to a document with no versions → 409 (was 404). Phase 3 removes that state entirely.
- Error bodies use the shape above instead of FastAPI's `{"detail": ...}`.

**Verified**
| Command | Result |
|---|---|
| `pytest --cov --cov-fail-under=85` | **23 passed**, coverage **97.36%** |
| `diff <(git show HEAD:tests/test_document_api.py) <(sed 's#/api/#/#g' tests/test_document_api.py)` before ruff | identical — original 6 tests changed only by URL prefix |
| `ruff check .` / `ruff format --check .` | clean (after `ruff --fix` + `ruff format`; fixes were line wrapping, import order, `x == "lit"` order) |
| `uvicorn app.main:app` + curl | `/` 200, `/api/health` `{"status":"ok"}`, create user 201, blank title → 422 in new error shape, `/api/docs` 200, no errors in server log |

**Not verified yet:** Postgres + `alembic upgrade head` (Docker daemon not running); Docker image build.
**Still open from audit:** B2, B3, B4, B8 (Phase 3) reproduce as before — expected.
Nothing committed.

## 005 — 2026-11-22 — Phase 1 committed; Phase 2: authentication and roles

**Commits (Phase 1):** `c066166` docs: plan + log · `2947ca3` chore: dependencies · `0a3e640` refactor: layers, errors, validation, CORS.

**Design:** threat model + decisions in `docs/adr/0001-authentication-and-authorization.md`.
Library APIs checked by running them, not from memory: `pwdlib.PasswordHash.recommended()` →
`$argon2id$v=19$m=65536,t=3,p=4`; `jwt.decode(..., options={"require": [...]})` (PyJWT 2.15.1).

**Changed**
- Deps: `pyjwt==2.15.1`, `pwdlib[argon2]==0.4.2`.
- `app/core/config.py`: `SECRET_KEY` (production refuses the default or anything < 32 chars), 12 h token
  lifetime, cookie name, rate-limit settings, `cookie_secure` in production.
- `app/core/security.py`: Argon2id hashing, dummy-hash verify for unknown emails (timing), JWT create/decode
  (`sub`, `typ=access`, `iat`, `exp` required; HS256 only), in-memory `LoginRateLimiter`
  (prunes empty keys so memory can't grow without bound).
- `app/db/models.py`: `Role` enum with ranks; `users.password_hash`, `users.created_at`;
  `documents.updated_at`; new `DocumentMember` (composite PK, role CHECK, cascade delete).
- `migrations/versions/20261122_0002_auth_and_members.py`: adds the columns/table and backfills each
  document's creator as owner; legacy users get an unusable hash.
- `app/api/deps.py`: `get_current_user` (bearer first, else cookie; cookie writes need
  `X-Requested-With`), `require_role()` → `ViewerAccess` / `EditorAccess` / `OwnerAccess`.
- `app/api/routes/auth.py` (register/login/logout/me), `app/api/routes/members.py` (sharing),
  `app/services/members.py` (last-owner guard locks owner rows `FOR UPDATE`).
- Documents/versions/compare routes take the authorized document from the dependency; `user_id`
  removed from every request body; list shows only the caller's documents with `my_role`.
- Removed `app/api/routes/users.py` (`GET /users` listed every account).
- Tests: `conftest.py` gains `signup`/`alice`/`make_document` fixtures and `TEST_DATABASE_URL`;
  original 6 tests ported to bearer auth with assertions kept, plus `test_meaningful_change_sends_notification`
  (the old suite only proved the *negative* case) and edited-by attribution; new `test_auth.py`,
  `test_permissions.py` (40-cell matrix + sharing rules).
- Docs: README sections for schema/auth/endpoints/running/tests rewritten; `USER_GUIDE.md` rewritten
  for the auth flow; `examples/curl_requests.md` removed (duplicated the guide).

**Bugs I introduced and caught during this phase**
- `document.updated_at = func.now()` would leave a SQL expression on the object after commit
  (`expire_on_commit=False`) → replaced with `datetime.now(UTC)`.
- 403 message read "you are a editor" → "your role is editor".

**Verified**
| Check | Result |
|---|---|
| `pytest --cov --cov-fail-under=85` (SQLite) | **108 passed**, coverage **98.07%** |
| same suite with `TEST_DATABASE_URL` → Postgres 16 | **108 passed** |
| Mutation check: 6 security checks broken one at a time (role rank, membership scoping, CSRF, token type, last-owner guard, rate limit) | **6/6 made the suite fail**; files restored, suite green after |
| `alembic upgrade` → seed legacy rows → `upgrade head` → `downgrade base` → `upgrade head` → `alembic check` (SQLite and Postgres) | backfill `owner|old@x.com|!unusable`; no server default left on `password_hash`; no model drift |
| `docker compose up --build api` | image builds, migrations run, `/api/health` ok, process runs as `appuser` |
| curl flow on live server | cookie write w/o header → 403; with header → 201; outsider → 404; viewer edit → 403 |
| Every `bash` block in `USER_GUIDE.md` executed in order against a live server | all responses match the guide |
| `ruff check .` / `ruff format --check .` | clean |

**Known limits (documented in ADR 0001):** logout doesn't revoke copied tokens; rate limiter is per process;
owners can tell whether an email is registered when sharing.
**Still open from audit:** B2, B3, B4, B8 (Phase 3). Phase 2 not committed yet.
