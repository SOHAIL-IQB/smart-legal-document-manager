---
version: 1
slug: "frontend-src-pages-documents-tsx"
primary_target: "frontend/src/pages/Documents.tsx"
related_targets: ["frontend/src/app/AppHeader.tsx"]
---

# Documents index and the app header

**Scope and mode:** `/documents`, the first signed-in screen, and the app header every signed-in
screen shares. Operate: find a contract fast, see what changed recently, start a new one.

**Audience and job:** a member of a small legal team, and a portfolio reviewer inside a demo
workspace. They scan their contracts, search titles and text, filter by their role, sort, page
through, open one, or start a new one from a file or pasted text. A demo visitor can switch to the
workspace's other two people to see each role.

**Action:** open a document (`/documents/{id}`). Secondary: "New document" (upload a PDF, DOCX or
TXT file, or paste text with a title); the ⌘K palette jumps to any document by title.

**Content (the API's, never invented):** each row's title, creator, my role, latest version, version
count, word count and last change. Search covers titles and latest text (`q`, up to 200 characters).
Role filter: owner, editor, viewer. Sort: last changed, created, title; either order. Pages of 20
(`limit`, `offset`). Upload refusals come from the API: too large, wrong type, unreadable, busy.

**Constraints:**
- WCAG 2.2 AA: a real table with a caption and column headers, `aria-sort`, labelled controls, a
  live status for result counts, the palette as a combobox with a listbox, the dialog modal with a
  focus trap.
- Desktop and phone (rows reflow to stacked entries on a phone).
- The URL keeps search, filter, sort and page so Back and links work.
- Small text never on vermilion.

## Direction contract

THESIS: The index is a register of sheets: every contract one ruled line in a strict numbered
column, its history shown as fold numbers. It refuses the category's card grid of documents and
its sidebar dashboard.

OWN-WORLD:
- The world's tokens and Alegreya Sans, as on the landing and account pages.
- The header is the sheet's top edge: a vermilion band with the wordmark, navigation and account
  menu at 24px or larger, or in washi tags.
- Rows are ruled by crease lines on the cream ground, with numbers in vermilion lining tabular
  figures.
- A row's history: "v4" in fold numbers, the gold dot on a document changed in the last 24 hours.
- Controls are ruled lines and small washi tags, never boxed cards. The primary action is
  vermilion-ink.

STORY: The visitor sees their contracts as a numbered register, narrows it by typing or by role,
sees which ones moved recently by the gold dot, and opens one, or starts a new one.

FIRST VIEWPORT:
- A vermilion band across the top, about 30% of the height on desktop, holds the header (wordmark,
  Documents, Notifications, account menu) and the title "Documents." large in fold-white, with
  "New document" as a washi tag at its foot.
- Below on cream: the search line, role filter and sort, then the first rows of the register.
- Phones: a shorter band, then the controls and stacked rows.

FORM: seed: none (pinned) — the approved Phase 9 spec ("Dense numbered rows") and the owner's
choice "Register under a sheet edge" on 2026-11-28.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

## Unresolved

- `DESIGN.md` follows in F9, from the landing page and this screen.
