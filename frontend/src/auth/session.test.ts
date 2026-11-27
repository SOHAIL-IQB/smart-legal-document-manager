import { afterEach, expect, test, vi } from 'vitest'

import { ApiError } from '@/api/client'

import { fetchSession } from './session'

afterEach(() => vi.unstubAllGlobals())

const asha = { id: 1, name: 'Asha', email: 'a@x.example', created_at: '2026-11-27T00:00:00Z' }

function stub(status: number, body: unknown) {
  const fetch = vi.fn(async () => new Response(JSON.stringify(body), { status }))
  vi.stubGlobal('fetch', fetch)
  return fetch
}

test('asks the session endpoint, which answers 200 even when signed out', async () => {
  const fetch = stub(200, { user: null })
  expect(await fetchSession()).toBeNull()
  expect(fetch).toHaveBeenCalledWith('/api/auth/session', expect.objectContaining({ method: 'GET' }))
})

test('a signed-in user comes back as the user', async () => {
  stub(200, { user: asha })
  expect(await fetchSession()).toEqual(asha)
})

test('a 401 still means signed out', async () => {
  stub(401, { error: { code: 'unauthorized', message: 'Not signed in.' } })
  expect(await fetchSession()).toBeNull()
})

test('any other failure is an error, not "signed out"', async () => {
  stub(503, { error: { code: 'unavailable', message: 'Down.' } })
  await expect(fetchSession()).rejects.toBeInstanceOf(ApiError)
})
