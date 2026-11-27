import { api } from '@/api/client'
import type { components } from '@/api/schema'

export type DemoWorkspace = components['schemas']['DemoWorkspaceResponse']

/** Create a private demo workspace and sign in as its first account (Phase 9 F1). */
export function openDemoWorkspace(): Promise<DemoWorkspace> {
  return api<DemoWorkspace>('/demo/workspaces', { method: 'POST' })
}
