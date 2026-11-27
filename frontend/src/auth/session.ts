import { useQuery } from '@tanstack/react-query'

import { api, ApiError } from '@/api/client'
import type { components } from '@/api/schema'

export type SessionUser = components['schemas']['UserResponse']

export const sessionKey = ['session'] as const

type SessionResponse = components['schemas']['SessionResponse']

/** The signed-in user, or null when signed out. The endpoint answers 200 either way, so a
 *  signed-out visit logs no failed request; a 401 (say, from an older API) still means signed out. */
export async function fetchSession(signal?: AbortSignal): Promise<SessionUser | null> {
  try {
    const { user } = await api<SessionResponse>('/auth/session', { signal })
    return user ?? null
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
