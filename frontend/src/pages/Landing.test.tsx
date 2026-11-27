import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { afterEach, expect, test, vi } from 'vitest'

import { sessionKey } from '@/auth/session'

import { Landing } from './Landing'

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  vi.useRealTimers()
})

const asha = { id: 7, name: 'Asha Rao', email: 'asha-7@demo.example', created_at: '2026-11-27T00:00:00Z' }

type Call = { url: string; init: RequestInit }

/** Answers the session check and the demo endpoint; records every request. */
function stubApi({ signedIn = false } = {}) {
  const calls: Call[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init: RequestInit) => {
      calls.push({ url, init })
      if (url === '/api/auth/session') {
        return new Response(JSON.stringify({ user: signedIn ? asha : null }), { status: 200 })
      }
      if (url === '/api/demo/workspaces' && init.method === 'POST') {
        return new Response(
          JSON.stringify({
            user: asha,
            access_token: 't',
            token_type: 'bearer',
            expires_in: 43200,
            workspace: { id: 3, expires_at: '2026-11-28T00:00:00Z' },
            accounts: [],
          }),
          { status: 201 },
        )
      }
      return new Response('{}', { status: 404 })
    }),
  )
  return calls
}

function renderLanding() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const router = createMemoryRouter(
    [
      { path: '/', element: <Landing /> },
      { path: '/documents', element: <p>the documents</p> },
      { path: '/sign-in', element: <p>sign in</p> },
    ],
    { initialEntries: ['/'] },
  )
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
  return { client, router }
}

/** The clause as the sheet shows it at wide sizes (the copy on the ground is the same text). */
function sheetClause() {
  return within(screen.getByRole('figure'))
}

/** Let the folds run: each step is a timer scheduled by an effect, and effects flush per act(). */
async function settle(stepMs = 10, rounds = 16) {
  for (let i = 0; i < rounds; i++) {
    await act(async () => {
      await vi.advanceTimersByTimeAsync(stepMs)
    })
  }
}

function motionAllowed() {
  vi.stubGlobal('matchMedia', (query: string) => ({
    matches: false,
    media: query,
    addEventListener: () => {},
    removeEventListener: () => {},
  }))
}

test('the first viewport says what it is and offers the demo', async () => {
  stubApi()
  renderLanding()
  expect(screen.getByRole('heading', { level: 1, name: 'One sheet. Every fold kept.' })).toBeTruthy()
  // The corner of the sheet, and again at the close.
  expect(screen.getAllByRole('button', { name: /open your demo workspace/i })).toHaveLength(2)
  expect(screen.getByRole('link', { name: 'Sign in' }).getAttribute('href')).toBe('/sign-in')
  // Every figure on the page sits under a sample label: on the sheet, and on the excerpt below it.
  expect(screen.getAllByText('Sample text: Master Services Agreement — Contoso')).toHaveLength(2)
  // The headline comes before the introduction, at every width.
  const h1 = screen.getByRole('heading', { level: 1 })
  const intro = screen.getByText(/keeps every version of a contract/)
  expect(h1.compareDocumentPosition(intro) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
})

test('the sheet rests on the current version, its change marked', () => {
  stubApi()
  renderLanding()
  const slider = screen.getByRole('slider', { name: 'Versions of the sample agreement' })
  expect(slider.getAttribute('aria-valuenow')).toBe('4')
  expect(slider.getAttribute('aria-valuetext')).toBe(
    'Version 4 of 4: Asha Rao, Liability cap change rejected, restores version 2, current',
  )
  expect(sheetClause().getByText('twelve (12)').tagName).toBe('INS')
  expect(sheetClause().getByText('three (3)').tagName).toBe('DEL')
  expect(screen.getByRole('button', { name: 'Replay the history' })).toBeTruthy()
  // The gold dot marks the current version on the strip (narrow screens) and in its row (wide).
  const current = document.querySelectorAll('.folds__row')[3]
  expect(current.querySelector('.folds__dot.gold-dot')).toBeTruthy()
  expect(current.querySelector('.folds__current .gold-dot')).toBeTruthy()
})

test('the keys move through the folds, and each shows its own change', async () => {
  vi.useFakeTimers()
  stubApi()
  renderLanding()
  const slider = screen.getByRole('slider')

  const press = async (key: string) => {
    fireEvent.keyDown(slider, { key })
    await settle()
  }

  await press('Home')
  expect(slider.getAttribute('aria-valuenow')).toBe('1')
  expect(sheetClause().queryByRole('insertion')).toBeNull()
  expect(sheetClause().getByText(/available 99\.5% of each/)).toBeTruthy()

  await press('ArrowDown')
  expect(slider.getAttribute('aria-valuenow')).toBe('2')
  expect(slider.getAttribute('aria-valuetext')).toBe(
    'Version 2 of 4: Chloe Martin, Higher uptime; 45-day payment',
  )
  expect(sheetClause().getByText('99.5%').tagName).toBe('DEL')
  expect(sheetClause().getByText('99.9%').tagName).toBe('INS')

  await press('ArrowDown')
  expect(slider.getAttribute('aria-valuetext')).toContain('withdrawn and kept on the record')
  expect(sheetClause().getByText('three (3)').tagName).toBe('INS')

  await press('ArrowUp')
  expect(slider.getAttribute('aria-valuenow')).toBe('2')

  await press('End')
  expect(slider.getAttribute('aria-valuenow')).toBe('4')
  await press('ArrowDown') // already at the last fold
  expect(slider.getAttribute('aria-valuenow')).toBe('4')
})

test('the sheet folds one fold at a time and shows the clause each fold changes', async () => {
  vi.useFakeTimers()
  stubApi()
  renderLanding()
  const shownRow = () => document.querySelector('.folds__row[data-shown] .folds__number')?.textContent
  const seen = [shownRow()]
  fireEvent.keyDown(screen.getByRole('slider'), { key: 'Home' })
  for (let i = 0; i < 24; i++) {
    await act(async () => {
      await vi.advanceTimersToNextTimerAsync() // one timer, so one step, per look
    })
    if (seen.at(-1) !== shownRow()) seen.push(shownRow())
  }
  expect(seen).toEqual(['04', '03', '02', '01'])
  expect(sheetClause().getByText(/^3\. Service Levels/)).toBeTruthy()
  expect(sheetClause().queryByText(/Limitation of Liability/)).toBeNull()

  fireEvent.keyDown(screen.getByRole('slider'), { key: 'End' })
  await settle()
  expect(sheetClause().getByText(/Limitation of Liability/)).toBeTruthy()
  expect(sheetClause().queryByText(/Service Levels/)).toBeNull()
})

test('the sheet carries the crease of every fold up to the one it shows', async () => {
  vi.useFakeTimers()
  stubApi()
  renderLanding()
  const lit = () => document.querySelectorAll('.crease[data-on]').length
  expect(lit()).toBe(4)
  fireEvent.keyDown(screen.getByRole('slider'), { key: 'Home' })
  await settle()
  expect(lit()).toBe(1)
})

test('at rest it shows the current version; Replay folds through the whole history in order', async () => {
  vi.useFakeTimers()
  motionAllowed()
  stubApi()
  renderLanding()
  const slider = screen.getByRole('slider')
  expect(slider.getAttribute('aria-valuenow')).toBe('4')
  expect(sheetClause().getByText('twelve (12)').tagName).toBe('INS')

  fireEvent.click(screen.getByRole('button', { name: 'Replay the history' }))
  expect(screen.getByRole('button', { name: 'Stop' })).toBeTruthy()
  const seen: string[] = []
  for (let i = 0; i < 40; i++) {
    await settle(250, 1)
    const now = slider.getAttribute('aria-valuenow') ?? ''
    if (seen.at(-1) !== now) seen.push(now)
  }
  expect(seen).toEqual(['1', '2', '3', '4'])
  expect(screen.getByRole('button', { name: 'Replay the history' })).toBeTruthy()
})

test('choosing a fold stops the replay where the visitor chose', async () => {
  vi.useFakeTimers()
  motionAllowed()
  stubApi()
  renderLanding()
  fireEvent.click(screen.getByRole('button', { name: 'Replay the history' }))
  await settle(250, 8)
  fireEvent.keyDown(screen.getByRole('slider'), { key: 'End' })
  fireEvent.keyDown(screen.getByRole('slider'), { key: 'ArrowUp' })
  await settle(500, 20)
  expect(screen.getByRole('slider').getAttribute('aria-valuenow')).toBe('3')
  expect(screen.getByRole('button', { name: 'Replay the history' })).toBeTruthy()
})

test('changed words glow only after the sheet folds, not when the page opens', async () => {
  vi.useFakeTimers()
  stubApi()
  renderLanding()
  const glowing = () => document.querySelectorAll('.clause[data-glow]').length
  expect(glowing()).toBe(0)
  fireEvent.keyDown(screen.getByRole('slider'), { key: 'ArrowUp' })
  await settle()
  expect(glowing()).toBe(2) // the sheet's clause and the copy on the ground
})

test('opening the demo creates a workspace, signs in and goes to the documents', async () => {
  const calls = stubApi()
  const { client, router } = renderLanding()
  const [corner] = screen.getAllByRole('button', { name: /open your demo workspace/i })
  fireEvent.click(corner)

  expect(await screen.findByText('the documents')).toBeTruthy()
  expect(router.state.location.pathname).toBe('/documents')
  const create = calls.find((c) => c.url === '/api/demo/workspaces')
  expect(create?.init.method).toBe('POST')
  expect((create?.init.headers as Record<string, string>)['X-Requested-With']).toBe('XMLHttpRequest')
  expect(client.getQueryData(sessionKey)).toEqual(asha)
})

test('a signed-in visitor is offered their documents instead', async () => {
  stubApi({ signedIn: true })
  renderLanding()
  const links = await screen.findAllByRole('link', { name: /go to your documents/i })
  expect(links.length).toBe(2) // the corner and the close
  expect(links.every((link) => link.getAttribute('href') === '/documents')).toBe(true)
  expect(screen.queryByRole('button', { name: /open your demo workspace/i })).toBeNull()
})
