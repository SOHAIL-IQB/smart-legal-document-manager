# Working on this repository

Read this file first, then `CONSTRAINTS.md`. Do not weaken `CONSTRAINTS.md` to make a change pass.

## Start of every session

1. Read the resume line at the top of `PLAN.md` and the newest entry in `LOG.md`.
2. Run `git status`, `git log --oneline -3` and the checks below. If they don't match what the log
   says, stop and reconcile before changing anything.
3. Work only on what the current phase's approved spec in `docs/specs/` lists.

## Stack

- Python 3.12 (the machine's default Python is newer; always use `.venv`), FastAPI 0.165, SQLAlchemy 2.1,
  Alembic, PostgreSQL 16 (SQLite for the fast test run), pydantic-settings, PyJWT, pwdlib (Argon2id),
  pypdf, python-docx.
- Frontend (from Phase 9): React + Vite + TypeScript in `frontend/`.

## Commands

| Purpose | Command |
|---|---|
| Set up | `python3.12 -m venv .venv && source .venv/bin/activate && pip install -r requirements-dev.txt` |
| Database | `docker compose up -d db` (Postgres on host port 5434; test DB `sldm_test`) |
| Migrate | `alembic upgrade head` |
| Run API | `uvicorn app.main:app --reload` → <http://localhost:8000/api/docs> |
| Lint | `ruff check . && ruff format --check .` |
| Tests (SQLite) | `pytest --cov` |
| Tests (Postgres) | `TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5434/sldm_test pytest` |
| Floor guard | `python scripts/floor_guard.py --base origin/main` |

## Layout

- `app/api/routes/`: thin routes, which parse input, resolve access (`app/api/deps.py`) and call a service.
- `app/services/`: business rules and transactions. One commit per action. The activity event and
  notifications are added in the same transaction.
- `app/core/`: config, errors (one error shape), security, limits.
- `app/db/models.py`: models. Timestamps use `UTCDateTime` and `utcnow()`.
- `migrations/versions/`: additive migrations, each with a tested downgrade.
- `tests/`: pytest; fixtures `signup`, `alice` and `make_document` live in `tests/conftest.py`.
- `docs/adr/`: decisions (`NNNN-title.md`). `docs/specs/`: per-phase specs.

## Conventions

- Errors: raise `NotFoundError`, `ConflictError`, `PermissionDeniedError`, `GoneError` or
  `AuthenticationError`; never `HTTPException` in services. Non-members get 404, not 403.
- JSON and query parameters are snake_case. List endpoints return `{items, total, limit, offset}`.
- Validate at the API boundary (pydantic schemas); trust data inside services.
- New behavior needs a test that fails without it. A bug fix starts with a failing test.
- Every new guard is broken once on purpose, and the suite must fail; record the result in `LOG.md`.
- Framework-specific code follows the official docs for the pinned version; cite the URL in the
  commit message or `LOG.md`.

## Boundaries

- Always: run lint, both test suites and the floor guard before committing; append a numbered entry
  to `LOG.md` with the commands run and the results seen.
- Ask first: database schema changes outside an approved spec, new dependencies, CI changes, anything
  that rewrites git history.
- Never: commit secrets or `.env`; skip, delete or weaken tests; add suppressions without a tracked
  exception; force-push.

## Commits and pushes

- Conventional messages (`feat:`, `fix:`, `docs:`, `test:`, `chore:`, `ci:`, `refactor:`), explaining why.
- Authored by the repository owner only: no co-author trailers, and no mention of AI tools in commit
  messages, pull requests or any tracked file.
- Work happens on `main`; push at the end of every phase or checkpoint, then confirm CI is green.
