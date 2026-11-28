import { FileUp } from 'lucide-react'
import { useId, useState, type DragEvent } from 'react'

// The API's own upload limits (app/core/config.py): PDF, DOCX or TXT, up to 10 MB.
export const MAX_UPLOAD_BYTES = 10 * 1024 * 1024
export const ACCEPTED = ['.pdf', '.docx', '.txt']

/** Why a file can't be sent, or null. The server still decides; this only saves a wasted upload. */
export function checkFile(file: File): string | null {
  const name = file.name.toLowerCase()
  if (!ACCEPTED.some((ext) => name.endsWith(ext))) return 'Choose a PDF, Word (.docx) or text (.txt) file.'
  if (file.size > MAX_UPLOAD_BYTES) return 'This file is larger than 10 MB.'
  return null
}

const size = (bytes: number) =>
  bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`

type Props = {
  file: File | null
  error: string | null
  /** Called with each file chosen or dropped (already checked: `error` says why one was refused). */
  onChoose: (file: File | null, error: string | null) => void
}

/** A washi slip to drop a file on, or a label for the hidden file input. */
export function FileDrop({ file, error, onChoose }: Props) {
  const id = useId()
  const [dragging, setDragging] = useState(false)

  function choose(next: File | undefined) {
    if (!next) return
    const problem = checkFile(next)
    onChoose(problem ? null : next, problem)
  }

  function onDrop(event: DragEvent) {
    event.preventDefault()
    setDragging(false)
    choose(event.dataTransfer.files[0])
  }

  return (
    <>
      <label
        htmlFor={`${id}-file`}
        className="dropzone"
        data-dragging={dragging || undefined}
        data-invalid={error ? true : undefined}
        onDragOver={(event) => {
          event.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
      >
        <FileUp aria-hidden size={22} />
        <span className="dropzone__label">Choose a file, or drop it here</span>
        <span className="dropzone__hint">PDF, Word (.docx) or text (.txt), up to 10 MB</span>
        {file && (
          <span className="dropzone__file">
            <span>{file.name}</span> <span className="dropzone__size">{size(file.size)}</span>
          </span>
        )}
      </label>
      <input
        id={`${id}-file`}
        type="file"
        className="sr-only"
        accept={ACCEPTED.join(',')}
        aria-describedby={error ? `${id}-file-error` : undefined}
        aria-invalid={error ? true : undefined}
        onChange={(event) => {
          choose(event.target.files?.[0])
          event.target.value = '' // the same file can be chosen again after a fix
        }}
      />
      {error && (
        <p id={`${id}-file-error`} className="field__error">
          {error}
        </p>
      )}
    </>
  )
}
