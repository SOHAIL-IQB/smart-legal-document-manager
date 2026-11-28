import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { afterEach, expect, test, vi } from 'vitest'

import { AppLayout } from '@/app/AppLayout'
import { sessionKey } from '@/auth/session'

import { DocumentPage } from './DocumentPage'

afterEach(() => vi.unstubAllGlobals())

// --- a fake API holding the sample agreement's real history --------------------------------------

type Role = 'owner' | 'editor' | 'viewer'
const asha = { id: 1, name: 'Asha Rao', email: 'asha@demo.example', created_at: '2026-11-27T00:00:00Z' }
const HOUR = 3600_000
const ago = (hours: number) => new Date(Date.now() - hours * HOUR).toISOString()

const TEXT_1 = '3. Service Levels. Provider will make the platform available 99.5% of each calendar month.'
const TEXT_2 = '3. Service Levels. Provider will make the platform available 99.9% of each calendar month.'
const TEXT_3 = '3. Service Levels. Provider will make the platform available 99.0% of each calendar month.'

function version(n: number, extra: Record<string, unknown> = {}) {
  return {
    id: 100 + n,
    version_number: n,
    edited_by: 1,
    edited_by_name: 'Asha Rao',
    change_note: null,
    content_hash: `h${n}`,
    created_at: ago(10 - n),
    source: 'manual',
    source_filename: null,
    restored_from: null,
    word_count: 14,
    is_deleted: false,
    deleted_at: null,
    deleted_by: null,
    ...extra,
  }
}

type Call = { method: string; url: string; body: unknown }

function fakeApi({ role = 'owner' as Role } = {}) {
  const calls: Call[] = []
  const state = {
    title: 'Master Services Agreement — Contoso',
    versions: [
      version(1),
      version(2, { edited_by_name: 'Chloe Martin', change_note: 'Higher uptime; 45-day payment' }),
      version(3, {
        edited_by_name: 'Chloe Martin',
        change_note: 'Draft: lower liability cap',
        is_deleted: true,
        deleted_at: ago(2),
        deleted_by: 1,
      }),
      // 04 restores 02's text, so it carries 02's hash, as in the real sample.
      version(4, { source: 'restore', restored_from: 2, content_hash: 'h2', change_note: 'Liability cap change rejected' }),
    ],
    texts: { 1: TEXT_1, 2: TEXT_2, 3: TEXT_3, 4: TEXT_2 } as Record<number, string>,
    members: [
      { user_id: 1, name: 'Asha Rao', email: 'asha@demo.example', role: 'owner', added_at: ago(10) },
      { user_id: 3, name: 'Chloe Martin', email: 'chloe@demo.example', role: 'editor', added_at: ago(9) },
    ],
    compare: { approximate: false, identical: false },
  }
  const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status })
  const problem = (status: number, code: string, message: string) =>
    json({ error: { code, message, request_id: 'req-7' } }, status)
  const live = () => state.versions.filter((v) => !v.is_deleted)
  const summary = () => ({
    id: 9,
    title: state.title,
    created_at: ago(10),
    updated_at: ago(1),
    created_by: 1,
    created_by_name: 'Asha Rao',
    my_role: role,
    latest_version: live().at(-1)!.version_number,
    version_count: live().length,
    word_count: 14,
  })
  const addVersion = (content: string, extra: Record<string, unknown>) => {
    const n = state.versions.length + 1
    state.versions.push(version(n, { created_at: new Date().toISOString(), ...extra }))
    state.texts[n] = content
    return n
  }

  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init: RequestInit = {}) => {
      const method = (init.method ?? 'GET').toUpperCase()
      const body = typeof init.body === 'string' ? JSON.parse(init.body) : init.body
      calls.push({ method, url, body })
      const u = new URL(url, 'http://x')
      const path = u.pathname
      if (path === '/api/auth/session') return json({ user: asha })
      if (path === '/api/demo/workspaces/current') return problem(404, 'not_found', 'Not a demo account.')
      if (path === '/api/documents/9' && method === 'GET') return json(summary())
      if (path === '/api/documents/9/title' && method === 'PATCH') {
        state.title = (body as { title: string }).title
        return json(summary())
      }
      if (path === '/api/documents/9/versions' && method === 'GET') {
        return json(u.searchParams.get('include_deleted') === 'true' ? state.versions : live())
      }
      if (path === '/api/documents/9/versions' && method === 'POST') {
        const { content, change_note } = body as { content: string; change_note?: string }
        if (content === state.texts[live().at(-1)!.version_number]) {
          return json({ document_id: 9, version: null, message: 'No changes; nothing was saved.' })
        }
        const n = addVersion(content, { change_note: change_note ?? null })
        return json({ document_id: 9, version: n, message: `Version ${n} saved.` }, 201)
      }
      if (path === '/api/documents/9/versions/upload' && method === 'POST') {
        const form = body as FormData
        const file = form.get('file') as File
        const n = addVersion('uploaded text', {
          source: 'upload',
          source_filename: file.name,
          change_note: form.get('change_note'),
        })
        return json({ document_id: 9, version: n, message: `Version ${n} saved.` }, 201)
      }
      const restore = path.match(/^\/api\/documents\/9\/versions\/(\d+)\/restore$/)
      if (restore && method === 'POST') {
        const from = Number(restore[1])
        const n = addVersion(state.texts[from], { source: 'restore', restored_from: from })
        return json({ document_id: 9, version: n, message: `Version ${n} saved.` }, 201)
      }
      const one = path.match(/^\/api\/documents\/9\/versions\/(\d+)$/)
      if (one) {
        const n = Number(one[1])
        const v = state.versions.find((x) => x.version_number === n)!
        if (method === 'DELETE') {
          if (live().length <= 1) return problem(409, 'conflict', 'A document must keep at least one version.')
          Object.assign(v, { is_deleted: true, deleted_at: new Date().toISOString(), deleted_by: 1 })
          return json({ message: `Version ${n} deleted.` })
        }
        if (v.is_deleted) return problem(410, 'gone', `Version ${n} was deleted.`)
        return json({ ...v, content: state.texts[n] })
      }
      if (path === '/api/documents/9/compare') {
        const [v1, v2] = [Number(u.searchParams.get('v1')), Number(u.searchParams.get('v2'))]
        const collapsed = u.searchParams.has('context')
        const rows = [
          ...(collapsed
            ? [{ type: 'skip', skipped: 6, old_line: null, new_line: null, old_text: null, new_text: null, old_segments: null, new_segments: null, whitespace_only: false }]
            : [{ type: 'equal', old_line: 1, new_line: 1, old_text: 'MASTER SERVICES AGREEMENT', new_text: 'MASTER SERVICES AGREEMENT', old_segments: null, new_segments: null, skipped: null, whitespace_only: false }]),
          {
            type: 'replace',
            old_line: 7,
            new_line: 7,
            old_text: TEXT_1,
            new_text: TEXT_2,
            old_segments: [
              { op: 'equal', text: '3. Service Levels. Provider will make the platform available ' },
              { op: 'delete', text: '99.5%' },
              { op: 'equal', text: ' of each calendar month.' },
            ],
            new_segments: [
              { op: 'equal', text: '3. Service Levels. Provider will make the platform available ' },
              { op: 'insert', text: '99.9%' },
              { op: 'equal', text: ' of each calendar month.' },
            ],
            skipped: null,
            whitespace_only: false,
          },
        ]
        return json({
          document_id: 9,
          version_1: v1,
          version_2: v2,
          version_1_meta: state.versions[v1 - 1],
          version_2_meta: state.versions[v2 - 1],
          before: '',
          after: '',
          changes: [],
          has_meaningful_changes: true,
          approximate: state.compare.approximate,
          stats: state.compare.identical
            ? { lines_added: 0, lines_removed: 0, lines_changed: 0, words_added: 0, words_removed: 0 }
            : { lines_added: 0, lines_removed: 0, lines_changed: 1, words_added: 1, words_removed: 1 },
          rows,
        })
      }
      if (path === '/api/documents/9/activity') {
        return json({
          total: 8,
          limit: 20,
          offset: 0,
          items: [
            { id: 8, action: 'member.role_changed', actor_id: 1, actor_name: 'Asha Rao', created_at: ago(0.5), details: { user_id: 3, name: 'Chloe Martin', from: 'viewer', to: 'editor' } },
            { id: 7, action: 'document.renamed', actor_id: 1, actor_name: 'Asha Rao', created_at: ago(1), details: { from: 'MSA', to: 'Master Services Agreement — Contoso' } },
            { id: 6, action: 'version.deleted', actor_id: 1, actor_name: 'Asha Rao', created_at: ago(2), details: { version: 3 } },
            { id: 5, action: 'version.restored', actor_id: 1, actor_name: 'Asha Rao', created_at: ago(3), details: { version: 4, restored_from: 2, change_note: 'Liability cap change rejected' } },
            { id: 4, action: 'version.created', actor_id: 3, actor_name: 'Chloe Martin', created_at: ago(30), details: { version: 3, source: 'upload', source_filename: 'msa-draft.docx' } },
            { id: 3, action: 'member.added', actor_id: 1, actor_name: 'Asha Rao', created_at: ago(31), details: { user_id: 3, name: 'Chloe Martin', role: 'viewer' } },
            { id: 2, action: 'member.removed', actor_id: 2, actor_name: 'Ben Carter', created_at: ago(32), details: { user_id: 2, name: 'Ben Carter', left: true } },
            { id: 1, action: 'document.created', actor_id: 1, actor_name: 'Asha Rao', created_at: ago(40), details: { title: 'MSA', version: 1, source: 'manual' } },
          ],
        })
      }
      if (path === '/api/documents/9/members' && method === 'GET') return json(state.members)
      if (path === '/api/documents/9/members' && method === 'POST') {
        const { email, role: newRole } = body as { email: string; role: Role }
        if (email === 'nobody@example.com') return problem(404, 'not_found', 'No account uses that email address.')
        const member = { user_id: 2, name: 'Ben Carter', email, role: newRole, added_at: new Date().toISOString() }
        state.members.push(member)
        return json(member, 201)
      }
      const memberPath = path.match(/^\/api\/documents\/9\/members\/(\d+)$/)
      if (memberPath) {
        const id = Number(memberPath[1])
        if (method === 'PATCH') {
          const m = state.members.find((x) => x.user_id === id)!
          m.role = (body as { role: Role }).role
          return json(m)
        }
        if (method === 'DELETE') {
          state.members = state.members.filter((x) => x.user_id !== id)
          return json({ message: 'Removed.' })
        }
      }
      return problem(404, 'not_found', `No fake for ${method} ${path}`)
    }),
  )
  return { calls, state }
}

function renderAt(path = '/documents/9') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  client.setQueryData(sessionKey, asha)
  const router = createMemoryRouter(
    [
      {
        element: <AppLayout />,
        children: [
          { path: '/documents', element: <p>the register</p> },
          { path: '/documents/:documentId', element: <DocumentPage /> },
        ],
      },
    ],
    { initialEntries: [path] },
  )
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
  return { router, user: userEvent.setup() }
}

const column = () => screen.getByRole('list', { name: 'Versions' })
const versionItems = () => within(column()).getAllByRole('listitem')
const reading = () => screen.getByRole('article', { name: /^Version \d+/ })

// --- reading -----------------------------------------------------------------------------------

test('it opens on the current version, with every version in the margin column', async () => {
  const { calls } = fakeApi()
  renderAt()
  expect(await screen.findByRole('heading', { level: 1, name: 'Master Services Agreement — Contoso.' })).toBeTruthy()
  expect(document.title).toBe('Master Services Agreement — Contoso · Inkstep')
  expect(document.querySelector('.tag--label')?.textContent).toBe('Your role: Owner')

  await waitFor(() => expect(versionItems()).toHaveLength(4))
  const [v4, v3, v2] = versionItems()
  expect(within(v4).getByText('04')).toBeTruthy()
  expect(v4.getAttribute('data-state')).toBe('restored')
  expect(within(v4).getByText(/restores 02/)).toBeTruthy()
  expect(within(v4).getByText('current')).toBeTruthy() // beside the gold dot
  expect(v3.getAttribute('data-state')).toBe('withdrawn')
  expect(within(v3).getByText(/withdrawn/)).toBeTruthy()
  expect(v2.getAttribute('data-state')).toBe('live')
  expect(within(v4).getByRole('link').getAttribute('aria-current')).toBe('true')

  expect(await within(reading()).findByText(TEXT_2)).toBeTruthy()
  expect(within(reading()).getByText(/Liability cap change rejected/)).toBeTruthy()
  expect(calls.some((c) => c.url.includes('/versions?include_deleted=true'))).toBe(true)
})

test('choosing a version in the column reads it; a withdrawn one says its text is gone', async () => {
  fakeApi()
  const { router, user } = renderAt()
  await waitFor(() => expect(versionItems()).toHaveLength(4))

  await user.click(within(versionItems()[2]).getByRole('link'))
  expect(router.state.location.search).toBe('?v=2')
  expect(await within(reading()).findByText(TEXT_2)).toBeTruthy()
  expect(within(versionItems()[2]).getByRole('link').getAttribute('aria-current')).toBe('true')

  await user.click(within(versionItems()[1]).getByRole('link'))
  expect(await within(reading()).findByText(/withdrawn by Asha Rao/i)).toBeTruthy()
  expect(within(reading()).getByText(/still on the record/i)).toBeTruthy()
})

// --- writing ------------------------------------------------------------------------------------

test('New version edits in place from the current text, then reads the version saved', async () => {
  const { calls } = fakeApi({ role: 'editor' })
  const { router, user } = renderAt()
  await user.click(await screen.findByRole('button', { name: 'New version' }))
  const editor = await screen.findByLabelText('Text of the new version')
  expect((editor as HTMLTextAreaElement).value).toBe(TEXT_2)

  await user.clear(editor)
  await user.type(editor, 'Changed text.')
  await user.type(screen.getByLabelText('Change note (optional)'), 'Shorter clause')
  await user.click(screen.getByRole('button', { name: 'Save version 5' }))

  await waitFor(() => expect(router.state.location.search).toBe('?v=5'))
  expect(calls.find((c) => c.method === 'POST' && c.url === '/api/documents/9/versions')?.body).toEqual({
    content: 'Changed text.',
    change_note: 'Shorter clause',
  })
  expect(await within(reading()).findByText('Changed text.')).toBeTruthy()
  expect(screen.queryByLabelText('Text of the new version')).toBeNull()
})

test('saving the same text saves nothing, and says so', async () => {
  fakeApi({ role: 'editor' })
  const { user } = renderAt()
  await user.click(await screen.findByRole('button', { name: 'New version' }))
  await screen.findByLabelText('Text of the new version')
  await user.click(screen.getByRole('button', { name: 'Save version 5' }))
  expect((await screen.findByRole('status', { name: 'Editor status' })).textContent).toContain(
    'Nothing changed, so no version was saved.',
  )
})

test('a viewer reads and compares but sees no way to write', async () => {
  fakeApi({ role: 'viewer' })
  renderAt('/documents/9?v=2')
  await within(await screen.findByRole('article')).findByText(TEXT_2)
  expect(screen.queryByRole('button', { name: 'New version' })).toBeNull()
  expect(screen.queryByRole('button', { name: 'Upload version' })).toBeNull()
  expect(screen.queryByRole('button', { name: 'Rename' })).toBeNull()
  expect(screen.queryByRole('button', { name: /restore/i })).toBeNull()
  expect(screen.queryByRole('button', { name: /withdraw/i })).toBeNull()
})

test('restoring an earlier version adds it as a new one', async () => {
  const { calls } = fakeApi({ role: 'editor' })
  const { router, user } = renderAt('/documents/9?v=1')
  await within(await screen.findByRole('article')).findByText(TEXT_1)
  expect(screen.queryByRole('button', { name: /withdraw/i })).toBeNull() // owners only
  await user.click(screen.getByRole('button', { name: 'Restore as version 5' }))
  await waitFor(() => expect(router.state.location.search).toBe('?v=5'))
  expect(calls.some((c) => c.method === 'POST' && c.url === '/api/documents/9/versions/1/restore')).toBe(true)
  expect(await within(reading()).findByText(TEXT_1)).toBeTruthy()
})

test('an owner withdraws a version after confirming, and it stays on the record', async () => {
  const { calls } = fakeApi()
  const { user } = renderAt('/documents/9?v=2')
  await within(await screen.findByRole('article')).findByText(TEXT_2)
  await user.click(screen.getByRole('button', { name: 'Withdraw version 2' }))
  const dialog = await screen.findByRole('alertdialog', { name: 'Withdraw version 2?' })
  expect(within(dialog).getByText(/stays in the history and the activity log/)).toBeTruthy()
  await user.click(within(dialog).getByRole('button', { name: 'Withdraw' }))

  await waitFor(() => expect(versionItems()[2].getAttribute('data-state')).toBe('withdrawn'))
  expect(calls.some((c) => c.method === 'DELETE' && c.url === '/api/documents/9/versions/2')).toBe(true)
})

test('upload a file as a new version, with a note', async () => {
  const { calls } = fakeApi({ role: 'editor' })
  const { router, user } = renderAt()
  await user.click(await screen.findByRole('button', { name: 'Upload version' }))
  const dialog = await screen.findByRole('dialog', { name: 'Upload a new version' })
  await user.upload(within(dialog).getByLabelText(/choose a file/i), new File(['x'], 'msa-v5.docx'))
  await user.type(within(dialog).getByLabelText('Change note (optional)'), 'Countersigned copy')
  await user.click(within(dialog).getByRole('button', { name: 'Upload as version 5' }))

  await waitFor(() => expect(router.state.location.search).toBe('?v=5'))
  const post = calls.find((c) => c.url === '/api/documents/9/versions/upload')!
  expect(((post.body as FormData).get('file') as File).name).toBe('msa-v5.docx')
  expect((post.body as FormData).get('change_note')).toBe('Countersigned copy')
})

// --- comparing ---------------------------------------------------------------------------------

test('Compare opens on the current version against the nearest earlier text that differs', async () => {
  const { calls } = fakeApi()
  const { router, user } = renderAt()
  await user.click(await screen.findByRole('tab', { name: 'Compare' }))
  expect(router.state.location.search).toBe('?tab=compare')

  // 04 restores 02 (the same text), so the first useful comparison is 01 against 04.
  const table = await screen.findByRole('table', { name: 'Version 1 compared with version 4' })
  const compare = calls.filter((c) => c.url.startsWith('/api/documents/9/compare')).at(-1)!
  expect(Object.fromEntries(new URL(compare.url, 'http://x').searchParams)).toEqual({ v1: '1', v2: '4', context: '3' })
  expect(within(table).getByText('99.5%').tagName).toBe('DEL')
  expect(within(table).getByText('99.9%').tagName).toBe('INS')
  expect(screen.getByText(/1 word added, 1 word removed/)).toBeTruthy()
  expect(within(table).getByText('6 unchanged lines')).toBeTruthy()

  await user.click(screen.getByRole('checkbox', { name: 'Show every line' }))
  expect(await within(table).findAllByText('MASTER SERVICES AGREEMENT')).toHaveLength(2) // an unchanged line, both sides
  expect(new URL(calls.at(-1)!.url, 'http://x').searchParams.has('context')).toBe(false)
})

test('the margin column picks the pair; the selects do the same; withdrawn versions are not offered', async () => {
  fakeApi()
  const { router, user } = renderAt('/documents/9?tab=compare')
  await screen.findByRole('table')
  await user.click(within(versionItems()[3]).getByRole('button', { name: 'Compare from version 1' }))
  await waitFor(() => expect(router.state.location.search).toBe('?tab=compare&from=1&to=4'))
  expect(await screen.findByRole('table', { name: 'Version 1 compared with version 4' })).toBeTruthy()
  expect(within(versionItems()[1]).queryByRole('button', { name: /compare/i })).toBeNull() // 03 is withdrawn

  const to = screen.getByRole('combobox', { name: 'To' }) as HTMLSelectElement
  expect(Array.from(to.options).map((o) => o.value)).toEqual(['4', '2', '1'])
  await user.selectOptions(to, '2')
  expect(await screen.findByRole('table', { name: 'Version 1 compared with version 2' })).toBeTruthy()
})

test('two identical texts say so, rather than a count of nothing', async () => {
  const { state } = fakeApi()
  state.compare.identical = true
  renderAt('/documents/9?tab=compare&from=2&to=4')
  expect(await screen.findByText('The two texts are identical.')).toBeTruthy()
})

test('an approximate comparison says so in words', async () => {
  const { state } = fakeApi()
  state.compare.approximate = true
  renderAt('/documents/9?tab=compare')
  expect((await screen.findByRole('note')).textContent).toMatch(/approximate/i)
})

// --- activity, sharing, renaming ---------------------------------------------------------------

test('activity reads as sentences', async () => {
  fakeApi()
  const { user } = renderAt()
  await user.click(await screen.findByRole('tab', { name: 'Activity' }))
  const log = await screen.findByRole('list', { name: 'Activity' })
  const lines = within(log)
    .getAllByRole('listitem')
    .map((li) => li.querySelector('.activity__what')?.textContent)
  expect(lines).toEqual([
    'Asha Rao made Chloe Martin an editor',
    'Asha Rao renamed it from “MSA” to “Master Services Agreement — Contoso”',
    'Asha Rao withdrew version 3',
    'Asha Rao restored version 2 as version 4: “Liability cap change rejected”',
    'Chloe Martin saved version 3 from msa-draft.docx',
    'Asha Rao shared it with Chloe Martin as a viewer',
    'Ben Carter left the document',
    'Asha Rao created it as version 1',
  ])
})

test('an owner shares by email, changes a role and removes a member', async () => {
  const { calls } = fakeApi()
  const { user } = renderAt()
  await user.click(await screen.findByRole('button', { name: 'Share' }))
  const dialog = await screen.findByRole('dialog', { name: 'Share this document' })
  const people = await within(dialog).findByRole('list', { name: 'People with access' })
  expect(within(people).getAllByRole('listitem')).toHaveLength(2)

  await user.type(within(dialog).getByLabelText('Email'), 'nobody@example.com')
  await user.click(within(dialog).getByRole('button', { name: 'Add' }))
  expect((await within(dialog).findByText('No account uses that email address.')).className).toContain('field__error')

  await user.clear(within(dialog).getByLabelText('Email'))
  await user.type(within(dialog).getByLabelText('Email'), 'ben@demo.example')
  await user.selectOptions(within(dialog).getByRole('combobox', { name: 'Role for the new person' }), 'viewer')
  await user.click(within(dialog).getByRole('button', { name: 'Add' }))
  await waitFor(() => expect(within(people).getAllByRole('listitem')).toHaveLength(3))
  expect(calls.filter((c) => c.method === 'POST' && c.url.endsWith('/members')).at(-1)?.body).toEqual({
    email: 'ben@demo.example',
    role: 'viewer',
  })

  await user.selectOptions(within(dialog).getByRole('combobox', { name: 'Role for Chloe Martin' }), 'viewer')
  await waitFor(() => expect(calls.some((c) => c.method === 'PATCH' && c.url.endsWith('/members/3'))).toBe(true))
  await user.click(within(dialog).getByRole('button', { name: 'Remove Chloe Martin' }))
  await waitFor(() => expect(within(people).getAllByRole('listitem')).toHaveLength(2))
})

test('a viewer sees who has access but cannot change it', async () => {
  fakeApi({ role: 'viewer' })
  const { user } = renderAt()
  await user.click(await screen.findByRole('button', { name: 'Share' }))
  const dialog = await screen.findByRole('dialog', { name: 'Who has access' })
  await within(dialog).findByText('Chloe Martin')
  expect(within(dialog).queryByLabelText('Email')).toBeNull()
  expect(within(dialog).queryAllByRole('combobox')).toHaveLength(0)
  expect(within(dialog).getByRole('button', { name: 'Leave this document' })).toBeTruthy()
})

test('rename changes the title in the band', async () => {
  const { calls } = fakeApi({ role: 'editor' })
  const { user } = renderAt()
  await user.click(await screen.findByRole('button', { name: 'Rename' }))
  const dialog = await screen.findByRole('dialog', { name: 'Rename' })
  const field = within(dialog).getByLabelText('Title')
  await user.clear(field)
  await user.type(field, 'MSA — Contoso (2026)')
  await user.click(within(dialog).getByRole('button', { name: 'Save title' }))
  expect(await screen.findByRole('heading', { level: 1, name: 'MSA — Contoso (2026).' })).toBeTruthy()
  expect(calls.find((c) => c.method === 'PATCH')?.body).toEqual({ title: 'MSA — Contoso (2026)' })
})

test('a document you can’t see reads as not found', async () => {
  fakeApi()
  renderAt('/documents/77')
  expect(await screen.findByRole('heading', { name: 'This document isn’t available' })).toBeTruthy()
  expect(screen.getByRole('link', { name: 'Back to your documents' }).getAttribute('href')).toBe('/documents')
})
