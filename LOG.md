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

## 013 — 2026-11-23 — Agent skills studied; record corrected; Phase 7 spec drafted

**Owner asked:** go through the agent skills carefully, use the correct ones for this project, then
start Phase 7.

**Read in full:**
- All 26 `SKILL.md` files of the agent-skills plugin (v0.6.17).
- The reference checklists `definition-of-done`, `orchestration-patterns`, `security-checklist` and
  `observability-checklist`.
- The 5 agent definitions (`code-reviewer`, `security-auditor`, `test-engineer`,
  `accessibility-auditor`, `web-performance-auditor`).

**Correction to the record:** `PLAN.md` §8 listed skills as used in Phases 0–6 that were never
loaded. Only five were loaded and followed: `using-agent-skills`, `git-workflow-and-versioning`,
`security-and-hardening`, `test-driven-development` and `code-review-and-quality`. §8 now has the
accurate table and a forward map of which skill governs which remaining work. Specific gaps it names:
- `interview-me`: Phase 0 asked 4 questions in one batch.
- No spec or approval gate per phase.
- Library behavior was verified from installed source rather than cited official docs.
- The evidence of the Phase 4 flaky failure was not preserved.
- No doubt-driven fresh-context reviews were run.

**How Phase 7 starts as a result:** spec-driven-development requires a written spec approved by the
owner before any code, and says to stop after writing it. Drafted
`docs/specs/phase-7-hardening.md` (delta spec). It contains:
- Objective, current behavior, assumptions.
- 14 tasks in 5 slices, each with acceptance criteria, a verification step and files.
- Checkpoints, proposed `CONSTRAINTS.md`, an out-of-scope list and 3 open questions.

Gaps the skills exposed that are now Phase 7 tasks:
- No rules file and no written quality bar (context-engineering, constraint-driven-development).
- No external CI checks (pip-audit, gitleaks).
- JWT without `iss`/`aud` (security checklist).
- No on-call questions, request IDs or RED metrics (observability).
- API naming and retry-safety never decided (api-and-interface-design).
- No changelog (documentation-and-adrs).
- No performance baseline (performance-optimization).

**Environment facts checked:** `gemini`, `codex`, `gitleaks`, `osv-scanner`, `semgrep`, `mypy` are not
installed. So cross-model doubt reviews can only be manual, and the scanners will run in CI.

**Slip caught before it shipped:** while writing the coverage ratchet I typed "97.92%" before reading
the measurement. The measured value is **98.07%** (`coverage json`, 265 passed + 1 skipped). Corrected
in the spec before saving this entry.

**Status:** spec awaiting owner approval. No code changed. Docs changes (PLAN §8, spec, this entry) uncommitted.

**Approved:** owner approved the Phase 7 spec on 2026-11-23. The spec already holds the plan and task
list (14 tasks with acceptance criteria, verification and files, plus checkpoints), so it serves as the
planning-and-task-breakdown output. Open questions 1 (CI DB password stays) and 3 (`prometheus-client`)
follow the spec's proposals; question 2 (account deletion/export) will be asked at the Slice A+B checkpoint.

## 014 — 2026-11-24 — Phase 7 Slices A–D (T1–T11)

Spec: `docs/specs/phase-7-hardening.md` (approved 2026-11-23). This entry records what was done,
what was measured and where the work differed from the spec.

**Commits:**

| Task | Commit | What |
|---|---|---|
| T1 | `d02e183` | `AGENTS.md`, `CONSTRAINTS.md`, `.constraintsignore`, `scripts/floor_guard.py` and its tests |
| T2 | `2f459d5` | CI `security` job: pip-audit 2.10.1, gitleaks v8.28.0 (redacted), floor guard; Dependabot |
| T3, T4 | `bf1c4da` | Security headers (R8); `FORWARDED_ALLOW_IPS`, `--proxy-headers`, no `Server` header (R4) |
| T5 | `6478e67` | JWT `iss` and `aud` required and checked |
| T1 fix | `2987d0c` | Floor guard: an edited assertion is not a removed one (count-based) |
| T7 | `51320a6` | Request IDs, one JSON access line per request, named events, `request_id` in error bodies |
| T8 | `3af903c` | `/health/live`, `/health/ready` (`SELECT 1`, 503), `/metrics` (RED, bounded labels) |
| T9 | `c6cd9de` | ADR 0002 (API contract, retry safety); README endpoint table checked against OpenAPI |
| T1 fix | `2bc0823` | Floor guard: one suppression line may cite an exception row (`[W3]`) |
| T6 | `217001f` | PDF/DOCX parsing in a confined worker process (R5) |
| T10 | `7a31e86` | `scripts/seed.py` demo data, README section |
| T11 | `df64fa3` | `scripts/bench.py`, `PERF.md` baseline |

**Deviations from the spec, and why:**
- T2: the CI failure cases (a vulnerable pin, a planted secret, a removed assertion) were proven
  locally with the same commands, not on a throwaway branch, so no planted secret was ever pushed.
- T2: the official gitleaks action (v3) has no redaction setting, so CI runs the pinned CLI
  container with `--redact`.
- T4: the uvicorn docs were unreachable (DNS failure, then 503). Proxy-header behavior was read in
  the installed uvicorn 0.54 source instead.
- T5: breaking "alg=none allowed" survived. It is an equivalent mutant: PyJWT refuses `alg=none`
  whenever a key is supplied. The test stays, as documentation of the rule.
- T6: the spec says "a timeout returns 422". Added: `503 busy` when all 4 parse slots stay taken
  for 5 s (the server, not the file, is the problem). Three adversarial review cycles instead of one.
- T6: the page-limit upload test uses a real 501-page PDF; patching the limit in the test process
  can't reach the worker.
- T1: the floor guard flagged documentation and its own `noqa` lines. Pattern rules now apply to
  code files only, and a suppression line may cite an exception row; rows W3–W5 were added.
- T6 coverage: moving the parsers into a subprocess dropped measured coverage to 92%, because
  coverage can't see a process that may not write files and exits with `os._exit`. The floor was
  not lowered: `tests/test_parse_worker.py` tests the worker's functions in-process, and five more
  tests cover the new runner branches. Coverage is back to 97.92% (floor 97.5%).

**Deliberate breaks (each guard broken once; the suite must fail):**

| Task | Breaks | Result |
|---|---|---|
| T1 | skips not detected; min direction inverted; cannot-run reads as clean; any exception row accepted | 4/4 caught |
| T3, T4 | HSTS outside production; API gets the docs CSP; no `no-store`; production trusts every proxy; middleware removed | 5/5 caught |
| T5 | expiry, token type, issuer, audience unchecked | 4/4 caught; `alg=none` equivalent (above) |
| T7 | incoming ID not validated; incoming ID ignored; ID not echoed; unhandled error not answered; raw paths as routes; user id missing from access line; ID missing from error body | 7/7 caught |
| T8 | unknown methods as labels (**survived**; test added, then caught); raw status codes; scrapes counted; token ignored; readiness skips the DB; metrics never recorded | 6/6 after the new test |
| T6 | no concurrency cap; reply size uncapped (**survived**, see below); no deadline; truncated reply accepted; server env leaks; worker runs in server cwd; worker's children survive; pages unchecked; worker text reaches users; worker imports from its cwd; oversized header accepted; reply decoded outside the slot; waiting reply dropped at deadline; worker may fork; worker may write files; surrogates crash the reply | 16/16 after the fix |
| T10 | seed runs in production; seed not idempotent | 2/2 caught |

- "Reply size uncapped" survived because the test matched `"too long"`, which the deadline's
  message ("took too long") also contains. Both tests now match their exact message, and the flood
  test has a 3 s deadline: uncapped, it first ran the test process out of memory (exit 137).
- From this entry on, breaks run in a throwaway copy of the repository in the scratchpad. A script
  applies each break to the copy, runs the tests there and hashes the real files before and after.
  The reason: an in-place run interrupted on 2026-11-24 left one break (`cwd="/"` removed) in
  `extract.py`. It was found by comparing with the backup, restored, and the tests rerun.

**T6 review cycles (doubt-driven-development).** Each cycle gave a fresh-context reviewer only the
code and the contract. The owner skipped the cross-model option in cycles 1 and 2. After cycle 3
the owner asked to stop the review cycle, and I triaged cycle 3 myself.

Cycle 1 (first design used `multiprocessing`):

| # | Finding | Class |
|---|---|---|
| 1 | Unbounded reply can exhaust server memory; no memory limit on macOS | Actionable |
| 2 | A crash mid-reply raises `OSError`; start-up failures escape as 500 | Actionable |
| 3 | A failed start can leak file descriptors and a zombie | Actionable |
| 4 | multiprocessing's resource-tracker process stays | Contract misread (no *per-request* child was meant) |
| 5 | Threads reaping each other's children could kill a reused PID | Actionable |
| 6 | `exc.message` might not exist | Noise (`AppError` sets it) |
| 7 | Start-up time not counted against the timeout | Actionable |
| 8 | Server unpickles the child's reply; child inherits `SECRET_KEY` and `DATABASE_URL` | Actionable, security |
| 9 | Child imports FastAPI and the app, using its memory allowance | Actionable |
| 10 | No cap on concurrent parsers | Actionable |
| 11 | Spawn re-runs `__main__`; daemon callers fail | Actionable (removed by the redesign) |

Response: a plain subprocess (file on stdin; JSON header and text on stdout; no pickle), a scrubbed
environment, a worker module that imports nothing from the app, reason codes mapped to the server's
own messages, a byte-capped read with one deadline, `with Popen`, and a 4-slot semaphore.

Cycle 2:

| # | Finding | Class and response |
|---|---|---|
| 1 | Waiting for a slot eats the parse deadline | Actionable: separate 5 s slot wait (503); the deadline starts after it |
| 2a | No framing, so a truncated reply counts as success | Actionable: the header carries the body `length` |
| 2b | A worker that can't start looks like a bad file | Trade-off: indistinguishable from outside; start-up is proven by tests on every platform we run |
| 3 | Malformed replies cause 500s | Actionable |
| 4 | Thread, selector and subprocess failures escape as 500 | Actionable: all map to 503 |
| 5 | Cap counted in characters, not bytes | Actionable: bytes on both sides |
| 6 | Slot waiters hold Starlette's shared thread pool | Partly fixed (short wait); trade-off recorded |
| 7 | A compromised parser has the server's privileges | Actionable parts: own process group, NPROC 0, FSIZE 0, CORE 0, NOFILE 64, `cwd="/"`. Trade-off: same uid, so the parent's `/proc` entry is readable. Partly a contract misread: the container runs as non-root `appuser` |
| 8 | Package `__init__` files might load secrets | Noise: both are empty |
| 9 | Four 1 GiB workers can trigger the OOM killer | Actionable: `oom_score_adj` 1000. Trade-off: no memory limit on macOS |
| 10 | Slow interpreter exit can lose a complete reply | Actionable: stop reading once complete; the worker calls `os._exit` |
| 11 | Float `cpu_seconds`, `ValueError` in the writer, lone surrogates | Actionable (small) |

Cycle 3:

| # | Finding | Class and response |
|---|---|---|
| 1 | Server memory pressure or CPU contention shows as 422 "damaged" | Trade-off: an OOM kill and the CPU-limit kill look the same from outside. Container sizing (about 4 GiB plus the API) documented in the README |
| 2 | Reply decoded after the slot is released, so 4 slots don't bound memory | Actionable: decoded inside the slot |
| 3 | A malformed header is re-parsed on every chunk while holding the GIL | Actionable: header capped at 4 KB and rejected at once |
| 4 | `BrokenPipeError` from `Popen.__exit__` replaces the result | Actionable: the writer is joined before stdin is closed. The race did not reproduce on macOS in 5 tries, so its test passed before the fix too; kept as a guard |
| 5 | A reply already waiting at the deadline is dropped | Actionable: one last non-blocking read, capped at 1 MiB |
| 6 | `MemoryError` while decoding is a 500; bad internal arguments | `MemoryError` actionable (now 503); arguments noise (internal constants) |
| 7 | `python -m` puts `/` first on the import path; `__init__` files run first | Path actionable (`-P`); `__init__` noise (both empty) |

Cycle-3 fixes were written test-first: 5 of the 6 new tests failed before the fix (#4 above is the
exception).

**Known trade-offs carried forward:**
- The worker runs as the server's uid.
- No memory limit on macOS (development only).
- Parse waits share Starlette's thread pool.
- The slot limit is per server process (N uvicorn workers = N×4 parsers).
- Upload p95 is over budget because worker start-up plus a 1-page parse takes about 0.215 s in the
  Linux container (`PERF.md`).

**Verification (2026-11-24, final tree):**
- `ruff check . && ruff format --check .`: clean.
- `pytest --cov`: 415 passed, 1 skipped; coverage 97.92%.
- Postgres (`TEST_DATABASE_URL=… pytest`): 416 passed.
- `python scripts/floor_guard.py --base origin/main`: clean (W3–W5 reported for review).
- Linux, `python:3.12-slim` as uid 10001 (real 1 GiB address-space limit), parse, worker and
  upload tests: 104 passed.
- `seed.run()` twice: counts unchanged on the second run (`tests/test_seed.py`).

**Status:** Slices A–D done (T1–T11). Next: checkpoint (push, CI green, owner question 2), then T12
(changelog and README structure), T13 (reviews) and T14 (simplification).

## 015 — 2026-11-24 — Phase 7 T15: account deletion and data export

**Owner decisions:**
- Open question 2 answered "add now".
- Spec addendum T15 (`docs/specs/phase-7-hardening.md`) approved as written, including migration
  `0007`. Names already written into past activity details and other people's notifications are
  kept (option "also scrub old names" not chosen).

**Design found in the code, before writing the spec:**
- `documents.created_by`, `document_versions.edited_by` and `activity_events.actor_id` reference
  `users.id` with no cascade, and the activity log is append-only. So deletion anonymizes the
  account row instead of removing it.
- A document can have several owners, so the refusal is "last owner of a document other members
  still use".
- Unexpired tokens would keep working without a marker, hence `users.deleted_at`.

**Corrections made while implementing (spec updated to match):**
- The placeholder email `…@deleted.invalid` fails pydantic's `EmailStr` (special-use domain),
  which would turn any response showing it into a 500. It is `deleted-user-<id>@deleted.example`
  (RFC 2606 reserved, never delivers).
- The spec said a wrong password returns `permission_denied`; the project's 403 code is
  `forbidden`.
- Two of my test expectations were wrong (that error code, and version order, which is oldest
  first); the code was right.

**What was built:**
- `GET /api/auth/me/export`: a JSON download (`Content-Disposition: attachment`, `no-store`) with
  profile, memberships, versions authored (with content), activity and notifications. Document
  data is limited to documents the user can still access.
- `DELETE /api/auth/me` with `{"password"}`:
  - The password is checked again, with its own key on the sign-in limiter.
  - 409 with `details.documents` when the user is the last owner of a shared document.
  - Otherwise, in one transaction: sole-member documents deleted, other documents left (a
    `member.removed` event with `left: true` and the placeholder name), own notifications deleted,
    and name, email and password replaced.
  - 204 and the cookie cleared; an `account_deleted` log event with `user_id` and counts only.
- `get_current_user` refuses a deleted account's tokens (401). `authenticate` also refuses
  deleted accounts, as a second lock.
- Files: `app/services/account.py`, `app/schemas/account.py`, `app/api/routes/auth.py`,
  `app/api/deps.py`, `app/services/users.py`, `app/db/models.py`,
  `migrations/versions/20261124_0007_user_deleted_at.py`, `tests/test_account.py` (20 tests), one
  retry test, README, `USER_GUIDE.md` §11, and the ADR 0002 retry table (`DELETE /auth/me` → 401).

**Tests first:** all 19 initial tests failed before the code existed. The 20th test was added for a
surviving break (below).

**Deliberate breaks (run in the throwaway copy; real files hashed before and after):** 16 breaks:
- last owner not protected; co-owner blocked;
- sole-member documents kept; memberships kept; notifications kept;
- name, email or password kept;
- export leaks versions, activity, or other inboxes;
- deleted account tokens work;
- sign-in second lock removed;
- password not checked; no rate limit; export not a download.

15 of 16 were caught. "Sign-in second lock removed" survived: the stored password is random, so
nothing reaches that line over HTTP. A test now restores a known hash on a deleted account (as a
restored backup might) and expects 401; the break is caught.

**Verification:**
- `ruff check . && ruff format --check .`: clean.
- `pytest --cov`: 436 passed, 1 skipped; coverage 98.07%.
- Postgres: 437 passed.
- Migration on Postgres and SQLite: upgrade, downgrade base, upgrade, `alembic check` ("No new
  upgrade operations detected"), downgrade base.
- `python scripts/floor_guard.py --base origin/main`: clean.
- Live, on the rebuilt Docker stack (migration 0007 applied on start), following `USER_GUIDE.md`
  §11:
  - export: 200 with the attachment header and `no-store`, all seven sections;
  - wrong password 403, delete 204, then `/auth/me` 401 and sign-in 401;
  - the `account_deleted` log line carries only `request_id`, `user_id` and counts.

**Status:** T15 done. Next: T12 (changelog, README structure), T13 (review), T14 (simplification).

## 016 — 2026-11-24 — Phase 7 T12: changelog and README structure

**What changed:**
- `CHANGELOG.md` (new, Keep a Changelog): everything since the original 2026-03-17 submission,
  under Breaking, Added, Changed, Fixed and Security. Each entry traces to a commit body or to a
  defect ID (B1–B16 in `PLAN.md` §4) or review finding (R1–R8, LOG 009). It is "Unreleased"
  (the API reports `0.2.0`): tagging a release is a separate decision.
- `README.md` restructured:
  - Overview and Features rewritten.
  - Quick start, Architecture (with the ADR links) and Commands added.
  - Operations added: health checks, logs and events, metrics, a table of every environment
    variable, deployment notes.
  - The feature sections (data model, auth, endpoints, comparison, search, upload, notifications)
    were kept, with `users.deleted_at` added to the data model.

**Found in the old README:**
- "System Architecture" and "Project Structure" still described `app/routers/`, `app/database/`
  and `app/notifications/`, none of which exist since Phase 1.
- "Features" listed "Background processing", replaced by same-transaction notifications in Phase 6.
- The Postgres test command used `sldm_test`, but nothing created that database. On a clean clone
  the suite can't connect. The Commands table now has the `createdb` step.

Event names, metric names and environment-variable defaults were copied from the code
(`log_event` calls, `app/core/metrics.py`, `app/core/config.py`), not written from memory.

**Verification: every README command on a clean clone.**

Setup:
- `git clone` of this repository into the scratchpad, plus the two changed files.
- The folder name differs (`sldm-clean-clone`), so Docker made a separate project and a fresh
  database volume.
- The README's fixed container names meant the dev containers had to be removed first
  (`docker compose down`, without `-v`). The dev volume was untouched, and the dev database was
  restored afterwards (8 users, 637 documents, `sldm_test` present).

| Command | Result |
|---|---|
| `docker compose up --build -d` | `/api/health/ready` → `{"status":"ok","database":"ok"}` |
| `docker compose exec api python -m scripts.seed` | demo data created; `/api/docs` 200; demo sign-in 200 |
| Set up (venv, `pip install -r requirements-dev.txt`, `cp .env.example .env`) | ok, Python 3.12.16 |
| `docker compose up -d db` / `alembic upgrade head` | running / at `20261124_0007` (head) |
| `python -m scripts.seed` | "Demo data already present; nothing changed." |
| `ruff check . && ruff format --check .` | clean, 86 files |
| `pytest --cov` | 436 passed, 1 skipped, 98% |
| Postgres tests before `createdb` | connection failure (the gap above) |
| `docker compose exec db createdb -U postgres sldm_test`, then the Postgres tests | 437 passed |
| `python scripts/floor_guard.py --base origin/main` | clean |
| `uvicorn app.main:app --reload` | ready |
| `python -m scripts.bench --base http://localhost:8000` | completed and printed its table (not added to `PERF.md`: local macOS uvicorn, not the Docker baseline) |
| `docker compose down -v` | removed the clone's containers, network and volume only |

**Status:** T12 done. Next: T13 (review) and T14 (simplification); then the owner reviews the
finished backend.

## 017 — 2026-11-24 — Phase 7 T13: backend review and fixes

**How the review was done (deviation from the spec):**
- The spec named three fresh-context agents (security-auditor, code-reviewer, test-engineer).
  The owner asked to stop agent review cycles (LOG 014), and chose "Start T13 myself".
- I reviewed on `f49af7e`, with the checkout clean and matching `origin/main`. Every file in
  `app/` was read, plus CI, using the code-review-and-quality checklist and the security
  checklist (all five axes).
- Suspected defects were confirmed by experiment before they were classified: timings, and
  probes on both SQLite and PostgreSQL.
- The cross-model second opinion was offered (manual only); the owner chose to fix first.

**Findings:**

| # | Finding | Evidence | Class |
|---|---|---|---|
| H1 | Compare does unbounded quadratic work. difflib with autojunk off is O(n·m) and worse for repetitive regions; any viewer can trigger it. | One line of 61 k characters: 6.67 s. One line of 245 k: still running after 90 s. 448 k characters of repeated lines: 69 s. A realistic 2.4 M-character contract with scattered edits: 7.45 s. | Actionable, High |
| M1 | Owners could share a document with a deleted account (regression from T15). The placeholder email is predictable, so a "Deleted user" co-owner let the real owner delete their account and leave a document nobody can open. | New test: 201 in every role | Actionable, Medium |
| M2 | NUL in text inputs crashed on PostgreSQL. SQLite stored it, so no test saw it. | Probe: content, title, name, change note, search query and upload title each 500 on Postgres and 2xx on SQLite | Actionable, Medium |
| M3 | Notification text can exceed `String(500)`: name (255) + title (255) + text. Postgres refuses the row, and the action's transaction with it. | Probe: sharing 500 on Postgres; every version save on such a document would fail too | Actionable, Medium |
| M4 | The sign-in limit is per IP+email only, so one IP can spray a password at every account. | Code and ADR 0001 | Actionable, Medium |
| D1 | ADR 0001 said only signed-in owners can learn whether an email is registered; sign-up's 409 tells anyone. | Code | Actionable (doc) |
| T1 | Logout doesn't revoke tokens (12 h) | Already in ADR 0001 | Trade-off, recorded |
| T2 | No per-user quotas; the data export is built in memory, so a user who stores a lot makes a large export | Code | Trade-off, recorded here |
| T3 | No database connect or statement timeout | `app/db/session.py` | Trade-off, recorded here |
| T4 | CORS doesn't expose `X-Request-ID` or `Content-Disposition` to browser code | `app/main.py` | FYI for Phase 9 (the frontend should use a same-origin proxy) |
| T5 | GitHub Actions are pinned by tag, not commit SHA | `ci.yml` | Deferred: CI changes need the owner's approval (`AGENTS.md`) |
| N1 | `# type: ignore` comments with no type checker running | 4 places | Nit, for T14 |
| N2 | The catch-all 500 handler never runs in tests | `errors.py` 113–114 | Noise: a backstop for errors in the outermost middleware |

Checked and clean: SQL injection (parameterized, `LIKE` escaped); IDOR (every document route
resolves membership; notifications are scoped to their owner); secrets in logs; JWT validation;
upload filenames (control characters stripped, 255 maximum).

**Fixes (each test-first; every new test failed before its fix):**
- **M1:** `add_member` treats a deleted account like an unknown email (404). 3 tests, one per
  role.
- **M3:** `notify()` fits messages to the column length read from the model and ends a cut
  message with "…". The test (sharing, a version, a role change, a deletion, with a 255-character
  name and title) also passes on Postgres.
- **M2:** one `NoNul` validator in `app/schemas/common.py`, on title, content, change note, name,
  the search `q` and both upload form fields: 422 `validation_error`. 9 tests, passing on both
  databases.
- **M4:** a second limiter key per IP, `LOGIN_MAX_FAILURES_PER_IP` (default 100 in the same
  15-minute window). A successful sign-in resets only the IP+email key, otherwise an attacker
  could clear the count with their own account. 2 tests.
- **H1:** `app/utils/diff.py` aligns in three steps:
  1. Elements unique on both sides anchor the alignment (longest increasing chain, patience-diff
     style).
  2. Each gap is trimmed at both ends.
  3. The rest is matched exactly while a per-request budget lasts (`MAX_COMPARE_CELLS`, a gap of
     n×m is charged n·m); past it, the gap is one replaced block and the response says
     `approximate: true`.
  - The unified `changes` are built from the same alignment, so difflib isn't run a second time
    without bounds. A test checks the format is identical to `difflib.unified_diff` on 200
    random documents.
  - Blank-line junking was tried first and dropped: the profile showed it moved the cost into
    difflib's recursion (33 M dictionary lookups on the realistic contract).
  - Choosing the budget: a first estimate (30 ns per cell, 20 M cells) still allowed 15 s on a
    dense repetitive gap, because difflib's cost grows faster than n·m there. The budget was
    then set by the worst pattern measured: 0.30 s at 250,000 cells (edits every 2 elements, on
    lines and on words). 200 hostile gaps sharing the budget took 0.11 s.

  | Case | Before | After |
  |---|---|---|
  | Realistic 2.2 M-character contract, 10 scattered edits | 7.45 s | 0.03 s, exact |
  | 448 k characters of repeated lines, scattered edits | 69 s | 0.49 s, approximate |
  | 280 k-character line edited at both ends | over 90 s | 0.08 s, approximate |
  | 280 k-character line, one edit | over 30 s | 0.04 s, exact |
  | 2 M-character single line | — | 0.44 s, exact |

  7 new engine tests and 2 API tests. The existing 300-case reconstruction test and the
  repeated-headings and blank-lines alignment tests pass unchanged.

My own test mistakes, corrected before committing:
- one inserted a word mid-word;
- one checked the rebuild on collapsed rows;
- one required `" amended"` where `"amended "` is equally minimal;
- `# noqa: E402` imports were placed mid-file. They were moved to the top rather than kept as new
  suppressions.

**Deliberate breaks (throwaway copy, real files hashed before and after):** 21 of 21 caught.
- M1 (1): deleted account can be shared.
- M3 (2): message not fitted; off by one.
- M2 (8): the check off, then each guard removed in turn (title, content, change note, name,
  search, upload title, upload change note).
- M4 (3): per-IP failures not counted; limit not checked; a success clears the per-IP count.
- H1 (7):
  - no budget: the two tests ran 7 min 20 s and failed;
  - `approximate` never set; the API hides it;
  - anchors out of order;
  - no head trimming; no tail trimming;
  - equal runs not merged.

**Verification:**
- `ruff check . && ruff format --check .`: clean.
- `pytest --cov`: 458 passed, 1 skipped; coverage 98.21%.
- Postgres: 459 passed.
- Floor guard: clean.

**Docs:** README (comparison method and the `approximate` flag; the new environment variable) and
ADR 0001 (the per-IP limit in the threat model; the corrected enumeration trade-off).

**Status:** T13 done. Next: T14 (simplification), then the owner reviews the finished backend.

## 018 — 2026-11-24 — Phase 7 T14: simplification pass

**How the candidates were chosen:**
- One ruff run over `app/` and `scripts/` with complexity, dead-code and simplification rules
  (`C901`, `PLR09xx`, `SIM`, `RET`, `PIE`, `ERA`, `ARG`, `PERF`, `FURB`, `C4`). The project's
  configuration was not changed.
- A search for suppressions.
- The T13 review notes.

Most signals were noise and were left alone:
- "Too many arguments": keyword-only service parameters with clear names.
- The unused `dialect` argument: required by SQLAlchemy's `TypeDecorator`.
- One `list.extend` suggestion: no clearer.
- Splitting `extract.py`: it would relocate complexity, not reduce it.

**Changes (one commit each; both full suites run after each; no existing test edited):**

| Commit | Change | Why |
|---|---|---|
| `704aa51` | Five `# type: ignore[no-untyped-def]` replaced with real annotations (`Select`, `Row`, `ColumnElement`, `AliasedClass` from `sqlalchemy.orm.util`, the DB-API connection) | No type checker is installed or configured and ruff doesn't check annotations, so the comments suppressed nothing. They stood in for return types (Phases 1, 3, 4). |
| `117b587` | The floor guard's threshold comparison moved to `threshold_verdict()`, which returns early | It replaces two nested loops sharing a `verdict` flag set in one place and checked with `break` in another. `find_violations` complexity: 26 → 19. |
| `343d063` | 2 new floor guard tests: a rule's number dropped (`threshold-removed`); a number with no direction changed (`threshold-changed`) | Breaking either rule had gone unnoticed, before and after the refactor. |
| `6e7b097` | `app/core/errors.py` module docstring shows `request_id` | It showed the error shape from before T7. |

**Behavior kept:**
- The refactor's equivalence was argued first: the old loop also kept the first verdict, and
  every later iteration broke at once.
- All 29 existing floor guard tests passed unchanged.
- The 2 new tests pass against both the old and the new guard.
- Breaks of the extracted helper, in the throwaway copy: removed threshold ignored; directionless
  change ignored; min loosening read as fine; max loosening read as fine. 4 of 4 caught (the first
  two only with the new tests).

**Verification (final tree):**
- `ruff check . && ruff format --check .`: clean.
- `pytest`: 460 passed, 1 skipped.
- Postgres: 461 passed.
- Floor guard: clean.

**Status:** Phase 7 tasks T1–T15 are done. Next: the owner reviews the finished backend
(PLAN.md gate), then Phase 8 (design direction).

## 019 — 2026-11-27 — Backend signed off; Phase 8 begins

**Session start (`AGENTS.md`):**
- The resume point and entry 018 said T1–T15 were done and pushed.
- Git matched: `HEAD` `0799281`, tree clean, in sync with `origin/main`.
- Docker had no containers and no data volume. The owner had run `docker compose down -v` to
  start the demo from an empty database, and that also removed the `sldm_test` database.
- Restored with the README's own commands: `docker compose up -d db`, then
  `docker compose exec db createdb -U postgres sldm_test`.

**Checks:**
- `ruff check . && ruff format --check .`: clean.
- `pytest`: 460 passed, 1 skipped.
- Postgres: 461 passed.
- Floor guard: clean.

These match entry 018.

**Owner review of the backend:**
- After the walkthrough (features, architecture, quality enforcement, the live demo, seven
  recorded trade-offs), the owner tried the demo stack.
- The owner then wrote "Its fine so the backend is completed ?". I answered that the plan's
  sign-off gate was the only open step and asked them to confirm.
- They replied "Now start where we left", which is recorded as the sign-off.
- No trade-off was asked to change. Phase 7 is closed.

**Next:** Phase 8 (design direction). Per PLAN §8:
- interview-me for design intent (one question at a time, with a stated guess);
- then a spec for approval (spec-driven-development);
- impeccable for the direction and `DESIGN.md`; 21st.dev for component candidates;
- the owner approves the look before Phase 9 builds anything.
