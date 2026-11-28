import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { afterEach, expect, test, vi } from 'vitest'

import { routes } from './routes'

afterEach(() => vi.unstubAllGlobals())

function renderAt(path: string) {
  const router = createMemoryRouter(routes, { initialEntries: [path] })
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
}

test('an unknown address shows the not-found page', () => {
  renderAt('/no/such/page')
  expect(screen.getByRole('heading', { name: "This page doesn't exist" })).toBeTruthy()
})

test('the signed-in area is behind the guard', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => new Response(JSON.stringify({ user: null }), { status: 200 })),
  )
  renderAt('/account')
  expect(await screen.findByRole('heading', { level: 1, name: 'Sign in.' })).toBeTruthy()
})
