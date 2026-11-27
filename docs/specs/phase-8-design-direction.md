# Spec: Phase 8 — Design direction

Status: approved by the owner as written, 2026-11-27, with the three recommended answers: demo entry
option 3, code-first, the landing page first
Source: `PLAN.md` §7 Phase 8 · `PRODUCT.md` (owner-confirmed intent, 2026-11-27) · `LOG.md` 019
Skills: interview-me (done), spec-driven-development, impeccable (init done; new-work next),
frontend-ui-engineering, 21st (component sourcing), source-driven-development

## Objective

Decide what the frontend looks like and how a portfolio reviewer moves through it, so that Phase 9
builds one committed design instead of improvising screen by screen. Phase 8 writes no
application code.

Confirmed intent (`PRODUCT.md`): within a few minutes and without instructions, a portfolio
reviewer must see version history, a word-level comparison, sharing with roles, file upload, and
activity and notifications. The product must be convincing as a tool for a small in-house legal
team, meet WCAG 2.2 AA, and work on desktop and phone.

## Current state

- The backend is done and signed off (31 endpoints, `README.md`). There is no `frontend/` yet.
- `PRODUCT.md` exists. There is no `DESIGN.md`, no visual identity, no logo and no product name
  beyond the descriptor "Smart Legal Document Manager".
- impeccable reports no visual authority, so a new visual world is created with the owner.
- Image generation: the only image tool connected is Figma's, which spends the owner's Figma AI
  credits on each image. impeccable's own fallback reported none.

## Deviations from `PLAN.md`, and why

1. **`DESIGN.md` moves to Phase 9.** `PLAN.md` puts "tokens (DESIGN.md)" in Phase 8. impeccable
   writes `DESIGN.md` after the first build, from what was actually built, so the rulebook
   describes reality instead of being defended against it. Phase 8 instead locks the direction:
   the chosen visual world and a written direction contract that Phase 9 builds to and its finish
   review audits.
2. **Code-first by default.** Without free image generation, the decision cards show palette chips,
   type, materials and a first-viewport sketch rather than rendered comps. App screens are designed
   in code either way; only the landing page could be designed from an image first (open question 2).

## Surfaces and their modes

impeccable designs each surface for what success looks like there:

| Surface | Mode | Why |
|---|---|---|
| Landing page | Persuade | The reviewer decides in seconds whether this is worth their time |
| Sign in / sign up, demo entry | Operate | A task to finish quickly |
| Documents dashboard (search, filters, pages) | Operate | Find a contract |
| Document workspace: text, version timeline, side-by-side comparison, activity, sharing | Operate | The product's core; the best demonstration |
| Notifications, upload, account (export and delete), 404 | Operate | Tasks and states |

The visual world is created once, on one first surface, and every other surface inherits it.

## Tasks

### D1. Product name

- Propose five short, original names, each with one line on what it says about the product.
  Unchecked first ideas: *Clausetrail*, *Draftline*, *Inkstep*, *Countermark*, *Redlet*.
- Check each with a web search for existing legal-tech products or obvious trademark conflicts,
  and drop any that collide.
- The owner picks one, or asks for another round.
- Acceptance: one name chosen by the owner, recorded in `PRODUCT.md` under Brand Commitments,
  with the conflict check noted in `LOG.md`.
- **Done 2026-11-27: Tracemark** (LOG 021). Countermark was dropped: an existing app uses it.

### D2. How a reviewer gets into the demo

The reviewer has no account, and the shared demo accounts can be edited or even deleted by any
visitor (account deletion is a real feature). Three options, each with a different backend cost:

1. **Prefilled demo sign-in.** The sign-in page offers the demo accounts. No backend change; one
   visitor's edits are seen by the next, and a deleted demo account stays deleted until reseeded.
2. **Shared demo, reset on a schedule.** Option 1, plus the demo data restored periodically
   (for example nightly). A small ops task, no API change.
3. **A private demo workspace per visitor.** "Try the demo" creates fresh demo accounts and sample
   contracts for that visitor alone, removed after a day. This needs one new endpoint and a
   clean-up job, built test-first in Phase 9.

- Recommendation: **option 3**. It lets a reviewer do anything, including share, restore and
  delete, without breaking the demo for the next person, and that freedom is the strongest
  demonstration.
- Acceptance: the owner chooses; the choice is recorded here, and any backend work becomes a Phase 9
  task with its own tests.
- **Decided 2026-11-27: option 3**, a private demo workspace per visitor. The endpoint and clean-up
  job are Phase 9 tasks, built test-first.

### D3. Visual world

- Follow impeccable's new-work flow, without substitutes:
  1. Derive seven candidate worlds from the in-house legal team's own culture (its documents,
     places, rituals and graphic traditions), not from software tools.
  2. Run impeccable's `concept-seed` roll for the first surface.
  3. Present the result on impeccable's decision page in the built-in browser. It shows the
     assigned direction, any challengers with their verdicts, my own pick when it differs, a quiet
     "category standard" exit, and re-roll (plain, safer, bolder).
- The owner chooses or re-rolls as often as they like.
- First surface: **the landing page** (recommended). It is where every reviewer arrives, and
  impeccable's Persuade rules make the first viewport demonstrate the product working (a real
  comparison of the demo contract) instead of describing it. The alternative is to start from
  the document workspace.
- Acceptance: one direction locked by the owner on the decision page (or through the question
  tool if the page can't be served, disclosed).

### D4. Direction contract

- Record the locked direction in impeccable's surface brief (`.impeccable/surfaces/…`). It has six
  blocks: THESIS, OWN-WORLD, STORY, FIRST VIEWPORT, FORM (with the roll's seed reference) and
  FINISH.
- Also record the signature interaction and the motion grammar the build must deliver.
- Acceptance: the brief reads back with all six blocks and the seed reference; the owner has
  read it.

### D5. Component candidates from 21st.dev

- After D3, so components are chosen to fit the locked world rather than the other way round.
- Search 21st.dev for the parts the screens need:
  - data table for the documents list;
  - command or search palette;
  - side-by-side diff view;
  - version timeline;
  - notifications popover;
  - upload dropzone;
  - sign-in and sign-up forms;
  - share dialog with role picker;
  - toasts.
- For each candidate, record in `docs/design/components.md`:
  - its source and license;
  - what it does well;
  - what must be restyled or rebuilt to fit the locked world (impeccable treats an unrestyled
    stock component inside a committed world as a defect);
  - its accessibility state (keyboard, focus, labels).
- Acceptance: every listed part has a chosen candidate, or an explicit "build our own" with the
  reason.

### D6. Owner approval of the look

- The owner reviews the locked direction (D3), the contract (D4), the name (D1), the demo entry
  (D2) and the component list (D5) together.
- Acceptance: explicit approval recorded in `LOG.md` with the owner's words. `PLAN.md` gate:
  "Owner approves the look before full build".

## Checkpoints

- After D1 and D2: the decisions are recorded, committed and pushed.
- After D6: everything is committed and pushed, the plan's resume point moves to Phase 9, and a
  Phase 9 spec is written for approval before any frontend code.

## Out of scope for Phase 8

- Any application code, `frontend/` scaffolding, or backend change (D2's endpoint, if chosen, is
  built in Phase 9).
- `DESIGN.md` (Phase 9, after the first build).
- Generating images, unless the owner opts in under open question 2.

## Open questions

1. **Demo entry (D2):** option 1, 2, or 3? Recommendation: 3.
2. **Landing-page comps:** design the landing page from an image first, using Figma's image
   generation (spends your Figma AI credits, roughly one image per decision card), or code-first
   with no images? Recommendation: code-first. App screens are code-first either way, and the
   decision page is complete without images.
3. **First surface for the world (D3):** the landing page (recommended) or the document workspace?

## Success criteria

- A product name, a demo-entry approach and a visual direction, each chosen by the owner, not
  defaulted.
- A direction contract specific enough that two people building from it would make recognizably
  the same product.
- Every part the screens need has a sourced or justified component.
- The owner approved the look before any Phase 9 code.
