# Spec: Phase 9 — Frontend build

Status: approved by the owner as written, 2026-11-27. This includes migration `0008`, the listed
dependencies, the CI frontend job, and the three recommended answers: 24-hour expiry and 5
workspaces per IP per hour; impeccable's finish reviewer and documenter allowed, one finish review
per surface; nginx in production
Source: `PLAN.md` §7 Phase 9 · `PRODUCT.md` · Phase 8 outcome (`docs/specs/phase-8-design-direction.md`,
`.impeccable/surfaces/frontend-src-pages-landing-tsx.md`, `docs/design/components.md`)
Skills: spec-driven-development, planning-and-task-breakdown, frontend-ui-engineering, impeccable
(new-work build, code-led), test-driven-development, incremental-implementation,
source-driven-development, security-and-hardening (demo workspace), git-workflow-and-versioning

## Objective

Build Inkstep's frontend in `frontend/`: the landing page and every app screen, in the approved
Folding Sequence world, against the existing API. Also build the one backend addition the design
needs: a private demo workspace per visitor.

Done means a portfolio reviewer, with no instructions and no account, opens the landing page, starts
their own demo workspace, and sees version history, a word-level comparison, sharing with roles,
upload, and activity and notifications. It works on desktop and phone, meets WCAG 2.2 AA, and
shows no console errors.

## Current state

- The backend is complete (31 endpoints, `README.md`). The frontend doesn't exist.
- Toolchain: Node 26.13.1 (current LTS, "Lithium") and npm 11.20.0 on this machine.
- Current registry versions (2026-11-27): Vite 8.4, React 19.3, TypeScript 7.0, Tailwind CSS 4.3,
  TanStack Query 5.108, React Router 8.5, react-hook-form 7.92, Zod 4.6, Vitest 5.1, ESLint 10.15.
  Exact versions are pinned in `package-lock.json` at scaffold time.

## Tasks

### Slice A — Foundations

**F0. Clear the open items from Phase 8**
- Confirm the 21st.dev catalog license terms for copying component code into this public repository.
- Check the code of the five "claimed" candidates: command palette, timeline, notification inbox,
  dropzone, toast. The free tier allows two retrievals a day.
- Any candidate whose license is unclear or whose code fails accessibility is built our own instead.
- Acceptance: `docs/design/components.md` updated; no catalog code is copied before this passes.
- **Done 2026-11-27 (LOG 027):** the license is unclear for a public repository, so no catalog code is
  copied. Every part is built our own on shadcn/Radix, with 21st.dev candidates as design references.
  The code checks are therefore not needed.

**F1. Demo workspace (backend, test-first; spec D2)**

`POST /api/demo/workspaces` creates a private copy of the demo: three fresh demo accounts and the
four sample contracts with their history, sharing, activity and notifications. It signs the visitor
in as the first account.

Behavior:
- The response names the workspace's other two accounts.
- `POST /api/demo/workspaces/current/switch` lets the visitor become another account of the **same**
  workspace, so they can see each role.

Isolation and safety:
- Demo accounts can share only within their own workspace.
- No real account can be added to a demo document, and no demo account to a real one.
- A demo account cannot be signed into with a password; it has an unusable hash, and sessions come
  from the endpoint.

Expiry and limits:
- A workspace expires after 24 hours. `python -m scripts.purge_demo` deletes expired workspaces and
  everything in them, and creating a workspace also purges expired ones.
- Creation is rate-limited per IP: 5 per hour by default, `DEMO_WORKSPACES_PER_IP`. That stops
  storage abuse.

Schema (**needs your approval**, per `AGENTS.md`):
- Migration `0008` adds a `demo_workspaces` table: id, created_at, expires_at.
- It adds a nullable `users.demo_workspace_id`.
- Both are additive, with a tested downgrade.

The seed script and the demo workspace share one service, so the sample data is defined once.

Acceptance:
- Tests first for each rule above, on SQLite and PostgreSQL.
- Deliberate breaks in the throwaway copy.
- README, ADR 0002 (retry safety: creating a workspace is not safe to retry) and the user guide
  updated.
- **Done 2026-11-27 (LOG 028):** 22 tests, passing on both databases; 13 of 13 deliberate breaks
  caught; migration `0008` round-trips with no drift.

**F2. Scaffold `frontend/`**
- Stack: Vite + React + TypeScript; Tailwind CSS 4 via `@tailwindcss/vite`; shadcn initialised (Radix
  primitives); TanStack Query; React Router; react-hook-form + Zod; ESLint; Vitest + Testing Library
  + jsdom. Node 26 is pinned in `.nvmrc` and `engines`.
- **TypeScript:** the newest version that typescript-eslint supports. TypeScript 7 (the native
  compiler) is used only if it is supported; the reason is recorded either way.
- **Same origin in development:** the Vite dev server proxies `/api` to `localhost:8000`, so the
  `httpOnly` cookie, the CSRF header and every response header (`X-Request-ID`,
  `Content-Disposition`) work without changing CORS.
- **Typed API client:** generated from the backend's OpenAPI schema with `openapi-typescript` and
  committed. A test fails when the generated file is out of date, like the README check.
- Acceptance: `npm run typecheck`, `npm run lint`, `npm test` and `npm run build` pass; the dev server
  shows the API's health.
- **Done 2026-11-27 (LOG 029):** TypeScript is **5.9.3**: typescript-eslint supports `<6.1.0`, and
  openapi-typescript 7.13 requires `^5`. ESLint replaced the template's oxlint. All four checks
  pass, and the dev server shows the API's readiness through the proxy.

**F3. App shell**
- Router with public routes (landing, sign in, sign up, 404) and signed-in routes behind a guard.
- Auth state from `GET /api/auth/me`.
- Every write sends `X-Requested-With`.
- One error handler shows the API's message and request ID.
- Toasts (Sonner, restyled).
- Acceptance: tests for the guard, the CSRF header, and error handling with a request ID.
- **Done 2026-11-27 (LOG 030):** 23 frontend tests; 14 of 14 deliberate breaks caught; checked live
  against the API. Open: a signed-out session check makes the browser log a 401 (LOG 030).

### Slice B — Surfaces (impeccable new-work, code-led; each surface finishes with its review)

**F4. Landing page.** Built to the direction contract:
- the sheet is the page;
- fold numbers run down the margin;
- the signature fold and unfold, with replay;
- "Open your demo workspace" as the turned-back corner, calling F1.

Acceptance:
- impeccable's first-viewport capture at desktop and mobile.
- Its detector run once.
- Its finish review against the contract (see open question 2).
- Reduced motion works; no console errors.

**F5. Sign in, sign up and demo entry.** Our own forms (react-hook-form + Zod), labelled, with inline
errors tied by `aria-describedby`. Rate-limit (429) and wrong-password messages come from the API.

**F6. Documents index**
- Dense numbered rows (adapted Data Table #27049).
- Search, role filter, sort, and server-side pagination (`limit`, `offset`).
- The ⌘K palette.
- Upload of a new document.
- Empty, loading and error states.

**F7. Document workspace**
- Read the current version.
- Save a new version from a plain-text editor, with an optional change note.
- The **version margin column** (signature): states by line form, the gold dot for "now", restore,
  and delete for owners.
- Side-by-side comparison from the API's rows, with `context` collapsing and an "approximate" notice.
- Rename, activity log, and the share dialog (rebuilt on Radix).
- Upload a new version.

**F8. Notifications, account and 404**
- The inbox popover with unread count, mark one read and mark all read.
- An account page with data export (download) and account deletion (password, the 409 list of
  documents explained).
- The 404 page.

**F9. `DESIGN.md`**
- After F4 and one app screen are built, impeccable's documenter writes `DESIGN.md` and
  `.impeccable/design.json` from the built world (see open question 2).

### Slice C — Quality and delivery

**F10. Frontend tests.** Vitest + Testing Library for:
- the API client and its error handling;
- the auth guard and the CSRF header;
- the comparison view (rows, segments, approximate);
- the version margin (states, keyboard, `aria-current`);
- the share dialog (focus trap, labels, role select).

A new frontend behavior needs a test that fails without it (`AGENTS.md`).

**F11. CI and constraints** (CI change: **needs your approval**)
- A `frontend` job: `npm ci --ignore-scripts`, typecheck, lint, test, build.
- `CONSTRAINTS.md` gains the frontend rows:
  - lint and typecheck clean;
  - tests pass;
  - coverage floor measured after F10 (ratchet);
  - a JavaScript bundle budget measured after F4–F8.

**F12. Docker Compose**
- A `frontend` service: the built files served by nginx, which proxies `/api` to the API, so
  production is same-origin too.
- `docker compose up --build` gives the whole product on one URL.
- The README's Quick start is updated and run on a clean clone.

## Dependencies to approve (exact versions pinned at scaffold)

- **Runtime:** react, react-dom, react-router, @tanstack/react-query, react-hook-form, zod,
  @hookform/resolvers, Radix primitives via shadcn, lucide-react, motion, sonner.
- **Development:** vite, @vitejs/plugin-react, typescript, tailwindcss, @tailwindcss/vite, eslint,
  typescript-eslint, vitest, @testing-library/react, @testing-library/user-event, jsdom,
  openapi-typescript.

## Checkpoints

- After Slice A: both suites, the floor guard and the new frontend checks pass; commit, push, CI
  green.
- After each surface in Slice B: finish review, commit, push.
- After Slice C: the clean-clone run, then the owner reviews the built frontend (gate before Phase 10).

## Out of scope

- Deployment to a host (Phase 10).
- Browser end-to-end runs, accessibility audit and performance audit (Phase 10).
- Rich-text editing, real-time co-editing and e-signatures (`PRODUCT.md`).

## Open questions

1. **Demo limits:** workspaces expire after 24 hours, with at most 5 new workspaces per IP per hour.
   Recommendation: as proposed.
2. **impeccable's finish reviewer and documenter run as subagents.** You asked earlier to stop
   agent review cycles. Options:
   - allow just these two shipped reviewers, one finish review per surface (impeccable's intended
     quality gate);
   - or run impeccable's in-thread version of the same review, disclosed.

   Recommendation: allow the two shipped reviewers, with no review loops beyond what impeccable
   prescribes.
3. **Serving in production:** nginx in front of the API (same origin) or FastAPI serving the built
   files. Recommendation: nginx.

## Success criteria

- A first-time visitor reaches a working demo workspace from the landing page, without
  instructions.
- Every screen in `PLAN.md` Phase 9 exists, with loading, empty and error states.
- The landing page passes impeccable's finish review against the direction contract.
- `DESIGN.md` describes the built world.
- All suites pass: backend on SQLite and Postgres, and the frontend's typecheck, lint, tests and
  build. CI is green.
