import type { FieldValues, Path, UseFormSetError } from 'react-hook-form'

import { ApiError } from '@/api/client'
import { describeError } from '@/lib/errors'

export type FormProblem = { message: string; requestId: string | null }

/**
 * Puts an API failure where the visitor will look for it: on the field it is about (422 field
 * details, or a field `fieldFor` names), otherwise as one message for the whole form.
 * Returns the form-level problem, or null when every error landed on a field.
 */
export function applyServerError<T extends FieldValues>(
  error: unknown,
  setError: UseFormSetError<T>,
  fields: readonly Path<T>[],
  fieldFor?: (error: ApiError) => Path<T> | null,
): FormProblem | null {
  if (error instanceof ApiError) {
    const named = fieldFor?.(error)
    if (named) {
      setError(named, { type: 'server', message: error.message }, { shouldFocus: true })
      return null
    }
    if (error.status === 422 && Array.isArray(error.details)) {
      const mine = (error.details as { field?: unknown; message?: unknown }[]).filter(
        (d): d is { field: Path<T>; message: string } =>
          fields.includes(d.field as Path<T>) && typeof d.message === 'string',
      )
      mine.forEach((d, i) => setError(d.field, { type: 'server', message: d.message }, { shouldFocus: i === 0 }))
      if (mine.length > 0) return null
    }
  }
  return describeError(error)
}
