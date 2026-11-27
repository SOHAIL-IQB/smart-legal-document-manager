import { afterEach, describe, expect, test, vi } from 'vitest'

import { api, ApiError } from './client'

afterEach(() => vi.unstubAllGlobals())

function stubFetch(response: Response | Error | DOMException) {
  const fetchMock = vi.fn(async () => {
    if (!(response instanceof Response)) throw response // DOMException isn't an Error in jsdom
    return response
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

const json = (status: number, body: unknown, headers: Record<string, string> = {}) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json', ...headers },
  })

function sent(fetchMock: ReturnType<typeof stubFetch>) {
  const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit]
  return { url, init, headers: init.headers as Record<string, string> }
}

describe('requests', () => {
  test('reads go to /api on the same origin, without the CSRF header', async () => {
    const fetchMock = stubFetch(json(200, { id: 1 }))
    await expect(api('/auth/me')).resolves.toEqual({ id: 1 })
    const { url, init, headers } = sent(fetchMock)
    expect(url).toBe('/api/auth/me')
    expect(init.method).toBe('GET')
    expect(init.credentials).toBe('same-origin')
    expect(headers['X-Requested-With']).toBeUndefined()
  })

  test('writes send JSON and the X-Requested-With header the API requires', async () => {
    const fetchMock = stubFetch(json(201, { document_id: 7 }))
    await api('/documents', { method: 'POST', body: { title: 'NDA', content: 'Text' } })
    const { init, headers } = sent(fetchMock)
    expect(headers['X-Requested-With']).toBe('XMLHttpRequest')
    expect(headers['Content-Type']).toBe('application/json')
    expect(init.body).toBe(JSON.stringify({ title: 'NDA', content: 'Text' }))
  })

  test('file uploads leave the content type to the browser (multipart boundary)', async () => {
    const fetchMock = stubFetch(json(201, { document_id: 7 }))
    const form = new FormData()
    form.append('title', 'Lease')
    await api('/documents/upload', { method: 'POST', body: form })
    const { init, headers } = sent(fetchMock)
    expect(init.body).toBe(form)
    expect(headers['Content-Type']).toBeUndefined()
    expect(headers['X-Requested-With']).toBe('XMLHttpRequest')
  })

  test('204 No Content resolves to undefined', async () => {
    stubFetch(new Response(null, { status: 204 }))
    await expect(api('/auth/logout', { method: 'POST' })).resolves.toBeUndefined()
  })
})

describe('errors', () => {
  test("the API's error shape becomes an ApiError with its code, message and request ID", async () => {
    stubFetch(
      json(409, {
        error: {
          code: 'conflict',
          message: 'A document must keep at least one owner.',
          details: { documents: [1] },
          request_id: 'req-123',
        },
      }),
    )
    const error = await api('/auth/me', { method: 'DELETE' }).catch((e: unknown) => e)
    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({
      status: 409,
      code: 'conflict',
      message: 'A document must keep at least one owner.',
      requestId: 'req-123',
      details: { documents: [1] },
    })
  })

  test('a non-JSON failure (e.g. a proxy error page) is still a clear ApiError', async () => {
    stubFetch(
      new Response('<html>Bad gateway</html>', { status: 502, headers: { 'X-Request-ID': 'req-9' } }),
    )
    const error = await api('/documents').catch((e: unknown) => e)
    expect(error).toMatchObject({ status: 502, code: 'unexpected_response', requestId: 'req-9' })
    expect((error as ApiError).message).toMatch(/HTTP 502/)
  })

  test('a network failure becomes an ApiError the user can act on', async () => {
    stubFetch(new TypeError('Failed to fetch'))
    const error = await api('/documents').catch((e: unknown) => e)
    expect(error).toMatchObject({ status: 0, code: 'network_error' })
    expect((error as ApiError).message).toMatch(/can't reach/i)
  })

  test('an aborted request is rethrown as-is, not reported as a network error', async () => {
    stubFetch(new DOMException('The operation was aborted.', 'AbortError'))
    const error = await api('/documents').catch((e: unknown) => e)
    expect(error).toBeInstanceOf(DOMException)
  })
})
