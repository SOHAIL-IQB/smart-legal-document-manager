import { api } from '@/api/client'
import type { components } from '@/api/schema'

export type DemoWorkspace = components['schemas']['DemoWorkspaceResponse']

/** Create a private demo workspace and sign in as its first account (Phase 9 F1). */
export function openDemoWorkspace(): Promise<DemoWorkspace> {
  return api<DemoWorkspace>('/demo/workspaces', { method: 'POST' })
}

export type CurrentWorkspace = components['schemas']['CurrentWorkspaceResponse']
export type AuthResponse = components['schemas']['AuthResponse']

/** The signed-in demo account's workspace and its people (404 for a real account). */
export function currentWorkspace(signal?: AbortSignal): Promise<CurrentWorkspace> {
  return api<CurrentWorkspace>('/demo/workspaces/current', { signal })
}

/** Become another account of the same demo workspace. */
export function switchAccount(userId: number): Promise<AuthResponse> {
  return api<AuthResponse>('/demo/workspaces/current/switch', {
    method: 'POST',
    body: { user_id: userId },
  })
}
