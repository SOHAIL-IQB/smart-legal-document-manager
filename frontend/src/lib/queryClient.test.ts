import { afterEach, expect, test, vi } from 'vitest'

import { ApiError } from '@/api/client'

const notifyError = vi.fn()
vi.mock('./errors', () => ({ notifyError: (error: unknown) => notifyError(error) }))

const { createQueryClient } = await import('./queryClient')

afterEach(() => notifyError.mockReset())

const forbidden = new ApiError(403, 'forbidden', 'This action needs the owner role.', 'req-1')

test('a failed query is shown once', async () => {
  const client = createQueryClient()
  await client
    .fetchQuery({ queryKey: ['x'], queryFn: () => Promise.reject(forbidden), retry: false })
    .catch(() => undefined)
  expect(notifyError).toHaveBeenCalledTimes(1)
  expect(notifyError).toHaveBeenCalledWith(forbidden)
})

test('a query marked silent is not shown (its screen shows the failure itself)', async () => {
  const client = createQueryClient()
  await client
    .fetchQuery({
      queryKey: ['y'],
      queryFn: () => Promise.reject(forbidden),
      retry: false,
      meta: { silent: true },
    })
    .catch(() => undefined)
  expect(notifyError).not.toHaveBeenCalled()
})

test('a failed mutation is shown', async () => {
  const client = createQueryClient()
  const mutation = client.getMutationCache().build(client, {
    mutationFn: () => Promise.reject(forbidden),
  })
  await mutation.execute(undefined).catch(() => undefined)
  expect(notifyError).toHaveBeenCalledWith(forbidden)
})

test('retries only what may succeed next time: network and server errors, at most twice', () => {
  const retry = createQueryClient().getDefaultOptions().queries?.retry as (
    failures: number,
    error: unknown,
  ) => boolean
  expect(retry(0, forbidden)).toBe(false)
  expect(retry(0, new ApiError(404, 'not_found', 'Gone.', null))).toBe(false)
  expect(retry(0, new ApiError(0, 'network_error', 'Offline.', null))).toBe(true)
  expect(retry(1, new ApiError(503, 'busy', 'Busy.', null))).toBe(true)
  expect(retry(2, new ApiError(503, 'busy', 'Busy.', null))).toBe(false)
})
