import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { X } from 'lucide-react'
import { AlertDialog, Dialog } from 'radix-ui'
import { useId, useState, type FormEvent, type ReactNode } from 'react'
import { useNavigate } from 'react-router'
import { toast } from 'sonner'

import { ApiError } from '@/api/client'
import {
  addMember,
  changeRole,
  listMembers,
  removeMember,
  renameDocument,
  uploadVersion,
  withdrawVersion,
  type DocumentSummary,
  type Member,
  type Role,
} from '@/api/document'
import { Field } from '@/components/Field'
import { FileDrop } from '@/components/FileDrop'

import { ErrorNote } from './ReadPanel'

const ROLES: Role[] = ['owner', 'editor', 'viewer']
const capital = (text: string) => text.charAt(0).toUpperCase() + text.slice(1)

function useRefresh(documentId: number) {
  const queryClient = useQueryClient()
  return () => {
    for (const key of ['document', 'versions', 'activity', 'members']) {
      void queryClient.invalidateQueries({ queryKey: [key, documentId] })
    }
    void queryClient.invalidateQueries({ queryKey: ['documents'] })
  }
}

function Sheet({ open, onOpenChange, title, description, children }: {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  description?: string
  children: ReactNode
}) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="overlay" />
        <Dialog.Content className="sheet-dialog">
          <div className="sheet-dialog__head">
            <Dialog.Title className="sheet-dialog__title">{title}</Dialog.Title>
            <Dialog.Close className="text-button" aria-label="Close">
              <X aria-hidden size={18} />
            </Dialog.Close>
          </div>
          {description ? (
            <Dialog.Description className="sheet-dialog__description">{description}</Dialog.Description>
          ) : (
            <Dialog.Description className="sr-only">{title}</Dialog.Description>
          )}
          {open && children}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}

// --- Rename ----------------------------------------------------------------------------------------

export function RenameDialog({ document, open, onOpenChange }: {
  document: DocumentSummary
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange} title="Rename">
      <RenameForm document={document} onDone={() => onOpenChange(false)} />
    </Sheet>
  )
}

function RenameForm({ document, onDone }: { document: DocumentSummary; onDone: () => void }) {
  const queryClient = useQueryClient()
  const refresh = useRefresh(document.id)
  const [title, setTitle] = useState(document.title)
  const [error, setError] = useState<string>()
  const rename = useMutation({
    mutationFn: () => renameDocument(document.id, title.trim()),
    meta: { silent: true },
    onSuccess: (renamed) => {
      queryClient.setQueryData(['document', document.id], renamed)
      refresh()
      toast.success('Renamed.')
      onDone()
    },
  })
  function submit(event: FormEvent) {
    event.preventDefault()
    if (!title.trim()) return setError('Give it a title.')
    setError(undefined)
    rename.mutate()
  }
  return (
    <form noValidate onSubmit={submit} className="field__group">
      <Field label="Title" maxLength={255} error={error} value={title} onChange={(e) => setTitle(e.target.value)} />
      {rename.isError && <ErrorNote error={rename.error} />}
      <button type="submit" className="button-primary" disabled={rename.isPending}>
        Save title
      </button>
    </form>
  )
}

// --- Upload a version -----------------------------------------------------------------------------

export function UploadVersionDialog({ documentId, next, open, onOpenChange, onSaved }: {
  documentId: number
  next: number
  open: boolean
  onOpenChange: (open: boolean) => void
  onSaved: (version: number) => void
}) {
  return (
    <Sheet
      open={open}
      onOpenChange={onOpenChange}
      title="Upload a new version"
      description="Only the file’s text is kept, as the next version. Every earlier version stays."
    >
      <UploadVersionForm documentId={documentId} next={next} onSaved={(n) => { onOpenChange(false); onSaved(n) }} />
    </Sheet>
  )
}

function UploadVersionForm({ documentId, next, onSaved }: { documentId: number; next: number; onSaved: (n: number) => void }) {
  const refresh = useRefresh(documentId)
  const [file, setFile] = useState<File | null>(null)
  const [fileError, setFileError] = useState<string | null>(null)
  const [note, setNote] = useState('')
  const [status, setStatus] = useState('')
  const upload = useMutation({
    mutationFn: () => uploadVersion(documentId, file as File, note.trim() || undefined),
    meta: { silent: true },
    onSuccess: (saved) => {
      if (saved.version === null || saved.version === undefined) {
        setStatus('The file’s text is the same as the current version, so no version was saved.')
        return
      }
      refresh()
      toast.success(`Version ${saved.version} saved.`)
      onSaved(saved.version)
    },
  })
  function submit(event: FormEvent) {
    event.preventDefault()
    setStatus('')
    if (!file) return setFileError('Choose a file first.')
    upload.mutate()
  }
  return (
    <form noValidate onSubmit={submit} className="field__group">
      <FileDrop file={file} error={fileError} onChoose={(f, problem) => { upload.reset(); setFile(f); setFileError(problem) }} />
      <Field label="Change note (optional)" maxLength={500} value={note} onChange={(e) => setNote(e.target.value)} />
      <p role="status" className="editor__status">{status}</p>
      {upload.isError && <ErrorNote error={upload.error} />}
      <button type="submit" className="button-primary" disabled={upload.isPending}>
        {upload.isPending ? 'Reading the file…' : `Upload as version ${next}`}
      </button>
    </form>
  )
}

// --- Withdraw a version (an alert dialog: it can't be undone from here) ----------------------------

export function WithdrawDialog({ documentId, version, open, onOpenChange }: {
  documentId: number
  version: number
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const refresh = useRefresh(documentId)
  const withdraw = useMutation({
    mutationFn: () => withdrawVersion(documentId, version),
    meta: { silent: true },
    onSuccess: () => {
      refresh()
      toast.success(`Version ${version} withdrawn. It stays on the record.`)
      onOpenChange(false)
    },
  })
  return (
    <AlertDialog.Root open={open} onOpenChange={onOpenChange}>
      <AlertDialog.Portal>
        <AlertDialog.Overlay className="overlay" />
        <AlertDialog.Content className="sheet-dialog">
          <AlertDialog.Title className="sheet-dialog__title">Withdraw version {version}?</AlertDialog.Title>
          <AlertDialog.Description className="sheet-dialog__description">
            It stays in the history and the activity log, marked withdrawn, but its text can no longer be
            read, compared or restored.
          </AlertDialog.Description>
          {withdraw.isError && <ErrorNote error={withdraw.error} />}
          <div className="editor__actions">
            <button
              type="button"
              className="button-primary"
              disabled={withdraw.isPending}
              onClick={() => withdraw.mutate()}
            >
              Withdraw
            </button>
            <AlertDialog.Cancel className="text-button">Keep it</AlertDialog.Cancel>
          </div>
        </AlertDialog.Content>
      </AlertDialog.Portal>
    </AlertDialog.Root>
  )
}

// --- Share --------------------------------------------------------------------------------------

export function ShareDialog({ document, me, open, onOpenChange }: {
  document: DocumentSummary
  me: number
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const owner = document.my_role === 'owner'
  return (
    <Sheet
      open={open}
      onOpenChange={onOpenChange}
      title={owner ? 'Share this document' : 'Who has access'}
      description={
        owner
          ? 'Owners manage access and can withdraw versions. Editors save, upload and restore versions. Viewers read, compare and see the activity.'
          : 'Only owners can change who has access.'
      }
    >
      <People document={document} me={me} owner={owner} onLeft={() => onOpenChange(false)} />
    </Sheet>
  )
}

function People({ document, me, owner, onLeft }: { document: DocumentSummary; me: number; owner: boolean; onLeft: () => void }) {
  const id = useId()
  const navigate = useNavigate()
  const refresh = useRefresh(document.id)
  const members = useQuery({
    queryKey: ['members', document.id],
    queryFn: ({ signal }) => listMembers(document.id, signal),
    meta: { silent: true },
  })
  const [email, setEmail] = useState('')
  const [role, setRole] = useState<Role>('viewer')
  const [emailError, setEmailError] = useState<string>()

  const add = useMutation({
    mutationFn: () => addMember(document.id, { email: email.trim(), role }),
    meta: { silent: true },
    onSuccess: (member) => {
      refresh()
      setEmail('')
      toast.success(`Shared with ${member.name} as ${role === 'owner' || role === 'editor' ? 'an' : 'a'} ${role}.`)
    },
    onError: (error) => {
      if (error instanceof ApiError && (error.status === 404 || error.status === 409 || error.status === 422)) {
        setEmailError(error.message)
      }
    },
  })
  const update = useMutation({
    mutationFn: ({ member, next }: { member: Member; next: Role }) => changeRole(document.id, member.user_id, next),
    onSuccess: () => refresh(),
  })
  const remove = useMutation({
    mutationFn: (member: Member) => removeMember(document.id, member.user_id),
    onSuccess: (_, member) => {
      refresh()
      if (member.user_id === me) {
        toast.success('You left the document.')
        onLeft()
        navigate('/documents')
      }
    },
  })

  function submit(event: FormEvent) {
    event.preventDefault()
    if (!email.trim()) return setEmailError('Enter their email address.')
    setEmailError(undefined)
    add.mutate()
  }

  if (members.isPending) return <p role="status">Loading who has access…</p>
  if (members.isError) return <ErrorNote error={members.error} retry={() => void members.refetch()} />

  return (
    <div className="share">
      <ul className="share__people" aria-label="People with access">
        {members.data.map((member) => (
          <li key={member.user_id} className="share__person">
            <span className="share__who">
              <span className="share__name">
                {member.name}
                {member.user_id === me && <span className="share__you"> (you)</span>}
              </span>
              <span className="share__email">{member.email}</span>
            </span>
            {owner && member.user_id !== me ? (
              <span className="share__controls">
                <select
                  className="field__select share__role"
                  aria-label={`Role for ${member.name}`}
                  value={member.role}
                  onChange={(event) => update.mutate({ member, next: event.target.value as Role })}
                >
                  {ROLES.map((r) => (
                    <option key={r} value={r}>
                      {capital(r)}
                    </option>
                  ))}
                </select>
                <button type="button" className="text-button" aria-label={`Remove ${member.name}`} onClick={() => remove.mutate(member)}>
                  Remove
                </button>
              </span>
            ) : (
              <span className="share__role-text">{capital(member.role)}</span>
            )}
          </li>
        ))}
      </ul>

      {owner ? (
        <form noValidate onSubmit={submit} className="share__add">
          <Field label="Email" type="email" autoComplete="off" error={emailError} value={email} onChange={(e) => setEmail(e.target.value)} />
          <div>
            <label htmlFor={`${id}-role`} className="field__label">
              Role
            </label>
            <select
              id={`${id}-role`}
              className="field__select"
              aria-label="Role for the new person"
              value={role}
              onChange={(event) => setRole(event.target.value as Role)}
            >
              {ROLES.map((r) => (
                <option key={r} value={r}>
                  {capital(r)}
                </option>
              ))}
            </select>
          </div>
          <button type="submit" className="button-primary" disabled={add.isPending}>
            Add
          </button>
        </form>
      ) : (
        <button
          type="button"
          className="text-button"
          onClick={() => {
            const self = members.data.find((m) => m.user_id === me)
            if (self) remove.mutate(self)
          }}
        >
          Leave this document
        </button>
      )}
      {(update.isError || remove.isError) && <ErrorNote error={update.error ?? remove.error} />}
    </div>
  )
}
