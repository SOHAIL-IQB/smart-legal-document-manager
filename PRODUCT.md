# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

React + Vite + TypeScript in `frontend/` (owner decision D2, 2026-11-22, `PLAN.md` §2), talking
to the existing FastAPI backend under `/api`. Planned libraries (`PLAN.md` §3, assumption 7):
Tailwind CSS with shadcn/ui primitives (21st.dev components build on these), TanStack Query,
React Router, react-hook-form with zod. Deployment target is not decided yet (Phase 10).

## Users

Two audiences, in this order of priority (confirmed by the owner, 2026-11-27):

1. **Portfolio reviewers.** Hiring managers, recruiters and potential clients who open the live
   demo for two or three minutes. They judge whether this is a real, well-made product and
   whether its author can build one. They arrive with no instructions and no account.
2. **The users in the product's story: a small in-house legal team.** A lawyer or two and a
   paralegal at a company, negotiating contracts with outside parties: NDAs, commercial leases,
   vendor and services agreements, employment agreements. They need to know what changed between
   drafts, who changed it, and who can see it.

When the two conflict, the reviewer's first few minutes win, as long as the product stays truthful
to the legal team's work.

## Product Purpose

A secure, multi-user version-control system for contracts. Every edit becomes a version that is
never overwritten; any two versions can be compared word by word; each document is shared with
owners, editors and viewers; members are notified of meaningful changes; and every action is kept
in an append-only activity log.

Success for this project: without instructions, a reviewer gets into the demo and sees version
history, a word-level comparison, sharing with roles, file upload, and activity and notifications,
on desktop and on a phone, with no console errors.

## Positioning

What the product can truthfully claim, because the backend proves it with tests:
- History can't be rewritten: version numbers are never reused, a deleted version stays in the
  audit trail, restoring creates a new version, and simultaneous saves queue instead of colliding.
- Comparison shows exactly which words changed, side by side, and stays fast on long contracts.
- People who aren't members of a document can't even tell it exists.
- Uploaded PDFs and Word files are parsed in an isolated process.

## Operating Context

- Documents are plain text. A version is created by typing or pasting a new full text, by
  restoring an older version, or by uploading a PDF, DOCX or TXT file (only its text is kept,
  with the original file name).
- Roles per document: owner (everything, including sharing and deletion), editor (new versions,
  restore, rename), viewer (read, compare, view activity).
- The backend API, its error format and its retry rules are fixed by
  `docs/adr/0002-api-contract.md`; the session is an `httpOnly` cookie (`docs/adr/0001`).
- Demo data: `python -m scripts.seed` creates three demo accounts (`asha@demo.example`,
  `ben@demo.example`, `chloe@demo.example`, password `demo password 2026`) and four sample
  contracts with history, a restore, a deleted version, sharing in every role, activity and
  notifications.

## Capabilities and Constraints

- Capabilities: the 31 API endpoints listed in `README.md`, including search, filters and
  pagination; comparison with `context` collapsing and an `approximate` flag; upload; notification
  inbox; per-document activity; data export and account deletion.
- Constraints: use the existing API; only small, additive API changes if a screen needs them.
- Out of scope (owner-confirmed): real-time co-editing, e-signatures, AI summaries (declined
  2026-11-22), pricing and payments, native mobile apps, rich-text editing.
- Product name: **Inkstep** (chosen 2026-11-27; see Brand Commitments).

## Brand Commitments

- **Name: Inkstep** (owner's choice, 2026-11-27). It says each version is a step written in ink that
  can't be erased. It passed the full check (exact-name search, products, trademark listings, likely
  domains): the only uses found are an inactive student tattoo app (2022) and an artist's handle. That
  is a careful web check, not legal trademark clearance; domain availability needs a registrar.
- "Smart Legal Document Manager" remains the descriptor ("Inkstep — smart legal document
  manager") and the repository name.
- No logo, voice or visual identity exists yet; Phase 8 D3 creates the visual world.

## Evidence on Hand

- Real: the working backend, 460 automated tests, CI, the performance measurements in `PERF.md`,
  and the demo data from `scripts/seed.py` (all sample text is original, not legal advice).
- None: customers, users, testimonials, logos, press, usage numbers or reviews. Future work must
  not invent any of these.

## Product Principles

1. **Show, don't claim.** Every promise on screen should be one the reviewer can watch the product
   keep: a real comparison, a real audit trail, a real permission refusal.
2. **The paper trail is the product.** Who changed what, when, and from which version is always
   one step away; nothing that happened is hidden or lost.
3. **Two minutes to the best part.** A first-time visitor reaches the comparison and the history
   quickly, without instructions. (How they get in without an account of their own is a design
   decision for the Phase 8 spec.)
4. **Plain words for legal work.** Labels say what happens ("Restore version 2 as a new version"),
   not what the database does.
5. **Honest edges.** Refusals, deleted versions and approximate comparisons are shown and explained,
   never hidden.

## Accessibility & Inclusion

WCAG 2.2 AA (owner-confirmed, 2026-11-27): keyboard access to every action, visible focus, text
contrast, and screen-reader names for icons and status changes. It must work on desktop and on a
phone.
