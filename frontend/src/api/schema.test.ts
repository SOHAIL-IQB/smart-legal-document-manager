// @vitest-environment node
// Phase 9 F2: the typed API client (schema.d.ts) is generated from the committed OpenAPI snapshot.
// This fails when the snapshot changed and `npm run gen:api` wasn't rerun.
import { execFileSync } from 'node:child_process'
import { mkdtempSync, readFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import path from 'node:path'

import { expect, test } from 'vitest'

const root = path.resolve(import.meta.dirname, '../..')

test('the committed API types match the OpenAPI snapshot', () => {
  const fresh = path.join(mkdtempSync(path.join(tmpdir(), 'inkstep-api-')), 'schema.d.ts')
  execFileSync(
    path.join(root, 'node_modules/.bin/openapi-typescript'),
    ['src/api/openapi.json', '-o', fresh],
    { cwd: root, stdio: 'pipe' },
  )
  const committed = readFileSync(path.join(root, 'src/api/schema.d.ts'), 'utf8')
  expect(committed, 'run `npm run gen:api` in frontend/').toBe(readFileSync(fresh, 'utf8'))
})
