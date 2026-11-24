# Constraints

Last reviewed: 2026-11-23 by the owner (approved with the Phase 7 spec, `docs/specs/phase-7-hardening.md`).

This is the project's quality bar. Every rule names the command that checks it. Do not weaken this
file to make a change pass: `scripts/floor_guard.py` reports any loosened or removed rule.

## Floor (always enforced)

- Suppressions: no new suppression comments (`# noqa`, `# type: ignore`, `pragma: no cover`, `# nosec`) outside a tracked exception
- Tests: no skipped, xfailed or deleted tests, and no assertions removed from tests that remain
- Stubs: no unimplemented stubs, swallowed exceptions (`except ...: pass`) or TODO/FIXME left in code
- Secrets: no secrets in source
- This file: no rule or threshold weakened or removed

Checked by `python scripts/floor_guard.py --base origin/main` (exit 0 clean, 1 violation, 2 could not run).

## Enforced with numbers

| Dimension | Rule | Checked by | Runs at |
|---|---|---|---|
| Lint | Zero ruff errors; formatted | `ruff check . && ruff format --check .` | before commit, CI |
| Tests (SQLite) | All pass | `pytest` | before commit, CI |
| Tests (Postgres) | All pass, including the row-lock concurrency test | `TEST_DATABASE_URL=… pytest` | before commit, CI |
| Coverage | must not fall below 97.5% (measured 98.07% on 2026-11-23; 0.5% ratchet tolerance) | `pytest --cov --cov-fail-under=97.5` | CI |
| Migrations | Upgrade, downgrade to base, upgrade, then no drift between models and migrations | `alembic upgrade head && alembic downgrade base && alembic upgrade head && alembic check` | CI (Postgres) |
| Dependencies (external) | No known vulnerability at any severity in pinned runtime dependencies | `pip-audit -r requirements.txt` | CI |
| Secrets (external) | No secrets found | `gitleaks` (redacted output) | CI |
| Floor | No floor violation in the pushed commits | `python scripts/floor_guard.py --base <previous commit>` | CI |

At least two checks are external (pip-audit, gitleaks): they judge the code against outside data,
not against tests written in this repo.

## Measured, not yet enforced

| Metric | Today | Direction |
|---|---|---|
| API latency p95 (seeded data) | not measured yet (Phase 7 T11) | must not grow once recorded |

## Phase rule

Every new guard (validation, permission check, limit) added in a phase is deliberately broken once,
and the suite must fail. Results are recorded in `LOG.md`.

## Exceptions

A new row is reported by the floor guard for review. It blocks unless it names an owner and expires
within 90 days. A row covers either a whole file (its path is listed in `.constraintsignore`) or a
single suppression line that cites the row's ID, e.g. `# noqa: S603  [W3]`.

| ID | Rule | Path | Reason | Owner | Expires |
|----|------|------|--------|-------|---------|
| W1 | silenced-checker, unfinished-work | scripts/floor_guard.py | The guard's source contains the patterns it searches for, plus one `noqa: S603, S607` for its fixed `git` subprocess call | SOHAIL-IQB | 2027-02-20 |
| W2 | silenced-checker, unfinished-work, test-made-easier | tests/test_floor_guard.py | Its tests write those patterns into throwaway repositories to prove they are caught | SOHAIL-IQB | 2027-02-20 |
| W3 | silenced-checker | app/utils/extract.py (the `subprocess.Popen` line in `_run_worker`) | ruff S603 flags every subprocess call; the argv is fixed to this interpreter and the parse worker module, with no user input | SOHAIL-IQB | 2027-02-20 |
