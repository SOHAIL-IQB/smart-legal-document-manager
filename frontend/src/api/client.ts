// The one way the app talks to the API (Phase 9 F3). Same origin: the httpOnly session cookie rides
// along, and every write carries the CSRF header the API requires (docs/adr/0001). Failures become
// ApiError with the API's own code, message and request ID (docs/adr/0002).

const SAFE_METHODS = new Set(['GET', 'HEAD', 'OPTIONS'])
const CSRF_HEADER = 'X-Requested-With'

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly requestId: string | null
  readonly details: unknown

  constructor(
    status: number,
    code: string,
    message: string,
    requestId: string | null,
    details?: unknown,
  ) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.requestId = requestId
    this.details = details
  }
}

type RequestOptions = {
  method?: string
  body?: unknown
  signal?: AbortSignal
}

type ErrorBody = {
  error?: { code?: unknown; message?: unknown; details?: unknown; request_id?: unknown }
}

function isAbort(error: unknown): boolean {
  // By the standard name, not the class: DOMException identity differs between environments.
  return typeof error === 'object' && error !== null && (error as { name?: unknown }).name === 'AbortError'
}

async function readJson(response: Response): Promise<{ ok: true; value: unknown } | { ok: false }> {
  const text = await response.text()
  if (!text) return { ok: true, value: undefined }
  try {
    return { ok: true, value: JSON.parse(text) }
  } catch {
    return { ok: false }
  }
}

function unexpected(response: Response): ApiError {
  return new ApiError(
    response.status,
    'unexpected_response',
    `The server sent an unexpected response (HTTP ${response.status}). Please try again.`,
    response.headers.get('X-Request-ID'),
  )
}

function fromErrorBody(response: Response, body: ErrorBody): ApiError {
  const error = body.error
  if (!error || typeof error.message !== 'string' || typeof error.code !== 'string') {
    return unexpected(response)
  }
  const requestId =
    typeof error.request_id === 'string' ? error.request_id : response.headers.get('X-Request-ID')
  return new ApiError(response.status, error.code, error.message, requestId, error.details)
}

/** Call the API at `/api{path}`. Resolves to the parsed JSON body (undefined for 204). */
export async function api<T = unknown>(path: string, options: RequestOptions = {}): Promise<T> {
  const method = (options.method ?? 'GET').toUpperCase()
  const headers: Record<string, string> = { Accept: 'application/json' }
  if (!SAFE_METHODS.has(method)) headers[CSRF_HEADER] = 'XMLHttpRequest'

  let body: BodyInit | undefined
  if (options.body instanceof FormData) {
    body = options.body // the browser sets the multipart Content-Type with its boundary
  } else if (options.body !== undefined) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(options.body)
  }

  let response: Response
  try {
    response = await fetch(`/api${path}`, {
      method,
      headers,
      body,
      signal: options.signal,
      credentials: 'same-origin',
    })
  } catch (error) {
    if (isAbort(error)) throw error
    throw new ApiError(
      0,
      'network_error',
      "Can't reach Inkstep. Check your connection and try again.",
      null,
    )
  }

  const parsed = await readJson(response)
  if (!response.ok) {
    if (!parsed.ok || typeof parsed.value !== 'object' || parsed.value === null) {
      throw unexpected(response)
    }
    throw fromErrorBody(response, parsed.value as ErrorBody)
  }
  if (!parsed.ok) throw unexpected(response)
  return parsed.value as T
}
