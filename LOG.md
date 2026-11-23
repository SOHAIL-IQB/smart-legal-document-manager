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

## 006 — 2026-11-22 — Phase 2 pushed; Phase 3: versioning correctness

**Pushed:** owner asked to push to GitHub at the end of every phase. Phase 1+2 commits pushed
(`76c18e1..c9d8f3b`). Checked first: no AI attribution in any commit message or tracked file.
CI run `44993011933` on `c9d8f3b`: **success**.

**Red first (Prove-It).** `tests/test_version_regressions.py` written before any fix, run on the old code:

| Test | SQLite (old) | Postgres (old) |
|---|---|---|
| B2 numbers never reused | FAIL `assert 2 == 3` | FAIL |
| B3 last version can't be deleted | FAIL `assert 200 == 409` | FAIL |
| B4 8 concurrent saves | skipped (needs row locks) | FAIL `[500, 201, …, 500]` — confirms B4, which was only inferred from code before |

**Changed**
- `document_versions`: `content_hash` (sha256), `word_count`, `change_note` (≤500, trimmed), `source`
  (`manual|restore|upload`, CHECK), `restored_from`, `deleted_at`, `deleted_by`. Migration `0003`
  backfills hash and word count.
- `app/services/versions.py` rewritten around three invariants: numbers only grow (`MAX` over all
  versions incl. deleted), soft delete only and ≥1 live version, `SELECT … FOR UPDATE` on the document
  row for every save/delete. Unique-constraint clash → 409 instead of 500.
- New `GoneError` (410): fetching, comparing or restoring a deleted version; deleting twice.
- Endpoints: `GET /documents/{id}/versions/{n}` (full content), `POST …/versions/{n}/restore`,
  `GET …/versions?include_deleted=true`. History list now returns summaries **without content**
  (editor name, hash, word count, source, note, deletion info).
- Detail `version_count` / `latest_version` count live versions only.
- CI: new `backend-postgres` job (Postgres 16 service): `alembic upgrade → downgrade base → upgrade → check`, then the full suite.
- Docs: README schema/invariants/endpoints; USER_GUIDE sections 4–7.

**Test changes**
- `test_content_whitespace_is_preserved_exactly` now reads content from `GET /versions/1` because the
  list no longer includes content (assertion unchanged).
- New `tests/test_versioning.py` (16 tests); permission matrix gains "get one version" (viewer+) and
  "restore version" (editor+).

**Verified**
| Check | Result |
|---|---|
| Regression tests after fix, Postgres | B2, B3, B4 **PASSED**; B4 repeated 3× — passed each time |
| `pytest --cov` (SQLite) | **132 passed, 1 skipped** (B4), coverage **98%** |
| Full suite on Postgres 16 | **133 passed** |
| Mutations, one at a time (row lock removed [on Postgres], hard delete, numbering ignores deleted, last-version guard off, list shows deleted, deleted readable, restore unmarked) | **7/7 made the suite fail**; `versions.py` restored byte-for-byte (shasum) |
| Migration 0003 with a seeded legacy row, SQLite and Postgres: upgrade → downgrade → upgrade → `alembic check` | backfill `word_count=5`, hash `cf13f4ac…` = `shasum -a 256` of the content; no drift |
| Every `bash` block in USER_GUIDE.md run against a live server | matches the documented responses |
| `ruff check` / `ruff format --check` | clean |
| B8 | `grep -rn "\.versions\b" app/` finds no use of the relationship |

**Note:** the new CI job is validated as YAML locally; its first real run is on this push.

## 007 — 2026-11-22 — Phase 4: structured diff, search and pagination

**CI for Phase 3 push** (`ef73400`, run `44993754153`): `backend` success, `backend-postgres` success —
the B4 concurrency test now runs in CI.

**Changed**
- `app/utils/diff.py`: `diff_documents()` → side-by-side `rows` (`equal|insert|delete|replace|skip`, 1-based
  line numbers per side), word-level `old_segments`/`new_segments` for `replace` rows, `whitespace_only`,
  `stats` (lines added/removed/changed, words added/removed), optional `context` collapsing.
  Tokenizer: `\w+|\s+|[^\w\s]` (Unicode), so segments rebuild each line exactly.
  Line and word matching use `autojunk=False`. A whitespace-only match between two changes is
  absorbed so "1 year" → "2 years" is one change. `build_unified_diff` / `has_meaningful_changes` kept.
- `GET /documents/{id}/compare`: adds `rows`, `stats`, `version_1_meta`, `version_2_meta`, `context` (0–50).
  `before`, `after`, `changes`, `has_meaningful_changes` unchanged.
- `app/services/documents.py`: one query (`_summaries_for`) for list and detail: membership join,
  live-version stats subquery, latest version join, creator join. `search_documents()` adds `ILIKE` on
  title + latest live content with `%`, `_`, `\` escaped; role filter; sort `updated_at|created_at|title`
  (title via `lower()`); `limit` 1–100, `offset` ≥ 0; total counted from the filtered query.
- **Breaking:** `GET /documents` returns `{items, total, limit, offset}` instead of a list. Document responses
  gain `created_by_name`, `latest_version`, `version_count`, `word_count`.
- `pyproject.toml`: tests may use seeded `random` (ruff S311).
- Docs: README comparison + search sections and endpoint table; USER_GUIDE sections 5–6.

**Tests:** written before the engine and run red (`ImportError: cannot import name 'diff_documents'`).
First green run: 4 failures.
- 2 were wrong expectations in my tests: the blank-line fixture already ended in a newline, so
  appending `"\nNew…"` really inserts two lines; and 10 unchanged lines with 2 lines of context
  collapse to 8, not 10. Fixed the tests.
- 2 were a real engine gap: words split around a matched space ("1", " ", "year"). Fixed in the
  engine (whitespace absorption).
New files: `tests/test_diff_engine.py` (27, incl. a 300-case seeded invariant test: rows rebuild both
documents, line numbers are contiguous, segments rebuild each line, stats equal row counts) and
`tests/test_document_list.py` (22). Adjusted for the new list shape: three `.json()` → `.json()["items"]`
in `test_permissions.py`; the 500 test patches `search_documents`. Assertions unchanged.

**Mutation testing found two weak tests**
- Turning line autojunk on survived: my blank-line example doesn't trigger difflib's junk heuristic.
  A random search (400 trials) found autojunk adding up to 393 wrong changed lines. Added a
  deterministic case: 400 lines over 20 repeated headings, one edit → 1 changed row
  (autojunk: 200). Now caught.
- Dropping `lower()` from title sort survived: the titles sorted the same either way. Added
  "Delta" (byte order: Apple, Delta, banana). Now caught on SQLite. On Postgres (`en_US.utf8`
  collation) the result is identical with or without `lower()`, so nothing can catch it there.
  `lower()` stays for SQLite and `C`-collation databases.

**Verified**
| Check | Result |
|---|---|
| `pytest` (SQLite) | **185 passed, 1 skipped** (B4), 5 runs in a row; coverage **98%** |
| Full suite on Postgres 16 | **186 passed**, 5 runs in a row (after the timestamp fix below) |
| Mutations (wildcard escaping [Postgres], stats incl. deleted, content not searched, total=0, no space absorption, autojunk on, whitespace flag off, context ignored, title sort case-sensitive [SQLite]) | **all caught** (2 only after strengthening the tests, above) |
| SQL statements per `GET /documents` (SQLAlchemy event counter) | **3** with 1 document and with 25 (no N+1); versions list: 4 |
| USER_GUIDE run against a live server | compare shows insert segment `"2 years"`; search `q=contract` finds the document by its text |
| `ruff check` / `ruff format --check` | clean |

**Flaky failure — investigated, original not reproduced, two latent defects fixed**
- A final Postgres run reported `1 failed, 185 passed`. The rerun was green; 6 more full runs and
  40 runs of the timing-sensitive tests were green too. I didn't capture which test failed (no `-rf`),
  so **the root cause is not proven**. From here on, suite runs use `-rf`.
- Found while investigating:
  1. `documents.updated_at` came from two clocks: the database `now()` on insert, Python's clock on edit
     and delete. Measured skew host↔container: about −0.6 ms.
  2. `test_new_version_bumps_document_updated_at` compared ISO strings. Pydantic drops the fraction when
     microseconds are 0, and `"…59Z"` sorts after `"…59.5Z"`. Now compares parsed datetimes.
- First fix: use the database `now()` everywhere. Checked my Phase 2 assumption first: SQLAlchemy
  **does** expire an attribute set to a SQL expression after commit and reloads a real datetime, so my
  Phase 2 note ("leaves a SQL expression on the object") was wrong. This fix then failed
  `test_default_sort_is_most_recently_updated_first` on SQLite, because `CURRENT_TIMESTAMP` has
  one-second resolution and the three writes tied.
- Final fix: the app is the single clock. `models.utcnow()` is the Python `default` / `onupdate` for all 5
  timestamp columns and is used for edits and soft deletes. `server_default=now()` stays for raw-SQL
  inserts. No schema change (`alembic check` clean on SQLite and Postgres).

## 008 — 2026-11-22 — Phase 5: file upload (PDF, DOCX, TXT)

**CI for Phase 4 push** (`11353b9`, run `44995869184`): `backend` success, `backend-postgres` success.

**Checked before writing code** (the code under test is the parsing of untrusted files)
- python-docx 1.2.0: `docx/oxml/parser.py:19` builds `etree.XMLParser(remove_blank_text=True, resolve_entities=False)` → no XXE.
- pypdf 7.1.1: has `is_encrypted`, decompression limits (`ZLIB_MAX_OUTPUT_LENGTH`, …, `LimitReachedError`).
- AES-encrypted test PDFs need the `cryptography` package; used RC4-128 for the fixture (the server
  refuses any encrypted PDF without decrypting, so the algorithm doesn't matter).

**Changed**
- Deps: `python-multipart==0.0.34`, `pypdf==7.1.1`, `python-docx==1.2.0`.
- `app/utils/extract.py`: type from magic bytes (`%PDF-`, `PK\x03\x04`, NUL ⇒ binary) and must match the
  extension (else 415); PDF: refuse encrypted / > 500 pages / damaged / no text; DOCX: sum of uncompressed
  sizes ≤ 50 MB checked before python-docx opens it, paragraphs and tables in body order; TXT: UTF-8 (BOM ok).
  Text normalized (CRLF → LF, trailing spaces, ≤ 1 blank line in a row). `safe_filename` keeps the base name
  (POSIX and Windows separators), drops control characters, caps at 255.
- `app/api/routes/uploads.py`: `POST /documents/upload` (title defaults to the file name),
  `POST /documents/{id}/versions/upload` (editor+, `change_note`). Plain `def` routes, so DB work and parsing
  run in FastAPI's threadpool. I first wrote them `async`, which would have blocked the event loop on the
  synchronous DB calls, and changed it before running anything.
- `app/main.py`: middleware returns 413 when `Content-Length` > limit + 64 KB, before the body is parsed;
  the route also caps the bytes it reads (no `Content-Length` case).
- `max_upload_bytes` setting (10 MB, `.env.example`); `document_versions.source_filename` (migration `0004`).
- Docs: README "File Upload" + endpoints; USER_GUIDE section 8.

**Tests** (`tests/files.py` builds real PDFs, DOCX, encrypted and blank PDFs and a zip bomb in memory)
- Written first; red with `ModuleNotFoundError: app.utils.extract`.
- Wrong assumptions in my tests, fixed:
  1. Expected message text "does not match"; the code says "do not match".
  2. A NUL in a multipart filename: httpx percent-encodes it, so the server got `Lease%00.txt`.
     Control-character stripping is now tested on `safe_filename` directly; the API test covers
     POSIX, Windows and absolute paths.
- Coverage gap found myself: the 413 test stayed under the middleware's allowance, so it only exercised the
  route check. Added a test that fails if the route runs; disabling the middleware check makes it fail.

**Verified**
| Check | Result |
|---|---|
| `pytest --cov` (SQLite) | **228 passed, 1 skipped**, coverage **98%** (`extract.py` 97%) |
| Full suite on Postgres 16 | **229 passed** |
| Mutations (mismatch allowed, encrypted accepted, zip-bomb check off, page cap off, binary as txt, paths kept, text cap off, route size check off, blank-line collapse off, middleware off) | **10/10 caught** |
| Migration 0004 up → down → up → `alembic check`, SQLite and Postgres | clean, no drift |
| Live server + curl `-F` with generated files | PDF → doc 201; DOCX with table → v2 201 (`source_filename` kept); scan → 422; disguised `.pdf` → 415; 11 MB → 413 in 0.5 ms |
| Whole USER_GUIDE run against a live server | upload step → version 4 as documented |
| `ruff check` / `ruff format --check` | clean (S108 on a test filename marked as a false positive) |

## 009 — 2026-11-22 — Review of the backend (Phases 1–5) before Phase 6

Reviewed ref `f617336` (clean tree, equals `origin/main`; CI run `44997621191` green on both jobs).
Scope `76c18e1..f617336`: 46 files under `app/` and `migrations/`, +2385 / −672. Every source file read in full.
Each finding below was confirmed by an experiment, not only by reading.

| # | Severity | Finding | Evidence |
|---|---|---|---|
| R1 | **Critical** (also in the original code) | Request bodies have no size limit before parsing. FastAPI reads the body before auth dependencies run, and the upload guard only checks a declared `Content-Length`. Unauthenticated chunked requests are read in full. | 300 MB chunked JSON to `/api/auth/login`, no auth: server RSS 149 → **1094 MB**, then 422. 60 MB chunked multipart to `/api/documents/upload`, no auth: fully read, then 401. |
| R2 | Required | Deleting a document loads every version (full `content`) and deletes them one row at a time (ORM cascade, no `ON DELETE CASCADE`). | SQL trace for a 30-version document (100 KB each): `SELECT document_versions.id, …, content, …` then per-row `DELETE … WHERE id =`. |
| R3 | Required (test gap) | CSRF check is only tested on POST. | Mutations exempting DELETE or PATCH from the check: **228 passed** (survived). |
| R4 | Consider → Phase 7 | Behind a proxy that isn't on localhost, `request.client.host` is the proxy's IP. All users then share one login rate-limit bucket, and 10 bad passwords lock an email out for everyone for 15 min. | uvicorn `--forwarded-allow-ips` defaults to `$FORWARDED_ALLOW_IPS` / 127.0.0.1; Dockerfile sets neither. |
| R5 | Consider → Phase 7 | PDF/DOCX parsing has no CPU time limit; a crafted file can occupy a worker thread. pypdf only caps decompression. | Code reading (`app/utils/extract.py`); not reproduced. |
| R6 | Nit | `DocumentDetailResponse = DocumentResponse` alias has no users (dead code). | `grep -rn DocumentDetailResponse app tests` → only its definition. |
| R7 | Nit | `uploads.py` imports `respond_to_version_result` from another route module. | `app/api/routes/uploads.py:9`. |
| R8 | FYI → Phase 7 | No security headers (`X-Content-Type-Options`, `Referrer-Policy`, …). | Already planned. |

**Checked and fine:** authorization on every document route (outsider → 404; 17 tests fail if it becomes 403);
last-owner guards; password check; token expiry; `alg=none`; LIKE escaping; N+1 (3 statements per list);
no secrets in code; `pip-audit -r requirements.txt` → **No known vulnerabilities found**; `ruff` S-rules clean.
Mutations run in this review: 7 (5 caught, 2 survived → R3).

**Status:** findings only; nothing changed in code yet.

## 010 — 2026-11-22 — Review fixes R1, R2, R3, R6, R7

Owner said "Fix them now". Regression tests written first (`tests/test_review_fixes.py`): R1 and R2 tests
**failed** on the old code. The R3 tests passed, because the CSRF code was correct; they exist to catch the
two mutations that survived the review, and now do.

**R1 — request body cap (Critical)**
- First approach: FastAPI 0.165's built-in `max_body_size`, which I found in its source (`fastapi/_body_limit.py`).
  Rejected after testing: its middleware sits outside all user middleware (`build_middleware_stack`) and
  answers a *declared* oversized body with Starlette's plain-text `Content Too Large`, breaking the API's
  error format (test failed with `JSONDecodeError`).
- Also checked: FastAPI turns any exception raised while it parses the body into `400 "There was an error
  parsing the body"` but re-raises `HTTPException` (`fastapi/routing.py`). So the custom middleware raises
  Starlette's `HTTPException(413)`.
- Final: `app/core/limits.py` `BodySizeLimitMiddleware` (pure ASGI). It refuses a declared `Content-Length`
  over the limit without reading anything, and counts streamed bytes (chunked) and stops at the limit.
  Limits: uploads `MAX_UPLOAD_BYTES` + 64 KB multipart room; everything else `MAX_JSON_BYTES` = 9 MB
  (≥ 2,000,000 × 4-byte UTF-8 + framing; test sends 2,000,000 emoji → 201).
  It runs inside CORS, so a 413 carries CORS headers (tested). It replaces the Phase 5 Content-Length-only middleware.
- My test mistake: a "9.5 MB upload" of `"word "` extracts to 9.5 M characters, over the 2 M content limit,
  so 422 was correct. Replaced with a file that's mostly blank lines (normalized away).

**R2 — cascade delete:** `document_versions.document_id` → `ON DELETE CASCADE`; `passive_deletes=True` on
`Document.versions` / `.members`. Migration `0005` replaces the FK (Postgres name `document_versions_document_id_fkey`,
read from `pg_constraint`; SQLite via a batch naming convention).
**R3:** CSRF test for POST version, PATCH title, DELETE version, DELETE document, POST restore (refused
without the header, allowed with it).
**R6:** removed unused `DocumentDetailResponse`. **R7:** `respond_to_version_result` → `app/api/version_responses.py`.
**R4, R5, R8** → added to Phase 7 in PLAN.md.

**Verified**
| Check | Result |
|---|---|
| `pytest --cov` (SQLite) | **240 passed, 1 skipped**, coverage **98%** (`limits.py` 98%), before the last no-read test (+1) |
| Full suite on Postgres 16 | **241 passed** |
| Mutations: DELETE/PATCH exempt from CSRF (survived in the review), streaming count off, declared check off, uploads get JSON limit, `passive_deletes` off, limiter removed | **7/7 caught**. The declared-check mutation survived at first (the streaming count still produced a 413); added an ASGI-level test that fails if the body is read. |
| Live uvicorn, no auth: 60 MB chunked multipart, 300 MB chunked JSON | both **413 immediately**; server RSS **146 → 155 MB** (review: 149 → 1094 MB) |
| Live: declared 50 MB JSON | 413; normal register still 201 |
| Migration 0005, SQLite and Postgres, with rows | after upgrade a raw `DELETE FROM documents` cascades (2 → 0 versions); after downgrade it's refused again (FK error); `alembic check` clean |
| `ruff check` / `ruff format --check` | clean |
| Final runs after all edits | SQLite **241 passed, 1 skipped**; Postgres **242 passed** |

## 011 — 2026-11-22 — End of session: where to resume

**State:** Phases 0–5 and the review fixes are done, committed and pushed. `main` = `origin/main` = `71e1ff4`
(15 commits since the original `76c18e1`). CI run `44998908950` green on both jobs. Working tree clean.
Tests: SQLite 241 passed + 1 skipped (Postgres-only concurrency test); Postgres 242 passed.

**Start here next session → Phase 6: notifications + audit log** (PLAN.md §7)
1. `notifications` table (user_id, document_id, kind, message, read_at, created_at); a meaningful new
   version notifies every member except the editor. Also notify on "shared with you" and "role changed".
   Replace the log-only `app/notifications/notification_service.py` (still uses naive local time).
2. `activity_events` table, append-only (document_id, actor_id, action, details JSON, created_at), written
   in the **same transaction** as the action: create, version, restore, upload, rename, delete version,
   member add/change/remove.
3. Endpoints: `GET /notifications`, `GET /notifications/unread-count`, `POST /notifications/{id}/read`,
   `POST /notifications/read-all`, `GET /documents/{id}/activity` (viewer+). Paginate both lists.
4. Migration `0006`; tests written first; mutation checks; run on SQLite and Postgres; update README,
   USER_GUIDE, PLAN, LOG; commit and push (owner wants a push at the end of every phase).

**Then:** Phase 7 (now includes review items R4 proxy IPs for the rate limit, R5 parse time limit,
R8 security headers), Phase 8 design direction with impeccable + 21st MCP (owner reviews the look),
Phase 9 React + Vite + TS frontend, Phase 10 verification and launch.

**How to pick up the environment**
- Python 3.12 venv in `.venv` (the Mac's default Python 3.15 isn't used): `source .venv/bin/activate`.
- Postgres: `docker compose up -d db` (host port **5434**). The test DB `sldm_test` already exists inside
  that container; if the volume was removed, recreate it with
  `docker exec smart-legal-document-manager-db psql -U postgres -c "CREATE DATABASE sldm_test"`.
- Checks before every commit: `ruff check . && ruff format --check .`, `pytest --cov` (SQLite), and
  `TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5434/sldm_test pytest` (Postgres).
- Commit rules: authored by the owner only; no co-author trailers and no mention of AI tools in
  commit messages or files. Check unpushed messages and tracked files for both before every push.

**Open decisions for the owner:** none pending. Known limits are listed in ADR 0001 and PLAN.md §7.

## 012 — 2026-11-23 — Phase 6: notification inbox and activity log

**Resumed from LOG 011.** Checked first: `main` = `origin/main` = `8842701`, CI green, Docker 29.2.0 up,
Postgres container running, `sldm_test` exists, `.venv` Python 3.12.16, baseline 241 passed + 1 skipped.

**Changed**
- Models: `ActivityEvent` (document_id ON DELETE CASCADE, actor_id, action, `details` JSON/JSONB, created_at;
  index `(document_id, created_at)`; `before_update` / `before_delete` listeners raise `PermissionError`,
  so it's append-only) and `Notification` (user_id CASCADE, document_id **SET NULL**, actor_id, kind CHECK,
  message, version_number, read_at; indexes `(user_id, created_at)`, `(user_id, read_at)`).
- `app/services/activity.py` (`record`, `list_activity`) and `app/services/notifications.py` (`notify`,
  `other_member_ids`, list / unread count / mark read / mark all). Both only *add* rows; the action's own
  commit saves them, so failed actions leave nothing behind.
- Recorded in: create (incl. upload source and file name), new version / restore (`meaningful`, note,
  source, restored_from), soft delete, rename (from → to; no-op renames aren't recorded), member
  added / role changed (no-op changes aren't recorded) / removed (`left` when self).
- Notifications: meaningful version → other members; shared / role changed / removed (not on leaving) →
  that member; document deleted → other members (survives via SET NULL).
- Removed `app/notifications/notification_service.py` (log-only) and the `BackgroundTasks` plumbing;
  `respond_to_version_result` is now just the 200/201 decision.
- Endpoints: `GET /documents/{id}/activity` (viewer+, paginated), `GET /notifications` (`unread_only`,
  paginated, with `unread`), `GET /notifications/unread-count`, `POST /notifications/{id}/read` (idempotent;
  someone else's → 404), `POST /notifications/read-all`.
- Migration `0006`: both tables + backfill of `document.created`, `version.created` / `version.restored`
  and `version.deleted` from existing rows (`"backfilled": true`). Membership history before this phase
  wasn't recorded and can't be reconstructed.
- **Bug found by a new test:** SQLite returned naive timestamps (`…798459`, no `Z`) while freshly written
  values serialized as `…798459Z`. Browsers read naive ISO times as local time. New `UTCDateTime` column
  type (all 9 timestamp columns) always returns aware UTC and refuses naive input; test checks every
  timestamp the API returns carries a zone. No schema change (`alembic check` clean).
- Docs: README "Notifications and Activity Log", schema rows, endpoint rows; USER_GUIDE section 9.

**Tests:** written first and run red (`ImportError: cannot import name 'ActivityEvent'`). The two original
tests that read the server log (`test_trivial_change_…`, `test_meaningful_change_…`) now check another
member's inbox instead; same intent (trivial edits are quiet, real ones notify). New file
`tests/test_activity_and_notifications.py` (25 tests).

**Mutation testing (13)** — all caught in the end:
- "leaving notifies" survived at first: my test looked at the owner's inbox, but a leave notification would
  go to the person leaving. Fixed the test to check the leaver's inbox.
- "no flush before delete" survived on SQLite **and** Postgres: the flush I added was unnecessary (the unit
  of work already inserts notifications before deleting the document). Removed the line.
- Caught: editor notifies themselves, whitespace edits notify, restore logged as create, append-only guard
  off, marking others' notifications, unread filter ignored, re-read overwrites `read_at`, naive timestamps
  returned, version delete not logged, document delete notifies nobody.

**Verified**
| Check | Result |
|---|---|
| `pytest --cov` (SQLite) | **265 passed, 1 skipped**, coverage **98%** |
| Full suite on Postgres 16 | **266 passed** |
| Migration 0006 with a seeded legacy document (v2 by another user and soft-deleted, v3 restored), SQLite and Postgres | 4 backfilled events with the right actors: `document.created` Ann, `version.created` Ben, `version.deleted` Ann, `version.restored` Ann (restored_from 1); downgrade → upgrade → `alembic check` clean. (My first Postgres seed failed on an untyped `NULL` in a `UNION`; re-seeded with separate inserts.) |
| Whole USER_GUIDE on a live server | Alice: 3 unread ("Bob saved version 2/3/4 of “Service Agreement”."), read-all → `{"updated": 3}`, activity 5 events. Running it showed my guide text named the wrong person for the restore; corrected. |
| `ruff check` / `ruff format --check` | clean |

**Next: Phase 7 — hardening & ops** (PLAN.md §7): R4 proxy IPs for the login rate limit, R5 CPU time limit
for file parsing, R8 security headers, request IDs + JSON logs, `/health` checks the DB, seed script with
demo data, docker-compose with the frontend later, CI additions, code review pass.
