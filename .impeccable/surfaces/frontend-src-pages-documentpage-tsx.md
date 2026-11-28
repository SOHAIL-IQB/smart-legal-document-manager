---
version: 1
slug: "frontend-src-pages-documentpage-tsx"
primary_target: "frontend/src/pages/DocumentPage.tsx"
related_targets: []
---

# Document workspace

**Scope and mode:** `/documents/{id}`: read a contract at any version, write a new version, compare
any two, restore or withdraw versions, see its activity, share it, rename it, upload a new version
from a file. Operate: reading comes first; every action is one or two steps from the text.

**Audience and job:** a member of a small legal team, and a portfolio reviewer in a demo workspace.
They want to know what the current text says, what changed between drafts and who changed it, and
who can see it. Their role decides what they can do: viewers read, compare and see activity; editors
also write, upload, restore and rename; owners also withdraw versions and manage members.

**Content (the API's, never invented):**
- The document: title, my role, version count.
- Versions with number, author, time, note, source (typed, restored from N, uploaded file name),
  word count, and the withdrawn state with who withdrew it.
- A version's full text. A withdrawn version's text is gone from reading and comparing (410).
- Comparison rows with word segments, stats, the "approximate" flag and collapsed unchanged
  stretches (`context`).
- Activity events: created, version saved, restored, withdrawn, renamed, shared, role changed,
  removed or left.
- Members with roles.

**Constraints:**
- WCAG 2.2 AA:
  - the margin column is a labelled list with `aria-current` on the version being read;
  - line forms are named in text as well;
  - the comparison is a real table with headers, inserted and removed words marked by form
    (underline and strike), and "approximate" announced as text;
  - dialogs are modal with labelled fields.
- The URL holds the tab, the version being read and the compared pair.
- Small text never on vermilion. Desktop and phone.
- The API's rules are shown, not hidden: the last live version can't be withdrawn (409), and
  saving the same text saves nothing (200 with no version).

## Direction contract

THESIS: The landing page's promise made real: the contract is one sheet whose versions run down a
strict margin column as numbered folds. Reading, comparing and history happen beside that column,
never in a separate history screen. It refuses the category's split of "document" and "version
history" into different pages.

OWN-WORLD:
- The established Folding Sequence (DESIGN.md).
- The margin column uses the landing's vocabulary at working density: vermilion lining numbers, a
  line form per version (solid live, dashed withdrawn, doubled restored), the gold dot on the
  current version, and the version being read on a small vermilion square.
- Text reads on the cream ground at a comfortable measure.
- The editor is lined paper. The comparison is two ruled columns with underline and strike.
- Dialogs are washi slips.

STORY: The reviewer opens the sample agreement, sees four folds in the margin with 03 dashed and 04
doubled with the gold dot, reads the current text, switches to Compare and sees exactly which words
changed between 01 and 04 (04 restores 02's text, so the comparison skips the identical pair), writes a version of their own, and finds it in the column and the
activity.

FIRST VIEWPORT:
- The header band, then a vermilion page band with the document's title in fold-white (large type
  only), the visitor's role as a washi tag, and Share, Rename, New version and Upload version as
  washi tags where the role allows.
- Below on cream: the margin column on the left (about 18rem) with the versions, newest first, and
  the actions for the version being read under it. On the right: tabs for Read, Compare and
  Activity, then the version's header line and the start of its text.
- Phones: the band, then the column as a compact strip of version numbers, then the tabs and the
  text.

FORM: seed: none (pinned). The world is pinned by the approved Phase 9 spec ("the approved Folding
Sequence world", docs/specs/phase-9-frontend-build.md) and recorded in DESIGN.md. The owner chose
"Text with the margin column", "In place" editing and "From the margin column" comparing on
2026-11-28.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

## Unresolved

- `DESIGN.md` is updated, not rewritten, after this build: the workspace adds the editor, the
  comparison and the share dialog to the system.
