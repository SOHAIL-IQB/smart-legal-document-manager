import type { ActivityItem } from '@/api/document'

const article = (role: unknown) => (role === 'owner' || role === 'editor' ? `an ${role}` : `a ${String(role)}`)
const note = (value: unknown) => (typeof value === 'string' && value ? `: “${value}”` : '')
const fromFile = (details: Record<string, unknown>) =>
  details.source === 'upload' && typeof details.source_filename === 'string' ? ` from ${details.source_filename}` : ''

/** One activity event as a sentence, in the record's own facts (app/services: `activity.record`). */
export function describeActivity(item: ActivityItem): string {
  const who = item.actor_name
  const d = (item.details ?? {}) as Record<string, unknown>
  switch (item.action) {
    case 'document.created':
      return `${who} created it as version 1${fromFile(d)}`
    case 'version.created':
      return `${who} saved version ${d.version}${fromFile(d)}${note(d.change_note)}`
    case 'version.restored':
      return `${who} restored version ${d.restored_from} as version ${d.version}${note(d.change_note)}`
    case 'version.deleted':
      return `${who} withdrew version ${d.version}`
    case 'document.renamed':
      return `${who} renamed it from “${d.from}” to “${d.to}”`
    case 'member.added':
      return `${who} shared it with ${d.name} as ${article(d.role)}`
    case 'member.role_changed':
      return `${who} made ${d.name} ${article(d.to)}`
    case 'member.removed':
      return d.left ? `${d.name ?? who} left the document` : `${who} removed ${d.name}`
    default:
      return `${who}: ${item.action}`
  }
}
