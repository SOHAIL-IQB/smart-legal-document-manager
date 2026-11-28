import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { afterEach, expect, test, vi } from 'vitest'

import { sessionKey } from '@/auth/session'

import { SignIn } from './SignIn'
import { SignUp } from './SignUp'

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

const asha = { id: 7, name: 'Asha Rao', email: 'asha@example.com', created_at: '2026-11-28T00:00:00Z' }
const auth = { user: asha, access_token: 't', token_type: 'bearer', expires_in: 43200 }
const error = (status: number, code: string, message: string, details?: unknown) =>
  new Response(JSON.stringify({ error: { code, message, details, request_id: 'req-1' } }), { status })

type Call = { url: string; init: RequestInit }

/** The session check answers `signedIn`; every other request gets `answer`. */
function stubApi(answer: () => Response, { signedIn = false } = {}) {
  const calls: Call[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init: RequestInit) => {
      calls.push({ url, init })
      if (url === '/api/auth/session') {
        return new Response(JSON.stringify({ user: signedIn ? asha : null }), { status: 200 })
      }
      return answer()
    }),
  )
  return calls
}

function renderAt(path: string, state?: unknown) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const router = createMemoryRouter(
    [
      { path: '/sign-in', element: <SignIn /> },
      { path: '/sign-up', element: <SignUp /> },
      { path: '/documents', element: <p>the documents</p> },
      { path: '/account', element: <p>the account page</p> },
    ],
    { initialEntries: [{ pathname: path, state }] },
  )
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
  return { client, router, user: userEvent.setup() }
}

const body = (call: Call | undefined) => JSON.parse(String(call?.init.body))

// --- sign in ---------------------------------------------------------------------------------

test('sign in: labelled fields, and empty or malformed input is caught before any request', async () => {
  const calls = stubApi(() => new Response('{}', { status: 500 }))
  const { user } = renderAt('/sign-in')
  expect(screen.getByRole('heading', { level: 1, name: 'Sign in.' })).toBeTruthy()
  expect(document.title).toBe('Sign in · Inkstep')

  await user.click(screen.getByRole('button', { name: 'Sign in' }))
  const email = screen.getByLabelText('Email')
  expect(email.getAttribute('aria-invalid')).toBe('true')
  const describedBy = email.getAttribute('aria-describedby') ?? ''
  expect(document.getElementById(describedBy.split(' ')[0])?.textContent).toBe('Enter your email address.')
  expect(document.activeElement).toBe(email) // focus goes to the first problem
  expect(screen.getByLabelText('Password').getAttribute('aria-invalid')).toBe('true')

  await user.type(email, 'not-an-email')
  await user.click(screen.getByRole('button', { name: 'Sign in' }))
  expect(await screen.findByText('Enter a valid email address, like name@example.com.')).toBeTruthy()
  expect(calls.filter((c) => c.url !== '/api/auth/session')).toHaveLength(0)
})

test('sign in: success stores the session and returns to where the visitor was going', async () => {
  const calls = stubApi(() => new Response(JSON.stringify(auth), { status: 200 }))
  const { client, router, user } = renderAt('/sign-in', { from: '/account' })
  await user.type(screen.getByLabelText('Email'), 'asha@example.com')
  await user.type(screen.getByLabelText('Password'), 'correct horse')
  await user.click(screen.getByRole('button', { name: 'Sign in' }))

  expect(await screen.findByText('the account page')).toBeTruthy()
  expect(router.state.location.pathname).toBe('/account')
  const login = calls.find((c) => c.url === '/api/auth/login')
  expect(login?.init.method).toBe('POST')
  expect(body(login)).toEqual({ email: 'asha@example.com', password: 'correct horse' })
  expect((login?.init.headers as Record<string, string>)['X-Requested-With']).toBe('XMLHttpRequest')
  expect(client.getQueryData(sessionKey)).toEqual(asha)
})

test('sign in: without a place to return to, it opens the documents', async () => {
  stubApi(() => new Response(JSON.stringify(auth), { status: 200 }))
  const { user } = renderAt('/sign-in')
  await user.type(screen.getByLabelText('Email'), 'asha@example.com')
  await user.type(screen.getByLabelText('Password'), 'correct horse')
  await user.click(screen.getByRole('button', { name: 'Sign in' }))
  expect(await screen.findByText('the documents')).toBeTruthy()
})

test('sign in: a wrong password shows the API message and clears the password', async () => {
  stubApi(() => error(401, 'unauthorized', 'Incorrect email or password.'))
  const { user } = renderAt('/sign-in')
  await user.type(screen.getByLabelText('Email'), 'asha@example.com')
  await user.type(screen.getByLabelText('Password'), 'wrong one')
  await user.click(screen.getByRole('button', { name: 'Sign in' }))

  expect((await screen.findByRole('alert')).textContent).toContain('Incorrect email or password.')
  expect((screen.getByLabelText('Email') as HTMLInputElement).value).toBe('asha@example.com')
  expect((screen.getByLabelText('Password') as HTMLInputElement).value).toBe('')
})

test('sign in: too many attempts shows the API message with its wait', async () => {
  stubApi(() =>
    error(429, 'rate_limited', 'Too many failed sign-in attempts. Try again in 42 seconds.', {
      retry_after: 42,
    }),
  )
  const { user } = renderAt('/sign-in')
  await user.type(screen.getByLabelText('Email'), 'asha@example.com')
  await user.type(screen.getByLabelText('Password'), 'guess')
  await user.click(screen.getByRole('button', { name: 'Sign in' }))
  expect((await screen.findByRole('alert')).textContent).toContain('Try again in 42 seconds.')
})

test('sign in: a field error from the API keeps focus on that field', async () => {
  stubApi(() =>
    error(422, 'validation_error', 'Request validation failed.', [
      { field: 'email', message: 'value is not a valid email address' },
    ]),
  )
  const { user } = renderAt('/sign-in')
  await user.type(screen.getByLabelText('Email'), 'asha@example.com')
  await user.type(screen.getByLabelText('Password'), 'correct horse')
  await user.click(screen.getByRole('button', { name: 'Sign in' }))
  const email = screen.getByLabelText('Email')
  await waitFor(() => expect(email.getAttribute('aria-invalid')).toBe('true'))
  expect(document.activeElement).toBe(email)
})

test('sign in: the password can be shown and hidden', async () => {
  stubApi(() => new Response('{}', { status: 500 }))
  const { user } = renderAt('/sign-in')
  const password = screen.getByLabelText('Password')
  expect(password.getAttribute('type')).toBe('password')
  await user.click(screen.getByRole('button', { name: 'Show password' }))
  expect(password.getAttribute('type')).toBe('text')
  await user.click(screen.getByRole('button', { name: 'Hide password' }))
  expect(password.getAttribute('type')).toBe('password')
})

test('sign in: a visitor who is already signed in goes straight to their documents', async () => {
  stubApi(() => new Response('{}', { status: 500 }), { signedIn: true })
  renderAt('/sign-in')
  expect(await screen.findByText('the documents')).toBeTruthy()
})

test('sign in: offers an account and the demo instead', async () => {
  const calls = stubApi(() =>
    new Response(
      JSON.stringify({ ...auth, workspace: { id: 1, expires_at: '2026-11-29T00:00:00Z' }, accounts: [] }),
      { status: 201 },
    ),
  )
  const { user } = renderAt('/sign-in', { from: '/account' })
  expect(screen.getByRole('link', { name: 'Create an account' }).getAttribute('href')).toBe('/sign-up')
  const demo = screen.getByRole('button', { name: 'Open a demo workspace instead' })
  expect(demo.getAttribute('aria-describedby')).toBeTruthy()
  await user.click(demo)
  expect(await screen.findByText('the account page')).toBeTruthy()
  expect(calls.some((c) => c.url === '/api/demo/workspaces' && c.init.method === 'POST')).toBe(true)
})

// --- sign up ---------------------------------------------------------------------------------

test('sign up: name, email and a password of at least 8 characters are checked first', async () => {
  const calls = stubApi(() => new Response('{}', { status: 500 }))
  const { user } = renderAt('/sign-up')
  expect(screen.getByRole('heading', { level: 1, name: 'Create an account.' })).toBeTruthy()
  expect(document.title).toBe('Create an account · Inkstep')
  await user.type(screen.getByLabelText('Email'), 'bob@example.com')
  await user.type(screen.getByLabelText('Password'), 'short')
  await user.click(screen.getByRole('button', { name: 'Create account' }))

  expect(screen.getByLabelText('Name').getAttribute('aria-invalid')).toBe('true')
  expect(await screen.findByText('Enter your name.')).toBeTruthy()
  expect(screen.getByText('Use at least 8 characters.')).toBeTruthy()
  expect(calls.filter((c) => c.url !== '/api/auth/session')).toHaveLength(0)
})

test('sign up: success creates the account, stores the session and opens the documents', async () => {
  const calls = stubApi(() => new Response(JSON.stringify(auth), { status: 201 }))
  const { client, user } = renderAt('/sign-up')
  await user.type(screen.getByLabelText('Name'), '  Asha Rao ')
  await user.type(screen.getByLabelText('Email'), 'asha@example.com')
  await user.type(screen.getByLabelText('Password'), 'correct horse')
  await user.click(screen.getByRole('button', { name: 'Create account' }))

  expect(await screen.findByText('the documents')).toBeTruthy()
  expect(body(calls.find((c) => c.url === '/api/auth/register'))).toEqual({
    name: 'Asha Rao',
    email: 'asha@example.com',
    password: 'correct horse',
  })
  expect(client.getQueryData(sessionKey)).toEqual(asha)
})

test('sign up: a taken email is reported on the email field', async () => {
  stubApi(() => error(409, 'conflict', 'An account with this email already exists.'))
  const { user } = renderAt('/sign-up')
  await user.type(screen.getByLabelText('Name'), 'Asha')
  await user.type(screen.getByLabelText('Email'), 'asha@example.com')
  await user.type(screen.getByLabelText('Password'), 'correct horse')
  await user.click(screen.getByRole('button', { name: 'Create account' }))

  const email = screen.getByLabelText('Email')
  await waitFor(() => expect(email.getAttribute('aria-invalid')).toBe('true'))
  const id = (email.getAttribute('aria-describedby') ?? '').split(' ')[0]
  expect(document.getElementById(id)?.textContent).toBe('An account with this email already exists.')
  expect(screen.getByRole('link', { name: 'Sign in' }).getAttribute('href')).toBe('/sign-in')
})

test('sign up: field errors from the API land on their fields', async () => {
  stubApi(() =>
    error(422, 'validation_error', 'Request validation failed.', [
      { field: 'name', message: 'Value error, the name contains a NUL character' },
    ]),
  )
  const { user } = renderAt('/sign-up')
  await user.type(screen.getByLabelText('Name'), 'Asha')
  await user.type(screen.getByLabelText('Email'), 'asha@example.com')
  await user.type(screen.getByLabelText('Password'), 'correct horse')
  await user.click(screen.getByRole('button', { name: 'Create account' }))

  const name = screen.getByLabelText('Name')
  await waitFor(() => expect(name.getAttribute('aria-invalid')).toBe('true'))
  expect(screen.getByText('Value error, the name contains a NUL character')).toBeTruthy()
})

test('sign up: a failure with no field to blame shows the message and its reference', async () => {
  stubApi(() => error(500, 'internal_error', 'Something went wrong on our side.'))
  const { user } = renderAt('/sign-up')
  await user.type(screen.getByLabelText('Name'), 'Asha')
  await user.type(screen.getByLabelText('Email'), 'asha@example.com')
  await user.type(screen.getByLabelText('Password'), 'correct horse')
  await user.click(screen.getByRole('button', { name: 'Create account' }))
  const alert = await screen.findByRole('alert')
  expect(alert.textContent).toContain('Something went wrong on our side.')
  expect(alert.textContent).toContain('Reference: req-1')
})
