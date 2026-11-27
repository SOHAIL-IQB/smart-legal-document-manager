import { afterEach, expect, test, vi } from 'vitest'

import { ApiError } from '@/api/client'

const toastError = vi.fn()
vi.mock('sonner', () => ({ toast: { error: (...args: unknown[]) => toastError(...args) } }))

const { describeError, notifyError } = await import('./errors')

afterEach(() => toastError.mockReset())

test("shows the API's message with the request ID as a reference", () => {
  notifyError(new ApiError(410, 'gone', 'Version 3 was deleted.', 'req-42'))
  expect(toastError).toHaveBeenCalledWith('Version 3 was deleted.', {
    description: 'Reference: req-42',
  })
})

test('no reference line when there is no request ID', () => {
  notifyError(new ApiError(0, 'network_error', "Can't reach Inkstep.", null))
  expect(toastError).toHaveBeenCalledWith("Can't reach Inkstep.", { description: undefined })
})

test('an unexpected error gets a generic message, never a stack trace', () => {
  expect(describeError(new Error('TypeError: x is undefined at foo.ts:12'))).toEqual({
    message: 'Something went wrong. Please try again.',
    requestId: null,
  })
})
