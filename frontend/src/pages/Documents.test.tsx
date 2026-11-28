import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { afterEach, expect, test, vi } from 'vitest'

import { AppLayout } from '@/app/AppLayout'
import { sessionKey } from '@/auth/session'

import { Documents } from './Documents'

afterEach(() => vi.unstubAllGlobals())

const asha = { id: 1, name: 'Asha Rao', email: 'asha@demo.example', created_at: '2026-11-27T00:00:00Z' }
const ben = { id: 2, name: 'Ben Carter', email: 'ben@demo.example', created_at: '2026-11-27T00:00:00Z' }
const HOUR = 3600_000

function doc(id: number, title: string, overrides: Record<string, unknown> = {}) {
  return {
    id,
    title,
    created_at: '2026-11-01T00:00:00Z',
    updated_at: new Date(Date.now() - 72 * HOUR).toISOString(),
    created_by: 1,
    created_by_name: 'Asha Rao',
    my_role: 'owner',
    latest_version: 2,
    version_count: 2,
    word_count: 420,
    ...overrides,
  }
}

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status })
const problem = (status: number, code: string, message: string) =>
  json({ error: { code, message, request_id: 'req-9' } }, status)

type Call = { url: string; init: RequestInit }
type Handler = (url: string, init: RequestInit) => Response | undefined

/** A fake API: the session, an optional demo workspace, and whatever `handler` answers. */
function stubApi(handler: Handler, { demo = false } = {}) {
  const calls: Call[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init: RequestInit = {}) => {
      calls.push({ url, init })
      const answer = handler(url, init)
      if (answer) return answer
      if (url === '/api/auth/session') return json({ user: asha })
      if (url === '/api/demo/workspaces/current') {
        return demo
          ? json({
              workspace: { id: 5, expires_at: new Date(Date.now() + 20 * HOUR).toISOString() },
              accounts: [
                { user_id: 1, name: 'Asha Rao', email: asha.email },
                { user_id: 2, name: 'Ben Carter', email: ben.email },
                { user_id: 3, name: 'Chloe Martin', email: 'chloe@demo.example' },
              ],
            })
          : problem(404, 'not_found', 'You are not in a demo workspace.')
      }
      return json({ items: [], total: 0, limit: 20, offset: 0 })
    }),
  )
  return calls
}

const listCalls = (calls: Call[]) => calls.filter((c) => c.url.startsWith('/api/documents?'))
const lastList = (calls: Call[]) => new URL(listCalls(calls).at(-1)!.url, 'http://x').searchParams

function renderAt(path = '/documents') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  client.setQueryData(sessionKey, asha)
  const router = createMemoryRouter(
    [
      {
        element: <AppLayout />,
        children: [
          { path: '/documents', element: <Documents /> },
          { path: '/documents/:id', element: <p>a document page</p> },
          { path: '/notifications', element: <p>notifications</p> },
          { path: '/account', element: <p>account</p> },
        ],
      },
      { path: '/', element: <p>the landing page</p> },
    ],
    { initialEntries: [path] },
  )
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
  return { client, router, user: userEvent.setup() }
}

// --- the register -----------------------------------------------------------------------------

test('the register: a captioned table of numbered rows, each opening its document', async () => {
  stubApi((url) =>
    url.startsWith('/api/documents?')
      ? json({
          items: [
            doc(11, 'Master Services Agreement', {
              latest_version: 4,
              version_count: 3,
              updated_at: new Date(Date.now() - 2 * HOUR).toISOString(),
            }),
            doc(12, 'Mutual NDA', { my_role: 'editor', created_by_name: 'Ben Carter' }),
          ],
          total: 2,
          limit: 20,
          offset: 0,
        })
      : undefined,
  )
  renderAt()
  const table = await screen.findByRole('table', { name: /your documents/i })
  expect(screen.getByRole('heading', { level: 1, name: 'Documents.' })).toBeTruthy()
  expect(document.title).toBe('Documents · Inkstep')
  const headers = within(table).getAllByRole('columnheader').map((h) => h.textContent)
  expect(headers).toEqual(['No.', 'Document', 'Your role', 'Versions', 'Words', 'Last change'])

  const rows = within(table).getAllByRole('row').slice(1)
  expect(rows).toHaveLength(2)
  expect(within(rows[0]).getByText('01')).toBeTruthy()
  const link = within(rows[0]).getByRole('link', { name: 'Master Services Agreement' })
  expect(link.getAttribute('href')).toBe('/documents/11')
  expect(within(rows[0]).getByText('v4')).toBeTruthy()
  expect(within(rows[0]).getByText(/changed in the last day/i)).toBeTruthy() // the gold dot, in words
  expect(within(rows[0]).getByTitle('Changed in the last day')).toBeTruthy()
  expect(screen.getByText('changed in the last day')).toBeTruthy() // the visible key to the dot
  expect(within(rows[1]).queryByText(/changed in the last day/i)).toBeNull()
  expect(within(rows[1]).getByText('by Ben Carter')).toBeTruthy()
  expect(screen.getByRole('status').textContent).toBe('2 documents')
})

test('the address drives the request, so Back and shared links keep the view', async () => {
  const calls = stubApi(() => undefined)
  renderAt('/documents?q=lease&role=editor&sort=title&order=asc&page=3')
  await waitFor(() => expect(listCalls(calls)).toHaveLength(1))
  const params = lastList(calls)
  expect(Object.fromEntries(params)).toEqual({
    q: 'lease',
    role: 'editor',
    sort: 'title',
    order: 'asc',
    limit: '20',
    offset: '40',
  })
  expect((screen.getByRole('searchbox', { name: 'Search documents' }) as HTMLInputElement).value).toBe('lease')
  expect((screen.getByRole('combobox', { name: 'Your role' }) as HTMLSelectElement).value).toBe('editor')
  expect((screen.getByRole('combobox', { name: 'Sort by' }) as HTMLSelectElement).value).toBe('title:asc')
})

test('searching, filtering and sorting go back to the first page', async () => {
  const calls = stubApi(() => undefined)
  const { router, user } = renderAt('/documents?page=2')
  await waitFor(() => expect(listCalls(calls)).toHaveLength(1))

  await user.type(screen.getByRole('searchbox', { name: 'Search documents' }), 'lease')
  await waitFor(() => expect(lastList(calls).get('q')).toBe('lease'))
  expect(lastList(calls).get('offset')).toBe('0')
  expect(router.state.location.search).toBe('?q=lease')

  await user.selectOptions(screen.getByRole('combobox', { name: 'Your role' }), 'owner')
  await waitFor(() => expect(lastList(calls).get('role')).toBe('owner'))

  await user.selectOptions(screen.getByRole('combobox', { name: 'Sort by' }), 'created_at:desc')
  await waitFor(() => expect(lastList(calls).get('sort')).toBe('created_at'))
  expect(lastList(calls).get('order')).toBe('desc')
  expect(lastList(calls).get('q')).toBe('lease')
})

test('pages of 20, with the range and Previous and Next', async () => {
  const calls = stubApi((url) => {
    if (!url.startsWith('/api/documents?')) return undefined
    const offset = Number(new URL(url, 'http://x').searchParams.get('offset'))
    const items = Array.from({ length: offset === 40 ? 5 : 20 }, (_, i) => doc(offset + i + 1, `Contract ${offset + i + 1}`))
    return json({ items, total: 45, limit: 20, offset })
  })
  const { user } = renderAt()
  expect(await screen.findByText('1–20 of 45')).toBeTruthy()
  expect(screen.getByRole('button', { name: 'Previous page' }).hasAttribute('disabled')).toBe(true)

  await user.click(screen.getByRole('button', { name: 'Next page' }))
  expect(await screen.findByText('21–40 of 45')).toBeTruthy()
  expect(lastList(calls).get('offset')).toBe('20')
  expect(within(screen.getAllByRole('row')[1]).getAllByRole('cell')[0].textContent).toBe('21') // numbering continues

  await user.click(screen.getByRole('button', { name: 'Next page' }))
  expect(await screen.findByText('41–45 of 45')).toBeTruthy()
  expect(screen.getByRole('button', { name: 'Next page' }).hasAttribute('disabled')).toBe(true)
})

test('empty: a first document is offered; a search with no match can be cleared', async () => {
  stubApi(() => undefined)
  const { router, user } = renderAt()
  expect(await screen.findByText('No documents yet.')).toBeTruthy()
  expect(screen.getAllByRole('button', { name: 'New document' }).length).toBeGreaterThan(0)

  await user.type(screen.getByRole('searchbox', { name: 'Search documents' }), 'zebra')
  expect(await screen.findByText('Nothing matches “zebra”.')).toBeTruthy()
  await user.click(screen.getByRole('button', { name: 'Clear the search' }))
  await waitFor(() => expect(router.state.location.search).toBe(''))
})

test('a failure shows the API message, its reference and a retry', async () => {
  let fail = true
  const calls = stubApi((url) =>
    url.startsWith('/api/documents?') && fail ? problem(500, 'internal_error', 'Something went wrong on our side.') : undefined,
  )
  const { user } = renderAt()
  const alert = await screen.findByRole('alert')
  expect(alert.textContent).toContain('Something went wrong on our side.')
  expect(alert.textContent).toContain('Reference: req-9')
  fail = false
  await user.click(within(alert).getByRole('button', { name: 'Try again' }))
  expect(await screen.findByText('No documents yet.')).toBeTruthy()
  expect(listCalls(calls).length).toBeGreaterThan(1)
})

// --- a new document ----------------------------------------------------------------------------

test('new document from pasted text: title and text, then it opens', async () => {
  const calls = stubApi((url, init) =>
    url === '/api/documents' && init.method === 'POST' ? json({ document_id: 31, version: 1 }, 201) : undefined,
  )
  const { router, user } = renderAt()
  await user.click((await screen.findAllByRole('button', { name: 'New document' }))[0])
  const dialog = await screen.findByRole('dialog', { name: 'New document' })
  await user.click(within(dialog).getByRole('tab', { name: 'Paste text' }))

  await user.click(within(dialog).getByRole('button', { name: 'Create document' }))
  expect(within(dialog).getByText('Give it a title.')).toBeTruthy()
  expect(within(dialog).getByText('Paste or type the text.')).toBeTruthy()

  await user.type(within(dialog).getByLabelText('Title'), 'Supply Agreement')
  await user.type(within(dialog).getByLabelText('Text'), '1. Supply. Seller supplies the goods.')
  await user.click(within(dialog).getByRole('button', { name: 'Create document' }))

  await waitFor(() => expect(router.state.location.pathname).toBe('/documents/31'))
  const post = calls.find((c) => c.url === '/api/documents')
  expect(JSON.parse(String(post?.init.body))).toEqual({
    title: 'Supply Agreement',
    content: '1. Supply. Seller supplies the goods.',
  })
})

test('new document from a file: checked first, sent as multipart, then it opens', async () => {
  const calls = stubApi((url, init) =>
    url === '/api/documents/upload' && init.method === 'POST' ? json({ document_id: 32, version: 1 }, 201) : undefined,
  )
  const { router } = renderAt()
  // Drag-and-drop and "All files" reach the page past the picker's `accept` list, so check it here.
  const user = userEvent.setup({ applyAccept: false })
  await user.click((await screen.findAllByRole('button', { name: 'New document' }))[0])
  const dialog = await screen.findByRole('dialog', { name: 'New document' })
  const input = within(dialog).getByLabelText(/choose a file/i) as HTMLInputElement

  await user.upload(input, new File(['x'], 'photo.png', { type: 'image/png' }))
  expect(within(dialog).getByText('Choose a PDF, Word (.docx) or text (.txt) file.')).toBeTruthy()

  const big = new File(['x'], 'big.pdf', { type: 'application/pdf' })
  Object.defineProperty(big, 'size', { value: 11 * 1024 * 1024 })
  await user.upload(input, big)
  expect(within(dialog).getByText('This file is larger than 10 MB.')).toBeTruthy()

  await user.upload(input, new File(['Lease text'], 'Lease.txt', { type: 'text/plain' }))
  expect(within(dialog).getByText('Lease.txt')).toBeTruthy()
  await user.click(within(dialog).getByRole('button', { name: 'Upload and create' }))

  await waitFor(() => expect(router.state.location.pathname).toBe('/documents/32'))
  const post = calls.find((c) => c.url === '/api/documents/upload')
  const body = post?.init.body as FormData
  expect((body.get('file') as File).name).toBe('Lease.txt')
  expect(post?.init.headers).toMatchObject({ 'X-Requested-With': 'XMLHttpRequest' })
})

test('an upload the server refuses shows its reason in the dialog', async () => {
  stubApi((url) =>
    url === '/api/documents/upload'
      ? problem(422, 'unprocessable', 'This PDF has no text to read; it may be a scan.')
      : undefined,
  )
  const { user } = renderAt()
  await user.click((await screen.findAllByRole('button', { name: 'New document' }))[0])
  const dialog = await screen.findByRole('dialog', { name: 'New document' })
  await user.upload(within(dialog).getByLabelText(/choose a file/i), new File(['%PDF'], 'scan.pdf', { type: 'application/pdf' }))
  await user.click(within(dialog).getByRole('button', { name: 'Upload and create' }))
  expect((await within(dialog).findByRole('alert')).textContent).toContain('it may be a scan')
})

// --- the palette -------------------------------------------------------------------------------

test('⌘K or Ctrl+K opens the palette; arrows and Enter open a document', async () => {
  const calls = stubApi((url) => {
    if (url.startsWith('/api/documents?') && new URL(url, 'http://x').searchParams.get('limit') === '8') {
      return json({ items: [doc(11, 'Master Services Agreement'), doc(14, 'Master Lease')], total: 2, limit: 8, offset: 0 })
    }
    return undefined
  })
  const { router, user } = renderAt()
  await screen.findByRole('heading', { level: 1 })
  await user.keyboard('{Control>}k{/Control}')
  const dialog = await screen.findByRole('dialog', { name: 'Jump to a document' })
  const box = within(dialog).getByRole('combobox', { name: 'Document title' })
  expect(box.getAttribute('aria-expanded')).toBe('false')

  await user.type(box, 'mast')
  const options = await within(dialog).findAllByRole('option')
  expect(options.map((o) => o.textContent)).toEqual(['Master Services Agreement', 'Master Lease'])
  expect(box.getAttribute('aria-expanded')).toBe('true')
  expect(new URL(calls.filter((c) => c.url.includes('limit=8')).at(-1)!.url, 'http://x').searchParams.get('q')).toBe('mast')

  await user.keyboard('{ArrowDown}')
  expect(box.getAttribute('aria-activedescendant')).toBe(options[1].id)
  expect(options[1].getAttribute('aria-selected')).toBe('true')
  await user.keyboard('{Enter}')
  await waitFor(() => expect(router.state.location.pathname).toBe('/documents/14'))
})

// --- the header --------------------------------------------------------------------------------

test('the header: where you are, and Sign out', async () => {
  const calls = stubApi((url, init) =>
    url === '/api/auth/logout' && init.method === 'POST' ? new Response(null, { status: 204 }) : undefined,
  )
  const { client, router, user } = renderAt()
  const nav = await screen.findByRole('navigation', { name: 'Main' })
  expect(within(nav).getByRole('link', { name: 'Documents' }).getAttribute('aria-current')).toBe('page')

  await user.click(screen.getByRole('button', { name: /account menu/i }))
  const menu = await screen.findByRole('menu')
  expect(within(menu).queryByRole('menuitem', { name: /switch to/i })).toBeNull() // a real account
  await user.click(within(menu).getByRole('menuitem', { name: 'Sign out' }))
  await waitFor(() => expect(router.state.location.pathname).toBe('/'))
  expect(calls.some((c) => c.url === '/api/auth/logout')).toBe(true)
  expect(client.getQueryData(sessionKey)).toBeNull()
})

test('a demo visitor can switch to the workspace’s other people', async () => {
  const calls = stubApi(
    (url, init) =>
      url === '/api/demo/workspaces/current/switch' && init.method === 'POST'
        ? json({ user: ben, access_token: 't', token_type: 'bearer', expires_in: 43200 })
        : undefined,
    { demo: true },
  )
  const { client, user } = renderAt()
  await user.click(await screen.findByRole('button', { name: /account menu/i }))
  const menu = await screen.findByRole('menu')
  expect(within(menu).getByText(/demo workspace/i)).toBeTruthy()
  expect(within(menu).getAllByRole('menuitem', { name: /switch to/i }).map((i) => i.textContent)).toEqual([
    'Switch to Ben Carter',
    'Switch to Chloe Martin',
  ])
  await user.click(within(menu).getByRole('menuitem', { name: 'Switch to Ben Carter' }))
  await waitFor(() => expect(client.getQueryData(sessionKey)).toEqual(ben))
  const post = calls.find((c) => c.url === '/api/demo/workspaces/current/switch')
  expect(JSON.parse(String(post?.init.body))).toEqual({ user_id: 2 })
  expect(await screen.findByRole('button', { name: /account menu.*ben carter/i })).toBeTruthy()
})
