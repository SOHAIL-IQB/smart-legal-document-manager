import { toast } from 'sonner'

import { ApiError } from '@/api/client'

// One way to show a failure (Phase 9 F3): the API's own message, plus its request ID as a
// reference the user can quote, which matches the X-Request-ID in the server logs (docs/adr/0002).
// Anything that isn't an ApiError gets a generic message; internals never reach the screen.

const GENERIC = 'Something went wrong. Please try again.'

export function describeError(error: unknown): { message: string; requestId: string | null } {
  if (error instanceof ApiError) return { message: error.message, requestId: error.requestId }
  return { message: GENERIC, requestId: null }
}

export function notifyError(error: unknown): void {
  const { message, requestId } = describeError(error)
  toast.error(message, { description: requestId ? `Reference: ${requestId}` : undefined })
}
