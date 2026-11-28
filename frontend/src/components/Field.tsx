import { useId, useState, type InputHTMLAttributes, type Ref } from 'react'

import './fields.css'

type Props = Omit<InputHTMLAttributes<HTMLInputElement>, 'id'> & {
  label: string
  error?: string
  hint?: string
  ref?: Ref<HTMLInputElement>
}

/** A ruled line on the washi: label above, the error (if any) and a hint below, all tied to the input. */
export function Field({ label, error, hint, ref, type = 'text', ...input }: Props) {
  const id = useId()
  const [shown, setShown] = useState(false)
  const errorId = `${id}-error`
  const hintId = `${id}-hint`
  const describedBy = [error && errorId, hint && hintId].filter(Boolean).join(' ') || undefined
  const isPassword = type === 'password'

  return (
    <div className="field" data-invalid={error ? true : undefined}>
      <label htmlFor={id} className="field__label">
        {label}
      </label>
      <div className="field__line">
        <input
          {...input}
          ref={ref}
          id={id}
          type={isPassword && shown ? 'text' : type}
          className="field__input"
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
        />
        {isPassword && (
          <button
            type="button"
            className="field__toggle"
            aria-label={shown ? 'Hide password' : 'Show password'}
            onClick={() => setShown((value) => !value)}
          >
            {shown ? 'Hide' : 'Show'}
          </button>
        )}
      </div>
      {error && (
        <p id={errorId} className="field__error">
          {error}
        </p>
      )}
      {hint && (
        <p id={hintId} className="field__hint">
          {hint}
        </p>
      )}
    </div>
  )
}
