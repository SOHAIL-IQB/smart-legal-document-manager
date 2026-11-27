import { useQuery } from '@tanstack/react-query'

import { api, ApiError } from '@/api/client'
import type { components } from '@/api/schema'

export type SessionUser = components['schemas']['UserResponse']

export const sessionKey = ['session'] as const

/** The signed-in user, or null when signed out (401 is an answer here, not an error). */
export async function fetchSession(signal?: AbortSignal): Promise<SessionUser | null> {
  try {
    return await api<SessionUser>('/auth/me', { signal })
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) return null
    throw error
  }
}

export function useSession() {
  return useQuery({
    queryKey: sessionKey,
    queryFn: ({ signal }) => fetchSession(signal),
    staleTime: 60_000,
    retry: false,
    meta: { silent: true }, // the guard shows its own state; no toast for a signed-out visitor
  })
}
