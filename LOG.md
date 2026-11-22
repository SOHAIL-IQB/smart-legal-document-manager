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
