import { render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import App from './App'

afterEach(() => vi.unstubAllGlobals())

function stubFetch(status: number, body: unknown) {
  const fetchMock = vi.fn(async () => new Response(JSON.stringify(body), { status }))
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

test('shows that the API is ready, asking it through the same-origin /api path', async () => {
  const fetchMock = stubFetch(200, { status: 'ok', database: 'ok' })
  render(<App />)
  expect(await screen.findByText('API ready · database ok')).toBeTruthy()
  expect(fetchMock).toHaveBeenCalledWith('/api/health/ready', expect.anything())
})

test('says so when the API is down', async () => {
  stubFetch(503, { error: { code: 'unavailable', message: 'The database is not reachable.' } })
  render(<App />)
  expect(await screen.findByText(/API unavailable: .*HTTP 503/)).toBeTruthy()
})
