import { api } from '@/api/client'
import type { components } from '@/api/schema'

// One document and everything about it: versions, comparison, activity, members.

type Schemas = components['schemas']
export type DocumentSummary = Schemas['DocumentResponse']
export type VersionSummary = Schemas['DocumentVersionSummary']
export type Version = Schemas['DocumentVersionResponse']
export type VersionSaved = Schemas['DocumentVersionCreateResponse']
export type Comparison = Schemas['CompareResponse']
export type DiffRow = Schemas['DiffRow']
export type Segment = Schemas['Segment']
export type ActivityPage = Schemas['ActivityPage']
export type ActivityItem = Schemas['ActivityItem']
export type Member = Schemas['MemberResponse']
export type Role = Schemas['Role']

const base = (id: number) => `/documents/${id}`

export const getDocument = (id: number, signal?: AbortSignal) =>
  api<DocumentSummary>(base(id), { signal })

/** Every version, withdrawn ones included: they stay on the record. */
export const listVersions = (id: number, signal?: AbortSignal) =>
  api<VersionSummary[]>(`${base(id)}/versions?include_deleted=true`, { signal })

export const getVersion = (id: number, n: number, signal?: AbortSignal) =>
  api<Version>(`${base(id)}/versions/${n}`, { signal })

export const saveVersion = (id: number, body: { content: string; change_note?: string }) =>
  api<VersionSaved>(`${base(id)}/versions`, { method: 'POST', body })

export function uploadVersion(id: number, file: File, changeNote?: string) {
  const form = new FormData()
  form.set('file', file)
  if (changeNote) form.set('change_note', changeNote)
  return api<VersionSaved>(`${base(id)}/versions/upload`, { method: 'POST', body: form })
}

export const restoreVersion = (id: number, n: number) =>
  api<VersionSaved>(`${base(id)}/versions/${n}/restore`, { method: 'POST', body: {} })

export const withdrawVersion = (id: number, n: number) =>
  api<{ message: string }>(`${base(id)}/versions/${n}`, { method: 'DELETE' })

/** `context` keeps that many unchanged lines around each change; omit it for every line. */
export function compareVersions(id: number, v1: number, v2: number, context?: number, signal?: AbortSignal) {
  const query = new URLSearchParams({ v1: String(v1), v2: String(v2) })
  if (context !== undefined) query.set('context', String(context))
  return api<Comparison>(`${base(id)}/compare?${query}`, { signal })
}

export const listActivity = (id: number, offset: number, signal?: AbortSignal) =>
  api<ActivityPage>(`${base(id)}/activity?limit=20&offset=${offset}`, { signal })

export const renameDocument = (id: number, title: string) =>
  api<DocumentSummary>(`${base(id)}/title`, { method: 'PATCH', body: { title } })

export const listMembers = (id: number, signal?: AbortSignal) =>
  api<Member[]>(`${base(id)}/members`, { signal })

export const addMember = (id: number, body: { email: string; role: Role }) =>
  api<Member>(`${base(id)}/members`, { method: 'POST', body })

export const changeRole = (id: number, userId: number, role: Role) =>
  api<Member>(`${base(id)}/members/${userId}`, { method: 'PATCH', body: { role } })

export const removeMember = (id: number, userId: number) =>
  api<{ message: string }>(`${base(id)}/members/${userId}`, { method: 'DELETE' })
