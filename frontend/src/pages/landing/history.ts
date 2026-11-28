import data from './msa-history.json'

// The sample agreement's real history (checked against the seed by tests/test_landing_sample.py).

export type Mark = 'ins' | 'del'
export type Segment = { text: string; mark?: Mark }
export type FoldState = 'live' | 'withdrawn' | 'restored'

export type Fold = {
  number: number
  author: string
  note: string | null
  state: FoldState
  restores?: number
  clauses: Segment[][]
}

type RawFold = Omit<Fold, 'clauses' | 'state'> & { state: string; clauses: string[][][] }

export const sample = {
  title: data.title,
  excerpt: data.excerpt,
  folds: (data.folds as RawFold[]).map(
    (fold): Fold => ({
      ...fold,
      state: fold.state as FoldState,
      clauses: fold.clauses.map((segments) =>
        segments.map(([text, mark]) => (mark ? { text, mark: mark as Mark } : { text })),
      ),
    }),
  ),
}

export const LAST_FOLD = sample.folds.length

export function foldAt(number: number): Fold {
  return sample.folds[number - 1]
}

/** The clause a fold changes; the first draft shows the clause the next fold changes. */
export function focusClause(fold: Fold): number {
  const changed = fold.clauses.findIndex((segments) => segments.some((s) => s.mark))
  return changed === -1 ? 0 : changed
}

export { pad } from '@/lib/format'

/** What a fold is, in words: for the slider's value text and the live status. */
export function describeFold(fold: Fold): string {
  const what =
    fold.state === 'withdrawn'
      ? `${fold.note}, withdrawn and kept on the record`
      : fold.state === 'restored'
        ? `${fold.note}, restores version ${fold.restores}, current`
        : (fold.note ?? 'created the agreement')
  return `Version ${fold.number} of ${LAST_FOLD}: ${fold.author}, ${what}`
}
