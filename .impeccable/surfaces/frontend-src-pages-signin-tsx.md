---
version: 1
slug: "frontend-src-pages-signin-tsx"
primary_target: "frontend/src/pages/SignIn.tsx"
related_targets: ["frontend/src/pages/SignUp.tsx"]
---

# Sign in, sign up and demo entry

**Scope and mode:** the two account pages, `/sign-in` and `/sign-up`, with the demo offered on both.
Operate: the visitor signs in or creates an account quickly and without doubt. The pages inherit
the Folding Sequence world the landing page built.

**Audience and job:** a returning member signs in; a new one creates an account; a portfolio
reviewer who landed here (a guard sent them, or they clicked Sign in) can still open a demo
workspace in one click instead.

**Action:** submit the form. After sign-in, go back to where the guard came from (`state.from`),
else to `/documents`. Secondary: open a demo workspace.

**Content:** sign in takes email and password; sign up takes name, email and a password of 8 to
128 characters. The API's messages are shown as they are: "Incorrect email or password.", the
429 "Too many failed sign-in attempts. Try again in N seconds.", the 409 for a taken email, and
422 field errors.

**Constraints:**
- WCAG 2.2 AA: labelled fields, inline errors tied by `aria-describedby`, focus moved to the first
  invalid field, visible focus.
- Small text never sits on vermilion.
- react-hook-form and Zod; desktop and phone.
- No invented claims.

## Direction contract

THESIS: The account pages are the sheet turned over. The title stays on the vermilion face; the
form is written on the washi underside, along the same crease. It refuses the category's centred
card floating on a blank page.

OWN-WORLD:
- The landing page's materials and tokens: vermilion sheet with kozo grain, fold-white crease, washi
  underside (#EDE3D1), sumi text, Alegreya Sans.
- Fields are ruled lines on the washi, not boxes: a sumi underline that turns vermilion-ink on focus.
- The primary button is vermilion-ink with fold-white text.
- Errors are written in vermilion-ink beside a short struck rule, the world's mark for something
  rejected.

STORY: The visitor sees which page they are on at a glance, fills two or three ruled lines and
signs in. A reviewer who doesn't want an account takes the next fold and opens a demo workspace.

FIRST VIEWPORT:
- Wide screens: a vermilion sheet fills the left part, full height, with the page title in large
  fold-white ("Sign in." / "Create an account.") and the wordmark above it.
- A vertical crease divides the sheet from its turned-back half on the right, the washi underside,
  which holds the form, the switch link (Create an account / Sign in) and, below a crease, the demo
  as a turned corner.
- Phones: a short vermilion band with the wordmark and title, then the form on washi, all in the
  first viewport.

FORM: seed: none (pinned) — the owner chose "Form on the underside" on 2026-11-28.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

## Unresolved

- `DESIGN.md` is written at F9, as the Phase 9 spec says, after this and one app screen.
