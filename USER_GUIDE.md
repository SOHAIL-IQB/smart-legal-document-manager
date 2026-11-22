# User Guide

This walks through every API feature with `curl`. It assumes the API runs at
`http://localhost:8000` (see the README). Interactive docs are at `http://localhost:8000/api/docs`.

The examples use bearer tokens. Browsers use the session cookie instead, and must send
`X-Requested-With: XMLHttpRequest` on requests that change data.

```bash
API=http://localhost:8000/api
```

## 1. Create two accounts

```bash
ALICE=$(curl -s -X POST $API/auth/register -H "Content-Type: application/json" \
  -d '{"name":"Alice","email":"alice@example.com","password":"correct horse battery"}' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')

BOB=$(curl -s -X POST $API/auth/register -H "Content-Type: application/json" \
  -d '{"name":"Bob","email":"bob@example.com","password":"correct horse battery"}' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')
```

Passwords must be 8–128 characters. Signing in later: `POST /auth/login` with
`{"email", "password"}`. Ten failed attempts for one email within 15 minutes returns `429`.

## 2. Create a document

```bash
curl -s -X POST $API/documents -H "Authorization: Bearer $ALICE" \
  -H "Content-Type: application/json" \
  -d '{"title":"Service Agreement","content":"This contract is valid for 1 year."}'
# {"document_id":1,"version":1}
```

Alice is now the document's **owner**. Bob can't see it yet; for him it returns `404`:

```bash
curl -s $API/documents/1 -H "Authorization: Bearer $BOB"
```

## 3. Share it

```bash
curl -s -X POST $API/documents/1/members -H "Authorization: Bearer $ALICE" \
  -H "Content-Type: application/json" -d '{"email":"bob@example.com","role":"editor"}'
```

Roles: `viewer` (read), `editor` (read + add versions + rename), `owner` (everything, including
sharing and deleting). Change a role with `PATCH /documents/1/members/{user_id}`; remove someone
with `DELETE /documents/1/members/{user_id}`. A document always keeps at least one owner.

## 4. Add a version

```bash
curl -s -X POST $API/documents/1/versions -H "Authorization: Bearer $BOB" \
  -H "Content-Type: application/json" -d '{"content":"This contract is valid for 2 years."}'
# {"message":"Version created","document_id":1,"version":2}
```

- Identical content returns `200` with `"No changes detected"` and creates nothing.
- The editor is taken from the token, so the history can't be forged.
- If the change is meaningful (not just whitespace), a notification is sent in the background.

## 5. History and comparison

```bash
curl -s $API/documents/1/versions -H "Authorization: Bearer $ALICE"
curl -s "$API/documents/1/compare?v1=1&v2=2" -H "Authorization: Bearer $ALICE"
```

## 6. Rename and delete

```bash
curl -s -X PATCH $API/documents/1/title -H "Authorization: Bearer $BOB" \
  -H "Content-Type: application/json" -d '{"title":"Master Service Agreement"}'

curl -s -X DELETE $API/documents/1/versions/2 -H "Authorization: Bearer $ALICE"     # owner only
curl -s -X DELETE "$API/documents/1?confirm=true" -H "Authorization: Bearer $ALICE"  # owner only
```

## Errors

Every error has the same shape:

```json
{"error": {"code": "forbidden", "message": "This action needs the owner role; your role is editor."}}
```

Codes: `bad_request`, `unauthorized`, `forbidden`, `not_found`, `conflict`, `validation_error`
(with `details` per field), `rate_limited`, `internal_error`.
