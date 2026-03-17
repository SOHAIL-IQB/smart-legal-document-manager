# Curl Request Examples

These examples assume the API is running at `http://localhost:8000`.

## Create User

```bash
curl -X POST http://localhost:8000/users \
  -H "Content-Type: application/json" \
  -d '{"name":"Alice","email":"alice@example.com"}'
```

## Create Document

```bash
curl -X POST http://localhost:8000/documents \
  -H "Content-Type: application/json" \
  -d '{"title":"Employment Agreement","content":"This contract is valid for 1 year.","user_id":1}'
```

## Add Version

```bash
curl -X POST http://localhost:8000/documents/1/versions \
  -H "Content-Type: application/json" \
  -d '{"content":"This contract is valid for 2 years.","user_id":1}'
```

## Compare Versions

```bash
curl "http://localhost:8000/documents/1/compare?v1=1&v2=2"
```

## Update Title

```bash
curl -X PATCH http://localhost:8000/documents/1/title \
  -H "Content-Type: application/json" \
  -d '{"title":"Updated Employment Agreement"}'
```

## Delete Version

```bash
curl -X DELETE http://localhost:8000/documents/1/versions/2
```
