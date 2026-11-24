# Spec Delta: Phase 7 — Hardening and operations

Status: approved by owner 2026-11-23 (open questions: 1 and 3 use the proposed defaults; 2 to be asked at the Slice A+B checkpoint)
Source plan: `PLAN.md` §7 Phase 7 · Review items R4, R5, R8 (`LOG.md` 009)
Skills: spec-driven-development, planning-and-task-breakdown, constraint-driven-development,
security-and-hardening, observability-and-instrumentation, ci-cd-and-automation,
api-and-interface-design, documentation-and-adrs, performance-optimization, context-engineering,
doubt-driven-development, code-review-and-quality, code-simplification

## Objective

Make the finished backend safe to deploy and easy to operate and review, before any frontend is
built on it. "Done" means: the quality bar is written down and enforced, the remaining security gaps
are closed, a single request can be traced through the logs, the API contract is decided and
documented, demo data exists, and independent reviewers found nothing critical.

## Current behavior

- Quality bar lives only as prose in `PLAN.md` §6; every check is judged by our own test suite.
- No security headers. JWTs carry no issuer/audience. Login rate limit sees the proxy's IP when
  deployed behind a non-local proxy (R4). PDF/DOCX parsing has no time limit (R5).
- Plain-text logs, no request IDs; `/health` always answers `ok` without checking the database (B15).
- API naming (snake_case), pagination shape and retry-safety were never decided in writing.
- No rules file for future sessions, no changelog, one ADR.

## Assumptions (correct any of these)

1. Deployment target is a single container behind a managed HTTPS proxy (e.g. Render or Fly), plus
   managed Postgres. Phase 10 picks the host.
2. Keep snake_case JSON and query parameters. Changing to camelCase now would touch every endpoint
   and test; the frontend can map. Recorded in ADR 0002.
3. Metrics are exposed in Prometheus format at `/metrics` (a new dependency, `prometheus-client`),
   but dashboards, alerting and tracing wait until there is a deployed environment.
4. Rules file is `AGENTS.md`, a tool-neutral name. Tracked files must not name AI tools (owner rule).

## Tasks

Each task: implement → test → verify → commit (incremental-implementation). Tests are written first
where behavior changes (test-driven-development). Framework-specific code cites official docs
(source-driven-development).

### Slice A — Foundations

**T1. Rules file and written quality bar** · context-engineering, constraint-driven-development
- Acceptance:
  - `AGENTS.md` has the stack, commands, conventions, boundaries and the commit rules.
  - `CONSTRAINTS.md` has the floor plus the numbered dimensions under *Proposed constraints* below;
    every row names the command that checks it.
  - Floor guard script (adapted from the skill's reference) fails on a diff that adds `# noqa`,
    `# type: ignore`, `pytest.skip`, or removes an assertion.
- Verify:
  - The floor guard is run against a deliberate violation (fails) and the clean tree (passes).
  - Every command in `CONSTRAINTS.md` runs today.
- Files: `AGENTS.md`, `CONSTRAINTS.md`, `scripts/floor_guard.py`

**T2. CI gates with an external opinion** · ci-cd-and-automation, security-and-hardening
- Acceptance:
  - CI adds dependency audit (`pip-audit`), secret scan (`gitleaks`) and the floor guard.
  - `.github/dependabot.yml` covers pip and GitHub Actions.
- Verify:
  - Each new gate is shown failing on a deliberate violation in a throwaway branch, then passing on main.
- Files: `.github/workflows/ci.yml`, `.github/dependabot.yml`

### Slice B — Security (R4, R5, R8 + checklist gaps)

**T3. Security headers (R8)**
- Acceptance:
  - Every response has the following headers:
    - `X-Content-Type-Options: nosniff`
    - `X-Frame-Options: DENY`
    - `Referrer-Policy: strict-origin-when-cross-origin`
    - `Permissions-Policy: camera=(), microphone=(), geolocation=()`
    - A restrictive `Content-Security-Policy` (relaxed only on `/api/docs` for its assets)
  - `Strict-Transport-Security` is sent only in production.
- Verify: tests per header; the docs page still loads in the browser pane with no console CSP errors.
- Files: `app/core/headers.py`, `app/main.py`, `tests/test_security_headers.py`

**T4. Real client IPs behind a proxy (R4)**
- Acceptance:
  - The container runs uvicorn with proxy headers trusted only from `FORWARDED_ALLOW_IPS`.
  - Login rate-limit keys use the forwarded client IP.
  - It is documented which value to set per host.
- Verify:
  - Test: two different `X-Forwarded-For` clients from a trusted proxy get separate limits.
  - Spoofed `X-Forwarded-For` from an untrusted peer is ignored.
- Files: `Dockerfile`, `app/core/config.py`, `README.md`, tests

**T5. JWT issuer and audience**
- Acceptance: tokens carry `iss`/`aud`, and decode rejects a token without them or with wrong values.
- Verify: tests for wrong `iss`, wrong `aud`, and missing claims.
- Files: `app/core/security.py`, `tests/test_auth.py`

**T6. Time-limited file parsing (R5)** · doubt-driven review required (process lifecycle)
- Acceptance:
  - PDF/DOCX extraction runs in a separate process with a CPU-time and wall-clock limit (default
    20 s). A timeout returns 422 `unreadable_file` and the worker process is gone afterwards.
- Verify:
  - Test with a deliberately slow parser stub: 422 within the limit, no leftover process.
  - Existing upload tests still pass.
- Files: `app/utils/extract.py`, `app/api/routes/uploads.py`, `tests/test_upload.py`

### Slice C — Observability (B15)

**On-call questions this slice must answer** (observability skill, step 1):
1. Is the API up, and can it reach the database?
2. Why did this specific user's request fail? (from the request ID they see in the error)
3. Which endpoints are slow or failing, and since when?
4. Are people being locked out by the login rate limit, or are uploads being refused, and why?

**T7. Request IDs and structured JSON logs**
- Acceptance:
  - Every request gets an `X-Request-ID` (accepted if it's a valid UUID, else generated). It is
    echoed in the response header and in every error body (`error.request_id`).
  - One JSON access-log line per request with fields `event`, `request_id`, `method`,
    `route` (template, not raw path), `status`, `duration_ms` and `user_id` when known.
  - Domain events are logged with stable names:
    - `login_failed`, `login_rate_limited`
    - `upload_rejected` (with reason code)
    - `version_conflict`
    - `unhandled_error`
  - No tokens, passwords, emails or bodies are ever logged.
- Verify:
  - Tests read captured log records.
  - A forced 500 is found in the logs by its request ID alone.
  - Real output is spot-checked for secrets.
- Files: `app/core/logging.py`, `app/core/errors.py`, `app/main.py`, tests

**T8. Health checks and RED metrics**
- Acceptance:
  - `/api/health/live` always 200.
  - `/api/health/ready` returns 200 when `SELECT 1` succeeds and 503 when it doesn't.
    `/api/health` stays as an alias of `ready`.
  - `/metrics` exposes the request counter and a latency histogram labelled by `method`, route
    template and status class only (bounded labels).
- Verify:
  - Readiness tested with the database stopped (503) and running (200).
  - Metric labels checked for no raw paths or IDs.
- Files: `app/api/routes/health.py`, `app/core/metrics.py`, `requirements.txt`, tests

### Slice D — Contract, data, documentation

**T9. API contract decisions (ADR 0002)** · api-and-interface-design, documentation-and-adrs
- Acceptance: ADR 0002 records the following, and the README links it:
  - snake_case naming.
  - The `{items,total,limit,offset}` pagination shape.
  - The error format.
  - Status-code meanings.
  - Retry safety per state-changing endpoint: version saves are safe to retry (identical content is
    a no-op); document create, share and upload are **not** safe to retry. Idempotency keys are deferred.
- Verify: every endpoint in the README table matches the ADR (checked by script against the OpenAPI schema).
- Files: `docs/adr/0002-api-contract.md`, `README.md`

**T10. Demo seed data**
- Acceptance:
  - `python -m scripts.seed` creates 3 demo users and 4 realistic contracts, with several versions
    each, a restore, a soft delete, sharing across roles, and resulting activity and notifications.
  - Re-running it is safe (no duplicates).
  - It refuses to run when `ENVIRONMENT=production`.
- Verify: run twice on a fresh database; counts unchanged on the second run; the API shows the data.
- Files: `scripts/seed.py`, `README.md`

**T11. Performance baseline (measure only)** · performance-optimization
- Acceptance: p50/p95 for list, search, compare and upload on the seeded database, plus
  `EXPLAIN ANALYZE` for search, recorded in `PERF.md`. No optimization unless p95 > 200 ms.
- Verify: the numbers come from a repeatable script (`scripts/bench.py`), run 3 times.
- Files: `scripts/bench.py`, `PERF.md`

**T12. Changelog and README structure** · documentation-and-adrs
- Acceptance:
  - `CHANGELOG.md` covers everything since the original code, grouped Added/Changed/Fixed/Security.
  - README has Quick start, Commands, Architecture (with links to ADRs) and Operations (health,
    logs, metrics, environment variables).
- Verify: every command in the README run on a clean clone.
- Files: `CHANGELOG.md`, `README.md`

### Slice E — Independent review (gate)

**T13. Reviews by fresh-context agents** · code-review-and-quality, doubt-driven-development
- Agents: `security-auditor`, `code-reviewer`, `test-engineer`, run in parallel on the whole backend
  (fan-out with merge).
- Acceptance: every finding is classified (actionable / trade-off / noise) against the code, not
  rubber-stamped. No Critical or High left open; trade-offs are written down.
- Verify: each fix gets a regression test; the deliberate-break checks run on every fix.
- A cross-model second opinion is offered at this point (manual only: no Gemini/Codex CLI is installed).

**T14. Simplification pass** · code-simplification
- Acceptance: only code changed in Phases 1–7. Behavior is identical and no tests are edited.
  One change per commit.
- Verify: full suite on SQLite and Postgres after each change.

### Addendum — T15 (owner answered open question 2 on 2026-11-24: add now)

Status: approved by owner 2026-11-24 as written (including migration `0007`).

**T15. Account deletion and data export** · security-and-hardening, api-and-interface-design,
test-driven-development

Why: security-and-hardening asks for a working path to delete and export personal data.

Constraint found in the code: documents, versions and activity events point at `users.id` with no
cascade, and the activity log is append-only by design (legal audit trail). So deleting an account
means **anonymizing** it: the row stays as a placeholder so history still resolves, and everything
that identifies the person is removed from it.

`GET /api/auth/me/export` (signed in)
- 200 JSON, sent as a download (`Content-Disposition: attachment`), `Cache-Control: no-store`.
- Contains:
  - `profile`: id, name, email, created_at.
  - `memberships`: document id, title, role, added_at.
  - `versions_authored`: every version you wrote, with its content.
  - `activity`: events you performed.
  - `notifications`: your inbox.
- Scope: only documents you can still access. A document you were removed from belongs to its
  owners; your profile and notifications are always included.

`DELETE /api/auth/me` with body `{"password": "..."}`
- The password is checked again. A stolen session alone can't delete the account.
  - Wrong password: 403 `forbidden` (the project's existing code for refused actions).
  - Repeated failures: 429 `rate_limited`, using the existing login limiter.
- Refused with 409 `conflict` if you are the **last owner** of a document that other members still
  use. Nothing changes; the response lists those documents, so you can make someone else an owner
  or delete them first.
- Otherwise, in one transaction:
  1. Documents where you are the only member are deleted (as `DELETE /documents/{id}` does).
  2. You leave every other document. A `member.removed` event is recorded with `left: true`.
  3. Your notifications are deleted.
  4. The account is anonymized:
     - name becomes "Deleted user";
     - email becomes `deleted-user-<id>@deleted.example`, so the address can sign up again
       (`.example` is reserved by RFC 2606; `.invalid` fails pydantic's `EmailStr`, found while
       implementing);
     - the password hash becomes unusable;
     - `deleted_at` is set.
  5. 204, the auth cookie is cleared, and an `account_deleted` log event is written.
- Afterwards every existing token for the account gets 401, and sign-in fails.

Schema change (needs owner approval per `AGENTS.md`):
- Migration `0007` adds a nullable `users.deleted_at` column (additive, with a tested downgrade).
- Without it, an unexpired token of a deleted account would keep working.

Kept on purpose (trade-off, written down):
- Names already written into the past are left as they are:
  - activity `details` (member events store the affected member's name);
  - the text of other people's notifications (e.g. "Asha shared X with you").
- Rewriting them would mean editing the append-only audit trail and other people's inboxes.
- Everywhere a name is looked up live (version authors, activity actors, owner names), the
  placeholder shows "Deleted user".

Acceptance:
- Export contains exactly the listed sections for the signed-in user and nothing from other users'
  inboxes or from documents the user can no longer access.
- Deletion: each step above, the 403/409/429 cases, tokens refused afterwards, the same email can
  register again, other members' documents and history intact.

Verify:
- Tests first for every rule above, on SQLite and Postgres.
- Migration upgrade, downgrade and upgrade with no drift.
- Deliberate breaks of each guard, run in a throwaway copy.
- README endpoint table (checked against OpenAPI) and ADR 0002 retry table updated.

Files: `app/api/routes/auth.py`, `app/services/users.py` (or a new `app/services/account.py`),
`app/api/deps.py`, `app/db/models.py`, `migrations/versions/20261124_0007_user_deleted_at.py`,
`app/schemas/user.py`, tests, `README.md`, `USER_GUIDE.md`, `docs/adr/0002-api-contract.md`.

### Checkpoints

- After Slice A+B: full suite on both databases, CI green, commit and push.
- After Slice C+D: same, plus the seeded demo and observability checks run live.
- After Slice E: **owner reviews the finished backend** (PLAN.md gate) before Phase 8.

## Proposed constraints (`CONSTRAINTS.md`)

Defaults from constraint-driven-development; "measure and hold" where no number is agreed.

| Dimension | Rule | Checked by | Runs at |
|---|---|---|---|
| Floor | No new suppressions (`noqa`, `type: ignore`), skipped or deleted tests, stripped assertions, stubs or secrets | `scripts/floor_guard.py` on the diff | before commit, CI |
| Lint | Zero ruff errors, formatted | `ruff check . && ruff format --check .` | before commit, CI |
| Tests | All pass on SQLite and Postgres | `pytest` and the Postgres job | before commit, CI |
| Coverage | Measured 98.07% on 2026-11-23 (branch coverage, `coverage json`); must not fall below 97.5% (ratchet, 0.5% tolerance) | `pytest --cov --cov-fail-under=97.5` | CI |
| Migrations | Up, down, up, no drift | `alembic upgrade/downgrade/check` | CI |
| Dependencies (external) | Nothing at high or above | `pip-audit -r requirements.txt` | CI |
| Secrets (external) | None in source | `gitleaks` (redacted) | CI |
| Mutation spot-check | Every new guard in a phase is broken once and must fail a test | manual, recorded in LOG | each phase |

## Out of scope (deferred)

- Distributed tracing (OpenTelemetry): one service, nothing to trace across yet. Revisit if a worker is added.
- Alerting, dashboards and runbooks: no deployed environment yet. Phase 10 deploys and adds a symptom-based
  alert (error rate) with a runbook.
- Idempotency keys: documented as not retry-safe instead (T9). Low risk for a manual-use legal tool.
- camelCase API: see assumption 2.
- Branch protection: conflicts with the owner's choice to push directly to `main`. CI still runs on every push.
- Frontend service in docker-compose: Phase 9.
- Account deletion and data export (privacy): see open question 2.

## Open questions

1. CI's Postgres service uses `postgres/postgres` in the workflow file. The ci-cd skill prefers
   GitHub Secrets even for CI. It's a throwaway container, so I propose leaving it unless you'd like
   a secret set.
2. **Answered 2026-11-24: add now (T15 above).** Account deletion and export: security-and-hardening asks for a working deletion path for personal
   data. Add it in Phase 7 (`DELETE /auth/me`, `GET /auth/me/export`; deletion refused while you are
   the sole owner of a shared document), or defer?
3. Adding `prometheus-client` (T8) is a new dependency. OK?

## Success criteria

- Every task's acceptance criteria are met with the verification shown, recorded in `LOG.md`.
- `CONSTRAINTS.md` exists. Each enforced row fails on a deliberate violation and passes on main.
- CI includes at least two external checks (`pip-audit`, `gitleaks`) and is green.
- No Critical or High open from the three review agents.
- Full suite green on SQLite and Postgres. Coverage not below the ratchet (97.5%).
- Owner has reviewed the finished backend.
