import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useId, useState, type FormEvent } from 'react'
import { toast } from 'sonner'

import { getVersion, saveVersion, type VersionSummary } from '@/api/document'
import { Field } from '@/components/Field'
import { describeError } from '@/lib/errors'
import { exactTime, timeAgo } from '@/lib/time'

import { lineForm } from './VersionColumn'

type ReadProps = {
  documentId: number
  version: VersionSummary
  withdrawnBy: string
}

/** One version's text, with who wrote it, when, and why. A withdrawn version's text is gone. */
export function ReadPanel({ documentId, version, withdrawnBy }: ReadProps) {
  const headingId = useId()
  const form = lineForm(version)
  const text = useQuery({
    queryKey: ['version', documentId, version.version_number],
    queryFn: ({ signal }) => getVersion(documentId, version.version_number, signal),
    enabled: form !== 'withdrawn',
    meta: { silent: true },
  })

  return (
    <article className="reading" aria-labelledby={headingId}>
      <header className="reading__head">
        <h2 id={headingId} className="reading__title">
          Version {version.version_number}
        </h2>
        <p className="reading__meta">
          {version.edited_by_name} ·{' '}
          <time dateTime={version.created_at} title={exactTime(version.created_at)}>
            {timeAgo(version.created_at)}
          </time>
          {form === 'restored' && version.restored_from && <> · restores version {version.restored_from}</>}
          {version.source === 'upload' && version.source_filename && <> · from {version.source_filename}</>}
          {form !== 'withdrawn' && <> · {version.word_count.toLocaleString('en')} words</>}
        </p>
        {version.change_note && <p className="reading__note">“{version.change_note}”</p>}
      </header>

      {form === 'withdrawn' ? (
        <div className="reading__withdrawn">
          <p>
            Withdrawn by {withdrawnBy}
            {version.deleted_at && <> {timeAgo(version.deleted_at)}</>}.
          </p>
          <p>
            It is still on the record, in this column and the activity log, but its text can no longer be
            read, compared or restored.
          </p>
        </div>
      ) : text.isPending ? (
        <p role="status" className="reading__status">
          Loading the text…
        </p>
      ) : text.isError ? (
        <ErrorNote error={text.error} retry={() => void text.refetch()} />
      ) : (
        <div className="reading__text">{text.data.content}</div>
      )}
    </article>
  )
}

export function ErrorNote({ error, retry }: { error: unknown; retry?: () => void }) {
  const { message, requestId } = describeError(error)
  return (
    <div role="alert" className="form-alert">
      <p>{message}</p>
      {requestId && <p className="form-alert__reference">Reference: {requestId}</p>}
      {retry && (
        <p>
          <button type="button" className="text-button" onClick={retry}>
            Try again
          </button>
        </p>
      )}
    </div>
  )
}

type EditorProps = {
  documentId: number
  current: VersionSummary // the text starts from the newest live version
  next: number // the number the new version will take
  onSaved: (version: number) => void
  onCancel: () => void
}

/** A new version, written in place on lined paper, from the current text. */
export function Editor({ documentId, current, next, onSaved, onCancel }: EditorProps) {
  const id = useId()
  const queryClient = useQueryClient()
  const source = useQuery({
    queryKey: ['version', documentId, current.version_number],
    queryFn: ({ signal }) => getVersion(documentId, current.version_number, signal),
  })
  const [draft, setDraft] = useState<string | null>(null)
  const [note, setNote] = useState('')
  const [status, setStatus] = useState('')
  const [empty, setEmpty] = useState(false)
  const text = draft ?? source.data?.content ?? ''

  const save = useMutation({
    mutationFn: () => saveVersion(documentId, { content: text, change_note: note.trim() || undefined }),
    meta: { silent: true },
    onSuccess: (saved) => {
      if (saved.version === null || saved.version === undefined) {
        setStatus('Nothing changed, so no version was saved.')
        return
      }
      for (const key of ['document', 'versions', 'activity']) {
        void queryClient.invalidateQueries({ queryKey: [key, documentId] })
      }
      void queryClient.invalidateQueries({ queryKey: ['documents'] })
      toast.success(`Version ${saved.version} saved.`)
      onSaved(saved.version)
    },
  })

  function submit(event: FormEvent) {
    event.preventDefault()
    setStatus('')
    if (!text.trim()) {
      setEmpty(true)
      return
    }
    setEmpty(false)
    save.mutate()
  }

  return (
    <form className="editor" noValidate onSubmit={submit} aria-labelledby={`${id}-title`}>
      <h2 id={`${id}-title`} className="reading__title">
        New version {next}
      </h2>
      <p className="reading__meta">Starting from version {current.version_number}. Change anything, then save.</p>
      <div className="field" data-invalid={empty || undefined}>
        <label htmlFor={`${id}-text`} className="sr-only">
          Text of the new version
        </label>
        <textarea
          id={`${id}-text`}
          className="field__textarea editor__text"
          value={text}
          disabled={source.isPending}
          aria-invalid={empty || undefined}
          aria-describedby={empty ? `${id}-text-error` : undefined}
          onChange={(event) => setDraft(event.target.value)}
        />
        {empty && (
          <p id={`${id}-text-error`} className="field__error">
            A version can’t be empty.
          </p>
        )}
      </div>
      <Field
        label="Change note (optional)"
        hint="Why it changed, in a line. It shows in the margin and the activity."
        maxLength={500}
        value={note}
        onChange={(event) => setNote(event.target.value)}
      />
      <p role="status" aria-label="Editor status" className="editor__status">
        {status}
      </p>
      {save.isError && <ErrorNote error={save.error} />}
      <div className="editor__actions">
        <button type="submit" className="button-primary" disabled={save.isPending || source.isPending}>
          {save.isPending ? 'Saving…' : `Save version ${next}`}
        </button>
        <button type="button" className="text-button" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </form>
  )
}
