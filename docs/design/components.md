# Component candidates (Phase 8, D5)

Sourced from 21st.dev on 2026-11-27 for Inkstep's screens, after the visual world was locked (the
Folding Sequence, `.impeccable/surfaces/frontend-src-pages-landing-tsx.md`).

**Rules for every part:**
- **Behavior and structure come from the catalog; the look comes from the world.** impeccable treats
  an unrestyled stock component inside a committed world as a defect. Every candidate is rebuilt in
  the fold language: washi cream ground, vermilion for large fields only, sumi text, crease-line
  borders, state by line form (solid live, dashed withdrawn, doubled restored) and the gold dot for
  "now".
- **Motion follows the contract:** one fold at a time, nothing slides, reduced motion respected.
  Springy, tilting and sliding effects in the candidates are removed.
- **Accessibility target:** WCAG 2.2 AA (`PRODUCT.md`).

**How far each candidate was checked:**
- The 21st.dev free tier allows two full-code retrievals per day.
- Two candidates were read in code: the share dialog and the documents table. They are marked
  **verified**.
- The rest were judged from their catalog descriptions only. They are marked **claimed**, and their
  code must be checked when Phase 9 installs them.

**License (resolved 2026-11-27, Phase 9 F0).** The [21st.dev Terms of Service](https://21st.dev/terms)
(last updated July 20, 2026) say:
- Marketplace code is "the sole and exclusive property of their respective authors and 21st Labs
  Inc.", for use "solely through the official 21st.dev platform".
- Redistribution "without authorization", or without a visible link back to the component page, is
  prohibited.
- The terms don't say whether a public repository counts, or how a component's own license
  (sometimes MIT) interacts with them.

**Decision:** no catalog code is copied into this public repository. The candidates below are
**design references** for behavior, structure and wording. Every part is built by us on shadcn
(open-source Radix primitives) with npm packages under their own open-source licenses (`motion`,
`sonner`, `lucide-react`). That also matches impeccable's rule that every element is rebuilt in the
world's vocabulary.

**New dependencies these imply:** `motion` or `framer-motion`, `lucide-react`, `sonner`. Each needs
the owner's approval in the Phase 9 spec (`AGENTS.md`).

## Decisions per part

| Part | Choice | Source | Accessibility | Fit and adaptation |
|---|---|---|---|---|
| Documents list (search, role filter, sort, pages) | **Data Table** by arihantcodes | [21st #27049](https://21st.dev/@arihantcodes_1f7b8c4d/components/data-table) | **Verified:** a real `<table>` with `<thead>` and `<th scope>`, `aria-sort`, arrow, Home and End keys with `aria-activedescendant`, an `aria-live` status, a selection checkbox, reduced-motion support | Becomes the **dense numbered index**: each contract a row with its version count as fold numbers and the gold dot on recently changed ones. Drop animated reordering and quick-filter pills; keep sorting, search, keyboard navigation. Server-side pagination (`limit`, `offset`) replaces client paging. Its 88 KB of code is heavy, so take only what the index uses |
| Jump to a document (⌘K) | **Command Palette** by vovalopuh13 | [21st #46285](https://21st.dev/@vovalopuh13/components/command-palette) | **Claimed:** combobox and listbox semantics; arrows, Home, End, Enter, Esc | Searches documents through `GET /documents?q=`. Remove the cursor-tilting preview pane (against the motion grammar). Matched letters stay underlined: a form cue, not colour |
| Side-by-side comparison | **Build our own** | — | Our own: rows as a semantic table; changes marked by underline and strike as well as colour; "approximate" announced as text | No catalog diff is for prose: every result is a code diff (accept or reject hunks, AI patches). The backend already returns rows with word segments. They render as two panels of the sheet, the fold language carrying state |
| Version history (the margin column) | **Build our own** | — | Our own: an ordered list with `aria-current` on the current version; dashed and doubled states also named in text | This is the world's signature interaction (fold and unfold along the margin, replay), so it can't be a stock timeline |
| Activity log | **Timeline** by kuratlielia, structure only | [21st #35051](https://21st.dev/@kuratlielia/components/timeline) | **Claimed:** expandable rows | Grouped-by-day feed with expandable detail fits the append-only log. Remove the animated drawing connector and slide-in inserts; the connector becomes a crease line |
| Notifications inbox | **Notification Inbox Popover** by ruixen.ui | [21st #8245](https://21st.dev/@ruixen.ui/components/notification-inbox-popover) | **Claimed:** tabs, bold for unread, dot indicator | Matches the API exactly: All and Unread, mark all read, unread count. Unread is shown by weight and a dot, not colour alone. Alternative: uvain's Notification Panel (#27135) has a "seen vs dealt with" state the backend doesn't model |
| File upload (PDF, DOCX, TXT) | **File Dropzone** by amankaushik481 | [21st #47199](https://21st.dev/@amankaushik481/components/file-dropzone) | **Claimed:** screen-reader announcements; type and size validation; retry | Single file. The server's own refusals (413 too large, 415 wrong type, 422 unreadable with the reason, 503 busy with retry) appear inline in the zone. Remove image previews |
| Share dialog (invite by email, owner, editor, viewer) | **Share Dialog** by uvain: wording and layout only, **rebuilt** | [21st #26993](https://21st.dev/@uvain/components/share-file-dialog) | **Verified, with gaps:** `role="dialog"`, an `aria-live` status, Escape. **But** no `aria-modal`, no focus trap, no `<label>`s, no email-type input, and a `role="menu"` role picker with no arrow-key handling | Keep its wording ("says what each choice actually does") and its information design. Rebuild on shadcn's Radix Dialog (focus trap, modal semantics) with a labelled email input and a Radix Select for the role. Remove "anyone with the link": the product has no public links |
| Sign in and sign up | **Build our own** on shadcn form primitives | Pattern reference: [21st #26677](https://21st.dev/@shadcnspace/components/field-01-sign-in-form) | Our own: labels, inline errors tied with `aria-describedby`, a password visibility toggle | Two short forms; the catalog ones bring social sign-in the product doesn't have, or TanStack Form instead of the planned react-hook-form + zod. The demo-workspace action is primary; sign-in is secondary |
| Toasts (saved, restored, errors with request ID) | **Toast Notification** (Sonner) by ghaerdi | [21st #46222](https://21st.dev/@ghaerdi/components/toast) | **Claimed:** Sonner uses an `aria-live` region | Brief confirmations ("Version 5 saved"); errors keep the API's message and request ID. Toasts appear in place, without sliding (motion grammar) |
| Landing page sheet and folds | **Build our own** | — | Our own: the sheet is decorative over real text; the primary action is a real link | The direction contract's first viewport; no catalog component exists or should |

## Status of the open items (Phase 9 F0, 2026-11-27)

1. License: **resolved.** No catalog code is copied (see above).
2. Code checks of the "claimed" candidates: **no longer needed.** No catalog code is used. Their
   accessibility claims become requirements our own builds must meet, and the Phase 9 tests check
   them (keyboard, labels, focus, live regions).
3. Dependencies: **approved** with the Phase 9 spec (LOG 026).
