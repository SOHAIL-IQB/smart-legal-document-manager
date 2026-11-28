import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { FileUp, Pencil, Plus, Users } from 'lucide-react'
import { Tabs } from 'radix-ui'
import { useState } from 'react'
import { Link, useParams } from 'react-router'
import { toast } from 'sonner'

import { ApiError } from '@/api/client'
import {
  getDocument,
  listMembers,
  listVersions,
  restoreVersion,
  type DocumentSummary,
  type VersionSummary,
} from '@/api/document'
import { useSession } from '@/auth/session'

import { ActivityPanel } from './document/ActivityPanel'
import { ComparePanel } from './document/ComparePanel'
import { RenameDialog, ShareDialog, UploadVersionDialog, WithdrawDialog } from './document/dialogs'
import { Editor, ErrorNote, ReadPanel } from './document/ReadPanel'
import { useDocumentView, type Tab } from './document/useDocumentView'
import { VersionColumn } from './document/VersionColumn'
import './document/document.css'

const RANK = { viewer: 1, editor: 2, owner: 3 } as const
const capital = (text: string) => text.charAt(0).toUpperCase() + text.slice(1)

/** One contract: read any version, write the next, compare two, see who did what, share it. */
export function DocumentPage() {
  const documentId = Number(useParams().documentId)
  const document = useQuery({
    queryKey: ['document', documentId],
    queryFn: ({ signal }) => getDocument(documentId, signal),
    meta: { silent: true },
  })

  if (document.isPending) {
    return (
      <main className="workspace">
        <p role="status" className="workspace__status">
          Opening the document…
        </p>
      </main>
    )
  }
  if (document.isError) {
    if (document.error instanceof ApiError && document.error.status === 404) return <Unavailable />
    return (
      <main className="workspace workspace__status">
        <ErrorNote error={document.error} retry={() => void document.refetch()} />
      </main>
    )
  }
  return <Workspace document={document.data} />
}

function Unavailable() {
  return (
    <main className="workspace workspace__status">
      <title>Document not available · Inkstep</title>
      <h1 className="workspace__missing">This document isn’t available</h1>
      <p>It may have been deleted, or it hasn’t been shared with you.</p>
      <Link to="/documents" className="text-button">
        Back to your documents
      </Link>
    </main>
  )
}

function Workspace({ document }: { document: DocumentSummary }) {
  const { view, go } = useDocumentView()
  const me = useSession().data
  const queryClient = useQueryClient()
  const [editing, setEditing] = useState(false)
  const [dialog, setDialog] = useState<'share' | 'rename' | 'upload' | 'withdraw' | null>(null)
  const rank = RANK[document.my_role]

  const versions = useQuery({
    queryKey: ['versions', document.id],
    queryFn: ({ signal }) => listVersions(document.id, signal),
    meta: { silent: true },
  })
  // Who withdrew a version: the record keeps their id; the member list or the session names them.
  const members = useQuery({
    queryKey: ['members', document.id],
    queryFn: ({ signal }) => listMembers(document.id, signal),
    meta: { silent: true },
  })

  const all = [...(versions.data ?? [])].reverse() // newest first
  const live = all.filter((v) => !v.is_deleted)
  const current = live[0]
  const next = (versions.data?.length ?? 0) + 1 // numbers are never reused, withdrawn ones included
  const reading = all.find((v) => v.version_number === view.version) ?? current

  const restore = useMutation({
    mutationFn: (n: number) => restoreVersion(document.id, n),
    meta: { silent: true },
    onSuccess: (saved) => {
      for (const key of ['document', 'versions', 'activity']) {
        void queryClient.invalidateQueries({ queryKey: [key, document.id] })
      }
      void queryClient.invalidateQueries({ queryKey: ['documents'] })
      toast.success(`Version ${saved.version} saved, restoring version ${reading?.version_number}.`)
      if (saved.version) go({ tab: 'read', version: saved.version })
    },
  })

  const nameOf = (userId: number | null | undefined) =>
    members.data?.find((m) => m.user_id === userId)?.name ?? (userId === me?.id ? me?.name : undefined) ?? 'an owner'

  // The pair compared: by default the current version against the nearest earlier one whose text
  // differs. A restore repeats an older text, so the version just before it may be identical.
  const to = live.some((v) => v.version_number === view.to) ? view.to! : current?.version_number
  const toHash = live.find((v) => v.version_number === to)?.content_hash
  const earlier = live.filter((v) => v.version_number < (to ?? 0))
  const before = earlier.find((v) => v.content_hash !== toHash) ?? earlier[0]
  const from = live.some((v) => v.version_number === view.from) ? view.from! : (before ?? live[1])?.version_number

  function startWriting() {
    setEditing(true)
    go({ tab: 'read', version: undefined })
  }

  return (
    <main className="workspace">
      <title>{`${document.title} · Inkstep`}</title>
      <section className="page-band workspace__band" aria-labelledby="document-title">
        <div className="workspace__heading">
          <h1 id="document-title" className="workspace__title">
            {document.title}.
          </h1>
          <span className="tag tag--label">
            <span className="sr-only">Your role: </span>
            {capital(document.my_role)}
          </span>
        </div>
        <div className="workspace__actions">
          <button type="button" className="tag" onClick={() => setDialog('share')}>
            <Users aria-hidden size={16} /> Share
          </button>
          {rank >= 2 && (
            <>
              <button type="button" className="tag" onClick={() => setDialog('rename')}>
                <Pencil aria-hidden size={15} /> Rename
              </button>
              <button type="button" className="tag" onClick={() => setDialog('upload')}>
                <FileUp aria-hidden size={16} /> Upload version
              </button>
              <button type="button" className="tag tag--large" onClick={startWriting} disabled={!current}>
                <Plus aria-hidden size={18} /> New version
              </button>
            </>
          )}
        </div>
      </section>

      <div className="workspace__body">
        <aside className="workspace__margin" aria-label="Versions of this document">
          {versions.isPending ? (
            <p role="status">Loading the versions…</p>
          ) : versions.isError ? (
            <ErrorNote error={versions.error} retry={() => void versions.refetch()} />
          ) : (
            <>
              <VersionColumn
                versions={all}
                reading={view.tab === 'read' && !editing ? reading?.version_number : undefined}
                current={current?.version_number ?? 0}
                compare={
                  view.tab === 'compare' && from && to
                    ? { from, to, pick: (side, n) => go({ from, to, [side]: n }) }
                    : undefined
                }
              />
              {view.tab === 'read' && !editing && reading && (
                <VersionActions
                  version={reading}
                  isCurrent={reading.version_number === current?.version_number}
                  canRestore={rank >= 2}
                  canWithdraw={rank >= 3 && live.length > 1}
                  next={next}
                  restoring={restore.isPending}
                  onRestore={() => restore.mutate(reading.version_number)}
                  onWithdraw={() => setDialog('withdraw')}
                />
              )}
              {restore.isError && <ErrorNote error={restore.error} />}
            </>
          )}
        </aside>

        <Tabs.Root
          className="workspace__main"
          value={view.tab}
          onValueChange={(tab) => {
            setEditing(false)
            go({ tab: tab as Tab, version: tab === 'read' ? view.version : undefined })
          }}
        >
          <Tabs.List className="tabs__list" aria-label="What to see">
            <Tabs.Trigger value="read" className="tabs__tab">
              Read
            </Tabs.Trigger>
            <Tabs.Trigger value="compare" className="tabs__tab" disabled={live.length < 2}>
              Compare
            </Tabs.Trigger>
            <Tabs.Trigger value="activity" className="tabs__tab">
              Activity
            </Tabs.Trigger>
          </Tabs.List>

          <Tabs.Content value="read" className="tabs__panel">
            {editing && current ? (
              <Editor
                documentId={document.id}
                current={current}
                next={next}
                onCancel={() => setEditing(false)}
                onSaved={(n) => {
                  setEditing(false)
                  go({ tab: 'read', version: n })
                }}
              />
            ) : (
              reading && (
                <ReadPanel
                  documentId={document.id}
                  version={reading}
                  withdrawnBy={nameOf(reading.deleted_by)}
                />
              )
            )}
          </Tabs.Content>
          <Tabs.Content value="compare" className="tabs__panel">
            {from && to ? (
              <ComparePanel
                documentId={document.id}
                live={live}
                from={from}
                to={to}
                everyLine={view.everyLine}
                onChange={(change) => go({ from, to, everyLine: view.everyLine, ...change })}
              />
            ) : (
              <p className="reading__status">Only one version so far: there is nothing to compare yet.</p>
            )}
          </Tabs.Content>
          <Tabs.Content value="activity" className="tabs__panel">
            <ActivityPanel documentId={document.id} />
          </Tabs.Content>
        </Tabs.Root>
      </div>

      {me && <ShareDialog document={document} me={me.id} open={dialog === 'share'} onOpenChange={(o) => setDialog(o ? 'share' : null)} />}
      <RenameDialog document={document} open={dialog === 'rename'} onOpenChange={(o) => setDialog(o ? 'rename' : null)} />
      <UploadVersionDialog
        documentId={document.id}
        next={next}
        open={dialog === 'upload'}
        onOpenChange={(o) => setDialog(o ? 'upload' : null)}
        onSaved={(n) => go({ tab: 'read', version: n })}
      />
      {reading && (
        <WithdrawDialog
          documentId={document.id}
          version={reading.version_number}
          open={dialog === 'withdraw'}
          onOpenChange={(o) => setDialog(o ? 'withdraw' : null)}
        />
      )}
    </main>
  )
}

function VersionActions({ version, isCurrent, canRestore, canWithdraw, next, restoring, onRestore, onWithdraw }: {
  version: VersionSummary
  isCurrent: boolean
  canRestore: boolean
  canWithdraw: boolean
  next: number
  restoring: boolean
  onRestore: () => void
  onWithdraw: () => void
}) {
  if (version.is_deleted) return null
  const restore = canRestore && !isCurrent
  if (!restore && !canWithdraw) return null
  return (
    <div className="versions__actions" aria-label={`Version ${version.version_number}`} role="group">
      {restore && (
        <button type="button" className="text-button" disabled={restoring} onClick={onRestore}>
          Restore as version {next}
        </button>
      )}
      {canWithdraw && (
        <button type="button" className="text-button" onClick={onWithdraw}>
          Withdraw version {version.version_number}
        </button>
      )}
    </div>
  )
}
