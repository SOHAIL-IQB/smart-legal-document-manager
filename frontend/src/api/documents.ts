import { api } from '@/api/client'
import type { components } from '@/api/schema'

export type DocumentSummary = components['schemas']['DocumentResponse']
export type DocumentList = components['schemas']['DocumentListResponse']
export type DocumentCreated = components['schemas']['DocumentCreateResponse']
export type Role = DocumentSummary['my_role']
export type SortField = 'updated_at' | 'created_at' | 'title'
export type SortOrder = 'asc' | 'desc'

export type ListParams = {
  q?: string
  role?: Role
  sort?: SortField
  order?: SortOrder
  limit: number
  offset: number
}

/** `GET /documents`: only parameters that are set go in the query string. */
export function listDocuments(params: ListParams, signal?: AbortSignal): Promise<DocumentList> {
  const query = new URLSearchParams()
  if (params.q) query.set('q', params.q)
  if (params.role) query.set('role', params.role)
  if (params.sort) query.set('sort', params.sort)
  if (params.order) query.set('order', params.order)
  query.set('limit', String(params.limit))
  query.set('offset', String(params.offset))
  return api<DocumentList>(`/documents?${query}`, { signal })
}

export function createDocument(body: { title: string; content: string }): Promise<DocumentCreated> {
  return api<DocumentCreated>('/documents', { method: 'POST', body })
}

export function uploadDocument(file: File, title?: string): Promise<DocumentCreated> {
  const form = new FormData()
  form.set('file', file)
  if (title) form.set('title', title)
  return api<DocumentCreated>('/documents/upload', { method: 'POST', body: form })
}
