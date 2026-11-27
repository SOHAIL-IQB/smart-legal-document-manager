# Inkstep frontend

React + Vite + TypeScript, built to the Phase 9 spec (`../docs/specs/phase-9-frontend-build.md`) in the
Folding Sequence world (`../.impeccable/surfaces/`). Node 26 (`.nvmrc`).

| Purpose | Command |
|---|---|
| Install (no install scripts) | `npm ci --ignore-scripts` |
| Dev server (proxies `/api` to the API on port 8000) | `npm run dev` |
| Typecheck · lint · test · build | `npm run typecheck` · `npm run lint` · `npm test` · `npm run build` |
| Refresh the typed API client after an API change | from the repository root: `python -m scripts.export_openapi`, then `npm run gen:api` here |
