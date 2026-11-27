---
version: 1
slug: "frontend-src-pages-landing-tsx"
primary_target: "frontend/src/pages/Landing.tsx"
related_targets: []
---

# Landing page

**Scope and mode:** Inkstep's public landing page, the first surface of the visual world. Persuade.
The app screens (Operate) inherit this world in Phase 9.

**Audience and job:** portfolio reviewers with two or three minutes and no account; in the
product's story, an in-house legal team. They must understand within seconds that every draft is
kept and any two can be compared.

**Action:** "Open your demo workspace", which creates a private demo workspace (spec D2; endpoint
built in Phase 9). It is visible in the first viewport.

**Proof:** the sample Master Services Agreement and its real seeded history (v1 Asha Rao; v2 Chloe
Martin, 99.5% to 99.9%; v3 withdrawn; v4 restored), labelled as sample text.

**Constraints:**
- WCAG 2.2 AA: small text never sits on vermilion.
- Desktop and phone.
- No invented customers, numbers or claims.
- Documents are plain text.

## Direction contract

THESIS: A contract is one uncut sheet: every version is a numbered fold, and the current draft
still carries every earlier crease. It refuses the category's split hero with a screenshot and a
row of feature cards.

OWN-WORLD:
- Washi cream ground (#F6F1E9) with kozo grain. Vermilion (#D83A2E) owns the sheet and the large
  type.
- Fold-white crease lines, sumi black (#1A1A1A) text, and one gold dot (#D4AF37) on the current
  version.
- A quiet humanist sans; numerals in a strict margin column.
- State by line form: solid is live, dashed is withdrawn but kept, doubled is restored. Inserted
  words are underlined; removed ones are struck.

STORY: The reviewer meets the sample agreement as a creased sheet and steps through its four
folds. They see 99.5% become 99.9%, and see the withdrawn draft stay on the record. They grasp that
nothing is ever lost, and open their own demo workspace.

FIRST VIEWPORT: The page is the sheet, seen flat from above.
- A vermilion square fills the viewport's height, offset right. Its creases run on across the cream
  and divide the page into panels.
- The headline is set large in fold-white across the upper panels.
- The clause, with its change marked, sits on one panel.
- Fold numbers 01–04 run down the cream margin column, with the gold dot on 04.
- "Open your demo workspace" is the next fold: the lower corner turned back, showing the cream
  underside with the action set in sumi.

FORM: The folding-sequence challenger (catalog paper-folds-pleats-deployable-orizuru-crane-sequence,
verdict competitive), outside my ordered list. The owner chose it in round 2 over the assigned court
cause list and my pick, pleading paper. seed:a1d94de8f3bc5217

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

## Signature interaction and motion

- **Signature:** dragging along the margin column folds and unfolds the sheet along its creases.
  The clause switches version, and each changed word keeps a short fading afterglow. "Replay"
  folds through the whole history in order.
- **Motion grammar:** one fold at a time, rotating on its crease axis with paper weight (about
  420 ms, ease-in-out). Nothing slides. With reduced motion, states swap directly.

## Unresolved

- Typefaces: chosen at build time within "quiet humanist sans", avoiding impeccable's default-face
  list.
- How far the world reaches into the Operate screens (dashboard and workspace) is decided in the
  Phase 9 spec; `DESIGN.md` records the result after the first build.
