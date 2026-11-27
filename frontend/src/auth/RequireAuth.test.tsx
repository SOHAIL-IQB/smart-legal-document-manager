import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { createMemoryRouter, RouterProvider, useLocation } from 'react-router'
import { afterEach, expect, test, vi } from 'vitest'

import { RequireAuth } from './RequireAuth'

afterEach(() => vi.unstubAllGlobals())

function SignInProbe() {
  const location = useLocation()
  const from = (location.state as { from?: string } | null)?.from
  return <p>sign-in page, return to {from}</p>
}

function renderAt(path: string) {
  const router = createMemoryRouter(
    [
      { path: '/sign-in', element: <SignInProbe /> },
      {
        element: <RequireAuth />,
        children: [{ path: '/documents', element: <p>the documents</p> }],
      },
    ],
    { initialEntries: [path] },
  )
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
}

const meResponse = (status: number, body: unknown) =>
  vi.fn(async () => new Response(JSON.stringify(body), { status }))

test('a signed-out visitor goes to sign-in, remembering where they were going', async () => {
  vi.stubGlobal('fetch', meResponse(401, { error: { code: 'unauthorized', message: 'Not signed in.' } }))
  renderAt('/documents?q=lease')
  expect(await screen.findByText('sign-in page, return to /documents?q=lease')).toBeTruthy()
  expect(screen.queryByText('the documents')).toBeNull()
})

test('a signed-in user sees the page', async () => {
  vi.stubGlobal('fetch', meResponse(200, { id: 1, name: 'Asha', email: 'a@x.example', created_at: '2026-11-27T00:00:00Z' }))
  renderAt('/documents')
  expect(await screen.findByText('the documents')).toBeTruthy()
})

test('while the session is being checked, a status says so', () => {
  vi.stubGlobal('fetch', vi.fn(() => new Promise<Response>(() => {})))
  renderAt('/documents')
  expect(screen.getByRole('status').textContent).toMatch(/checking/i)
})
