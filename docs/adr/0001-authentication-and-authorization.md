# ADR 0001 — Authentication and per-document authorization

- Status: accepted (2026-11-22)
- Phase: 2

## Context

The original API had no authentication: every request carried a `user_id` in its body, so any
client could act as any user (audit defect B1). The product handles legal documents, so both
*who you are* and *what you may do with a given document* must be enforced by the server.

## Threat model (STRIDE, condensed)

Trust boundary: every HTTP request to `/api/*`. Assets: document content, version history,
membership lists, user credentials.

| Threat | Abuse case | Control |
|---|---|---|
| Spoofing | Send someone else's id; replay or forge a token | Identity comes only from a signed JWT (HS256, server secret). `user_id` removed from all request bodies. Tokens expire. |
| Spoofing | Guess passwords | Argon2id hashes; login limited to 10 failed attempts per IP+email per 15 min (429). |
| Spoofing | Learn which emails are registered from login errors or timing | Same error message for unknown email and wrong password; a dummy hash is verified for unknown emails so timing matches. |
| Tampering | Another site makes the browser POST with the user's cookie (CSRF) | Cookie is `SameSite=Lax` and `httpOnly`; unsafe requests authenticated by cookie must also send `X-Requested-With: XMLHttpRequest`, which a cross-site form cannot set and CORS blocks for scripts. |
| Repudiation | "I didn't change that clause" | `edited_by` is taken from the token, not the client. Full activity log arrives in Phase 6. |
| Information disclosure | Read a document you weren't shared on by guessing ids (IDOR) | Every document route resolves the caller's membership; non-members get **404**, not 403, so ids can't be probed. `GET /users` (list of every account) is removed. |
| Information disclosure | Token stolen by injected script | Browser token lives only in an `httpOnly` cookie; the frontend never stores it in `localStorage`. |
| Denial of service | Huge passwords to burn CPU in Argon2 | Password length capped at 128. |
| Elevation of privilege | Viewer edits; editor deletes; owner removes the last owner | Role checked server-side on every route (matrix below). Last-owner guard on demote/remove. |

## Decision

1. **Credentials:** email + password. Passwords hashed with Argon2id via `pwdlib` (recommended params).
   Length 8–128.
2. **Token:** a stateless JWT (`sub`, `iat`, `exp`, `typ=access`), HS256, lifetime 12 h, signed
   with `SECRET_KEY` from the environment. In production the app refuses to start unless
   `SECRET_KEY` is set and at least 32 characters.
3. **Transport:** login/register set the token in a cookie (`httpOnly`, `SameSite=Lax`,
   `Secure` in production, `Max-Age` = token lifetime). The token is also returned in the
   response body so API clients (Swagger, curl) can send `Authorization: Bearer …`.
   The bundled frontend uses only the cookie.
4. **Roles per document:** `owner > editor > viewer`, stored in `document_members`.
   The creator becomes owner. A document can have several owners; it must always keep at least one.

| Action | viewer | editor | owner |
|---|:-:|:-:|:-:|
| Read document, versions, compare, member list | ✓ | ✓ | ✓ |
| Add version, rename | | ✓ | ✓ |
| Delete a version, delete the document | | | ✓ |
| Add / change / remove members | | | ✓ |
| Leave a document (remove yourself) | ✓ | ✓ | ✓ (not if last owner) |

## Consequences and known limits

- **Logout is client-side**: it clears the cookie, but a copied token stays valid until it expires
  (max 12 h). Server-side revocation (a token version column) is a possible later addition.
- **The login rate limiter is in-memory**, so it is per process. That is fine for the single-process
  deployment here; with several instances it must move to a shared store such as Redis.
- **Owners can learn whether an email is registered** when sharing (a 404 says no account exists).
  That trade-off is accepted for usability; it is limited to signed-in owners.
- Existing documents get their creator backfilled as owner by migration `0002`. Existing users get
  an unusable password hash and must be re-created (there were no real users).
