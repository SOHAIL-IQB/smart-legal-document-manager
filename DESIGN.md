---
name: Inkstep
description: Version control for contracts, drawn as one uncut sheet whose every version is a fold.
colors:
  fold: "#f6f1e9"
  washi: "#ede3d1"
  vermilion: "#d83a2e"
  vermilion-ink: "#b42d22"
  vermilion-ink-deep: "#96251b"
  sumi: "#1a1a1a"
  sumi-soft: "#4a4540"
  gold: "#d4af37"
  gold-edge: "#9c7e1e"
  crease-ground: "rgb(216 58 46 / 0.32)"
typography:
  display:
    fontFamily: "Alegreya Sans, Gill Sans, Segoe UI, system-ui, sans-serif"
    fontSize: "clamp(2.75rem, 7vw, 6rem)"
    fontWeight: 300
    lineHeight: 0.98
    letterSpacing: "-0.015em"
  headline:
    fontFamily: "Alegreya Sans, Gill Sans, Segoe UI, system-ui, sans-serif"
    fontSize: "clamp(2rem, 4.2vw, 3.5rem)"
    fontWeight: 300
    lineHeight: 1.05
    letterSpacing: "-0.01em"
  title:
    fontFamily: "Alegreya Sans, Gill Sans, Segoe UI, system-ui, sans-serif"
    fontSize: "2rem"
    fontWeight: 300
    lineHeight: 1.1
  wordmark:
    fontFamily: "Alegreya Sans, Gill Sans, Segoe UI, system-ui, sans-serif"
    fontSize: "1.5rem"
    fontWeight: 500
  figure:
    fontFamily: "Alegreya Sans, Gill Sans, Segoe UI, system-ui, sans-serif"
    fontSize: "1.5rem"
    fontWeight: 400
    lineHeight: 1
    fontFeature: "lnum, tnum"
  body-large:
    fontFamily: "Alegreya Sans, Gill Sans, Segoe UI, system-ui, sans-serif"
    fontSize: "1.125rem"
    fontWeight: 400
    lineHeight: 1.45
  body:
    fontFamily: "Alegreya Sans, Gill Sans, Segoe UI, system-ui, sans-serif"
    fontSize: "1.0625rem"
    fontWeight: 400
    lineHeight: 1.55
  label:
    fontFamily: "Alegreya Sans, Gill Sans, Segoe UI, system-ui, sans-serif"
    fontSize: "0.9375rem"
    fontWeight: 500
  caption:
    fontFamily: "Alegreya Sans, Gill Sans, Segoe UI, system-ui, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.35
rounded:
  none: "0px"
  dot: "50%"
spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  gutter: "20px"
  field: "22px"
  page: "clamp(20px, 4vw, 56px)"
  section: "clamp(72px, 10vw, 136px)"
components:
  button-primary:
    backgroundColor: "{colors.vermilion-ink}"
    textColor: "{colors.fold}"
    typography: "{typography.body}"
    rounded: "{rounded.none}"
    padding: "12px 22px"
    height: "48px"
  button-primary-hover:
    backgroundColor: "{colors.vermilion-ink-deep}"
  tag:
    backgroundColor: "{colors.washi}"
    textColor: "{colors.sumi}"
    typography: "{typography.label}"
    rounded: "{rounded.none}"
    padding: "6px 12px"
    height: "36px"
  tag-large:
    backgroundColor: "{colors.washi}"
    textColor: "{colors.sumi}"
    typography: "{typography.body}"
    rounded: "{rounded.none}"
    padding: "8px 16px"
    height: "44px"
  text-button:
    textColor: "{colors.sumi}"
    typography: "{typography.label}"
    padding: "0 4px"
    height: "40px"
  field-line:
    textColor: "{colors.sumi}"
    typography: "{typography.body-large}"
    rounded: "{rounded.none}"
    padding: "9px 2px 7px"
  field-line-focus:
    backgroundColor: "rgb(246 241 233 / 0.6)"
    textColor: "{colors.sumi}"
  washi-slip:
    backgroundColor: "{colors.washi}"
    textColor: "{colors.sumi}"
    rounded: "{rounded.none}"
    padding: "clamp(20px, 4vw, 32px)"
    width: "min(560px, calc(100vw - 24px))"
  vermilion-band:
    backgroundColor: "{colors.vermilion}"
    textColor: "{colors.fold}"
    typography: "{typography.display}"
    rounded: "{rounded.none}"
    padding: "clamp(20px, 5svh, 56px) clamp(20px, 4vw, 56px) clamp(18px, 3svh, 28px)"
  register-number:
    textColor: "{colors.vermilion}"
    typography: "{typography.figure}"
    width: "3.5rem"
  gold-dot:
    backgroundColor: "{colors.gold}"
    rounded: "{rounded.dot}"
    size: "12px"
---

# Design System: Inkstep

## Overview

**Creative North Star: "The Folding Sequence"**

A contract is one uncut sheet of paper. Every version is a numbered fold, and the current draft still carries every earlier crease. The whole interface is built from that one sheet: a vermilion face with fibrous grain, a cream ground it lies on, and a washi underside that shows wherever the sheet is turned over. Pages are composed from the sheet's geometry. The landing page is the sheet seen flat from above; the account pages are the sheet turned over, title on the face and form on the underside; the signed-in screens sit under the sheet's top edge, a vermilion band whose shade falls on a ruled register.

The material is paper and ink, never screen chrome. Divisions are crease lines, not boxes or gaps. Overlays are slips of washi laid on the page, square-cornered with a warm paper shadow. Type is a quiet humanist sans, light and large on the sheet, plain and readable on the ground. Colour is spent with discipline: vermilion owns the sheet and large type, a deeper ink red carries every small red mark, and one gold dot marks what is current.

Motion is folding. One fold at a time, rotating on its crease with paper weight; nothing slides into place. Under reduced motion every state swaps directly.

**Key Characteristics:**
- One sheet, three faces: vermilion face, cream ground, washi underside, each with its own grain.
- Ruled lines for fields, crease lines for divisions, washi slips for anything laid on top.
- State shown by the form of a line, never by colour alone.
- Square paper corners everywhere; the gold dot is the only round thing.
- Light 300-weight display type; strict lining tabular figures for every number.

## Colors

A warm paper palette: one saturated red sheet on a cream ground, black ink, and a single gold accent.

### Primary
- **Sheet Vermilion** (#d83a2e): the sheet itself. Fills the landing square, the account face, the app header band and the page band under it, the landing's closing panel, the favicon, the wordmark mark and the text selection. On the ground it may also set large figures: register numbers and fold numbers (24px and up), and record titles on the landing. Carries the sheet grain (`--grain-sheet`) whenever it fills an area.
- **Ink Vermilion** (#b42d22): the red for anything small or interactive. Primary buttons, field focus lines, error text and its struck rule, the resting underline under controls in words, version labels ("v4"), active-tab rule, form alerts. 5.4:1 on the ground.
- **Deep Ink Vermilion** (#96251b): the pressed-in hover state of a primary button, nothing else.

### Tertiary
- **Current Gold** (#d4af37) with **Gold Edge** (#9c7e1e) as its 1px inner ring: the gold dot only. It means "current": the current version on the landing, a document changed in the last day on the index.

### Neutral
- **Fold White** (#f6f1e9): the ground every page rests on (with `--grain-ground` flecks), the text colour on vermilion, and the crease lines drawn on the sheet.
- **Washi Underside** (#ede3d1): the back of the sheet. The account form's half, dialogs, the account menu, the palette, the dropzone, toasts, header tags and the landing's "Sample text" label.
- **Sumi Ink** (#1a1a1a): body text, field lines at rest, the table's head rule, the default focus outline.
- **Sumi Wash** (#4a4540): secondary text: notes, hints, metadata, dates, struck words, inactive tabs. 8.4:1 on the ground.
- **Ground Crease** (rgb(216 58 46 / 0.32)): every crease line on the cream ground and the washi: row rules, menu separators, the tab rail, the dropzone edge, the landing's creases running on from the sheet. Declared on `:root` so dialogs and menus rendered in a portal inherit it.

### Named Rules
**The Large-Type-Only Rule.** Small text never sits on vermilion: fold white on Sheet Vermilion is about 4.1:1, so only text of 24px or more goes on the sheet (the wordmark on a band is set at exactly 24px for this reason). Anything smaller that must sit on the sheet goes on a washi tag.

**The Ink Red Rule.** Small red text, red controls and red rules use Ink Vermilion (#b42d22), never Sheet Vermilion. Sheet Vermilion is for areas and for figures of 24px or more.

**The One Gold Dot Rule.** Gold has one meaning: what is current. It appears only as the 12px gold dot (18px in the landing legend) and never as a fill, border or text colour.

## Typography

**Display Font:** Alegreya Sans, self-hosted at 300, 400 and 500 (with Gill Sans, Segoe UI, system-ui)
**Body Font:** Alegreya Sans (same stack)

**Character:** one humanist sans across the whole system, with calligraphic warmth at light weights. Large type goes light (300) and tight; labels and controls go to 500; nothing is set heavier.

### Hierarchy
- **Display** (300, clamp(2.75rem, 7vw, 6rem), 0.98): page titles on vermilion ("Documents.", "Sign in."), the landing's closing title. The landing headline scales the same way inside the sheet (9.6cqw, 1.02). Titles end with a full stop.
- **Headline** (300, clamp(2rem, 4.2vw, 3.5rem), 1.05): landing section titles on the ground, at most 18ch wide.
- **Title** (300, 2rem, 1.1): dialog titles on washi. Record titles on the landing run 1.75–2.5rem in vermilion.
- **Wordmark** (500, 1.5rem): the wordmark and its 20px folded mark; 1.375rem on the ground.
- **Figure** (400, 1.5rem, 1, lining tabular): register numbers in vermilion; fold numbers at 1.5–1.75rem.
- **Body Large** (400, 1.125rem, 1.45): field input text, intros, document titles in the register (at 500).
- **Body** (400, 1.0625rem, 1.55): running text and primary-button text (at 500). Measures held to 44–52ch.
- **Label** (500, 0.9375rem): field labels, tags, column heads at 0.875rem.
- **Caption** (400, 0.875rem, 1.35): hints, metadata, references, the gold-dot key.

### Named Rules
**The Light Display Rule.** Display, headline and title sizes are always weight 300 with slight negative tracking. Emphasis comes from size and placement on the sheet, never from bold.

**The Lining Figures Rule.** Every number that is compared or scanned (fold numbers, register numbers, version counts, word counts, page ranges) is set in lining tabular figures.

## Layout

Pages are composed from the sheet's geometry rather than a card grid. On the landing the sheet is a square sized to the viewport (`min(100vw, 640px, …)` stacked; full height and offset right from 1100×600 up), its horizontal crease running on across the ground to divide the margin column into panels; inside the sheet, sizes are in container units so the composition holds at every size. The account pages split at 900px into the vermilion face (44%) and the washi underside, with the face's crease running on across the form; below 900px a short vermilion band sits above the form. Signed-in screens stack a vermilion header band, a vermilion page band (clamp(150px, 24svh, 260px) high, shortened on phones) and the cream register.

Horizontal padding is `{spacing.page}` in the app, 20px on phones, and up to 112px on the landing's lower sections. Sections are separated by `{spacing.section}`. Form fields stack at 22px. The register is a real table with a 3.5rem number column and the free width given to the title; at 640px and below each row restacks into a two-line entry (number beside title, then versions and last change). Search, role and sort sit on one line from 760px, with search taking its own line on phones. Interactive targets are at least 44px high (40px for in-line controls and menu items).

## Elevation & Depth

Depth is paper lying on paper. Surfaces are flat colour with grain; shadow appears only where one sheet lies over another, always tinted warm brown (rgb(70 20 12)) rather than grey, with a tight contact shadow plus a long soft fall. There are no raised cards and no glows.

### Shadow Vocabulary
- **Sheet** (`box-shadow: 0 1px 2px rgb(70 20 12 / 0.14), 0 22px 44px -26px rgb(70 20 12 / 0.45)`): the landing sheet on the ground.
- **Band edge** (`box-shadow: 0 12px 20px -14px rgb(70 16 8 / 0.45)`): the page band's edge lying on the register.
- **Slip** (`box-shadow: 0 2px 6px rgb(70 20 12 / 0.2), 0 24px 48px -16px rgb(70 20 12 / 0.5)`): dialogs and the palette. The menu and toasts use a slightly shorter fall (`0 2px 4px … / 0.18, 0 14px 30px -10px … / 0.4`).
- **Tag** (`box-shadow: 0 1px 2px rgb(70 20 12 / 0.3)`; hover `0 3px 6px rgb(70 20 12 / 0.35)`): washi tags and the dropzone; hovering lifts the slip slightly.
- **Turned corner** (`filter: drop-shadow(5px 8px 9px rgb(80 16 8 / 0.34))`): a lifted corner flap casting onto what lies under it.

### Named Rules
**The Washi Slip Rule.** Anything laid on top of a page (dialog, menu, palette, dropzone, toast, tag) is a square slip of washi with grain and a warm paper shadow. There are no cards.

**The Crease Rule.** Regions on the ground are divided by 1px Ground Crease lines, never by boxed panels or background tints. The register is ruled, the menu is separated, the tab rail is drawn, all with the same line.

## Shapes

Square paper. Every surface, button, tag, field and slip has a 0px corner, toasts included. Geometry comes from folding: triangular corner flaps cut with `clip-path`, a diagonal crease across the 20px wordmark mark, a turned corner on the landing's washi panel, and a small turned vermilion corner marking the palette's active option. The only round form is the gold dot.

Lines carry meaning by their form. A solid 2px rule is a live version, a dashed rule is withdrawn but kept, a 6px double rule is restored. Inserted words are underlined and removed words are struck (2px, in Ink Vermilion on the ground). Fields are a single 1.5px underline. An error is a short 14px struck rule beside its message.

## Components

### Buttons
Few and square; most actions are words or tags.
- **Shape:** square (0px).
- **Primary:** Ink Vermilion fill, fold-white 1.0625rem text at 500, 12px 22px padding, 48px high. One per view: sign in, create account, create document, open the demo workspace.
- **Hover / Focus:** fill deepens to Deep Ink Vermilion over 200ms `--ease-paper`; focus is the global 2px sumi outline at 3px offset. Pending states set `cursor: progress`.
- **Outline (landing Replay):** 1px Ink Vermilion border and text, transparent fill, an 8% Ink Vermilion wash on hover.

### Controls in words
- **Style:** sumi text at 500 with a resting 1px Ink Vermilion underline at 0.25em offset, so it reads as a control at rest; 40px target with -4px margin so the words align with the text above.
- **Hover:** the underline thickens to 2px. **Disabled:** Sumi Wash at 55% opacity.

### Tags (washi labels)
- **Style:** washi with ground grain and the tag shadow, sumi label text (0.9375rem, 500), 6px 12px padding, 36px high; the large tag is 44px with body text. Used for navigation, the palette trigger and the account menu trigger on the header band, and "New document" at the foot of the page band.
- **State:** hover deepens the shadow; the current page carries a 2px Ink Vermilion underline; focus is a 2px fold-white outline, visible against the band. A keyboard hint sits in a 1px sumi-tinted box inside the tag and hides on phones.

### Inputs / Fields
- **Style:** a ruled line, not a box: 1.5px sumi underline, transparent ground, 1.125rem input text, label above at 0.9375rem 500. Selects use the same line with a small sumi chevron; the textarea is lined paper, a faint rule under every 1.6em line.
- **Focus:** the line turns Ink Vermilion and doubles to 3px (border plus a 1.5px shadow), and the ground lightens to fold white at 60%. The browser outline is removed because the line carries focus.
- **Error:** the line turns Ink Vermilion; the message is written below in Ink Vermilion beside a 14px struck rule. Autofill keeps the washi ground and sumi ink.

### Navigation
- **Header band:** a vermilion band with the 24px wordmark at left and washi tags at right, ended by a fold-white crease (35% opacity). On phones the navigation wraps onto its own line.
- **Account menu:** a washi slip (min 250px) with a name and note at the top, crease separators, 40px items; the highlighted item lightens to fold white and is underlined in Ink Vermilion.
- **Palette:** a washi slip with a ruled search line at 1.375rem; matches underlined in Ink Vermilion; the active option is lightened and marked by a small turned vermilion corner.

### Dialogs
- **Style:** a washi slip up to 560px wide over a 42% sumi scrim, title at 2rem 300, tabs as words on a crease rail with a 2px Ink Vermilion rule under the active one.
- **Dropzone:** a washi slip edged in Ground Crease; hover or drag turns the edge Ink Vermilion and the ground fold white.

### Toasts
Washi slips with ground grain and the menu shadow, sumi text at 0.9375rem, square; error toasts set their text in Ink Vermilion.

### The Register (signature)
The documents index is a ruled register under the page band: a real table whose rows are ruled by crease lines, a sumi rule under the column heads, a strict number column in vermilion lining figures (1.5rem), the title at 1.125rem 500 underlined in Ink Vermilion on hover, the version label in Ink Vermilion with the gold dot beside documents changed in the last day, and a key to the dot above the table. Rows tint toward washi on hover over 160ms. While loading, the body fades to 60%.

### The Sheet and its Folds (signature)
The landing's square vermilion sheet carries its crease lines in fold white at 40% (dashed for a withdrawn version, doubled for a restored one). The margin column lists fold numbers 01–04 as a slider; the shown fold fills its number with vermilion. Its lower-right corner is the next action: a washi flap turned back over a cream ground, lifting 16° on its crease on hover or focus and 26° while pending. Changed words keep a short afterglow (1.9s) after each fold.

### Motion
One fold at a time, each panel rotating on its crease axis: about 420ms (`--duration-fold`) in two 210ms halves, lifting to 90° and laying back with a slight darkening at the edge. Corner flaps rotate in 3D on hover. State colour changes run 200ms on `--ease-paper` (cubic-bezier(0.45, 0, 0.25, 1)). Nothing slides or fades in from off-screen. Under `prefers-reduced-motion: reduce` transitions and the afterglow are removed and states swap directly.

## Do's and Don'ts

### Do:
- **Do** put only text of 24px or more on Sheet Vermilion; set anything smaller on a washi tag.
- **Do** use Ink Vermilion (#b42d22) for small red text, focus lines, error text and primary buttons.
- **Do** show state by line form: solid for live, dashed for withdrawn but kept, double for restored; underline inserted words and strike removed ones.
- **Do** draw fields as a single 1.5px underline that turns Ink Vermilion and thickens on focus, with errors written beside a short struck rule.
- **Do** divide regions on the ground with 1px Ground Crease lines.
- **Do** lay dialogs, menus, palettes, dropzones, toasts and tags on the page as square washi slips with grain and a warm brown shadow.
- **Do** underline every control in words in Ink Vermilion at rest.
- **Do** set compared numbers in lining tabular figures.
- **Do** move by folding on a crease, one fold at a time (about 420ms, `--ease-paper`), and swap states directly under reduced motion.

### Don't:
- **Don't** set text under 24px on Sheet Vermilion, or use Sheet Vermilion for small red text.
- **Don't** use colour alone to show a version's state.
- **Don't** use the gold dot for anything but "current", or use gold as a fill, border or text colour.
- **Don't** draw fields as boxes or use cards for content; use ruled lines and washi slips.
- **Don't** round corners; the gold dot is the only circle.
- **Don't** use grey or black shadows; paper shadows are warm brown (rgb(70 20 12)).
- **Don't** slide panels or content into place; things fold.
- **Don't** set display type bold; large type is weight 300.
