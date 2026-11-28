import { useMutation, useQueryClient } from '@tanstack/react-query'
import { X } from 'lucide-react'
import { Dialog, Tabs } from 'radix-ui'
import { useId, useRef, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router'
import { toast } from 'sonner'

import { createDocument, uploadDocument, type DocumentCreated } from '@/api/documents'
import { Field } from '@/components/Field'
import { FileDrop } from '@/components/FileDrop'
import { describeError } from '@/lib/errors'

// The API's own limit for pasted text (app/schemas/common.py).
const MAX_CONTENT_CHARS = 2_000_000

type Props = { open: boolean; onOpenChange: (open: boolean) => void }

/** A new document from a file (PDF, DOCX, TXT) or from pasted text. It opens once created. */
export function NewDocumentDialog({ open, onOpenChange }: Props) {
  const queryClient = useQueryClient()
  const navigate = useNavigate()

  function created({ document_id }: DocumentCreated) {
    void queryClient.invalidateQueries({ queryKey: ['documents'] })
    onOpenChange(false)
    toast.success('Document created. This is version 1.')
    navigate(`/documents/${document_id}`)
  }

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="overlay" />
        <Dialog.Content className="sheet-dialog">
          <div className="sheet-dialog__head">
            <Dialog.Title className="sheet-dialog__title">New document</Dialog.Title>
            <Dialog.Close className="text-button" aria-label="Close">
              <X aria-hidden size={18} />
            </Dialog.Close>
          </div>
          <Dialog.Description className="sheet-dialog__description">
            Only the text is kept. It becomes version 1; every later change adds a version.
          </Dialog.Description>
          {open && (
            <Tabs.Root defaultValue="upload" className="tabs">
              <Tabs.List className="tabs__list" aria-label="How to start it">
                <Tabs.Trigger value="upload" className="tabs__tab">
                  Upload a file
                </Tabs.Trigger>
                <Tabs.Trigger value="paste" className="tabs__tab">
                  Paste text
                </Tabs.Trigger>
              </Tabs.List>
              <Tabs.Content value="upload" className="tabs__panel">
                <UploadForm onCreated={created} />
              </Tabs.Content>
              <Tabs.Content value="paste" className="tabs__panel">
                <PasteForm onCreated={created} />
              </Tabs.Content>
            </Tabs.Root>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}

function UploadForm({ onCreated }: { onCreated: (created: DocumentCreated) => void }) {
  const [file, setFile] = useState<File | null>(null)
  const [title, setTitle] = useState('')
  const [fileError, setFileError] = useState<string | null>(null)
  const upload = useMutation({
    mutationFn: () => uploadDocument(file as File, title.trim() || undefined),
    onSuccess: onCreated,
    meta: { silent: true }, // the reason is shown in the dialog
  })

  function submit(event: FormEvent) {
    event.preventDefault()
    if (!file) {
      setFileError('Choose a file first.')
      return
    }
    upload.mutate()
  }

  const serverProblem = upload.isError ? describeError(upload.error) : null

  return (
    <form noValidate onSubmit={submit} className="field__group">
      <FileDrop
        file={file}
        error={fileError}
        onChoose={(next, problem) => {
          upload.reset()
          setFile(next)
          setFileError(problem)
        }}
      />
      <Field
        label="Title (optional)"
        hint="The file name if left blank."
        maxLength={255}
        value={title}
        onChange={(event) => setTitle(event.target.value)}
      />
      {serverProblem && (
        <div role="alert" className="form-alert">
          <p>{serverProblem.message}</p>
          {serverProblem.requestId && <p className="form-alert__reference">Reference: {serverProblem.requestId}</p>}
        </div>
      )}
      <button type="submit" className="button-primary" disabled={upload.isPending}>
        {upload.isPending ? 'Reading the file…' : 'Upload and create'}
      </button>
    </form>
  )
}

function PasteForm({ onCreated }: { onCreated: (created: DocumentCreated) => void }) {
  const id = useId()
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [errors, setErrors] = useState<{ title?: string; content?: string }>({})
  const titleRef = useRef<HTMLInputElement>(null)
  const contentRef = useRef<HTMLTextAreaElement>(null)
  const create = useMutation({
    mutationFn: () => createDocument({ title: title.trim(), content }),
    onSuccess: onCreated,
    meta: { silent: true },
  })

  function submit(event: FormEvent) {
    event.preventDefault()
    const next = {
      title: title.trim() ? undefined : 'Give it a title.',
      content: !content.trim()
        ? 'Paste or type the text.'
        : content.length > MAX_CONTENT_CHARS
          ? 'This text is longer than 2,000,000 characters.'
          : undefined,
    }
    setErrors(next)
    if (next.title || next.content) {
      ;(next.title ? titleRef.current : contentRef.current)?.focus()
      return
    }
    create.mutate()
  }

  const serverProblem = create.isError ? describeError(create.error) : null

  return (
    <form noValidate onSubmit={submit} className="field__group">
      <Field
        ref={titleRef}
        label="Title"
        maxLength={255}
        error={errors.title}
        value={title}
        onChange={(event) => setTitle(event.target.value)}
      />
      <div className="field" data-invalid={errors.content ? true : undefined}>
        <label htmlFor={`${id}-content`} className="field__label">
          Text
        </label>
        <textarea
          ref={contentRef}
          id={`${id}-content`}
          className="field__textarea"
          aria-invalid={errors.content ? true : undefined}
          aria-describedby={errors.content ? `${id}-content-error` : undefined}
          value={content}
          onChange={(event) => setContent(event.target.value)}
        />
        {errors.content && (
          <p id={`${id}-content-error`} className="field__error">
            {errors.content}
          </p>
        )}
      </div>
      {serverProblem && (
        <div role="alert" className="form-alert">
          <p>{serverProblem.message}</p>
          {serverProblem.requestId && <p className="form-alert__reference">Reference: {serverProblem.requestId}</p>}
        </div>
      )}
      <button type="submit" className="button-primary" disabled={create.isPending}>
        {create.isPending ? 'Creating…' : 'Create document'}
      </button>
    </form>
  )
}
