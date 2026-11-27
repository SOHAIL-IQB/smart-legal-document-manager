import { MutationCache, QueryCache, QueryClient } from '@tanstack/react-query'

import { ApiError } from '@/api/client'

import { notifyError } from './errors'

// Every failed query or mutation is shown once, the same way (Phase 9 F3). A request opts out with
// `meta: { silent: true }` when its screen shows the failure itself.
export function createQueryClient(): QueryClient {
  return new QueryClient({
    queryCache: new QueryCache({
      onError: (error, query) => {
        if (!query.meta?.silent) notifyError(error)
      },
    }),
    mutationCache: new MutationCache({
      onError: (error, _variables, _context, mutation) => {
        if (!mutation.meta?.silent) notifyError(error)
      },
    }),
    defaultOptions: {
      queries: {
        // Retry only what might succeed next time: network trouble and server errors, twice.
        retry: (failures, error) =>
          failures < 2 && !(error instanceof ApiError && error.status > 0 && error.status < 500),
      },
    },
  })
}
