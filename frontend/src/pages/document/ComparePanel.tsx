import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useId } from 'react'

import { compareVersions, type Comparison, type DiffRow, type Segment, type VersionSummary } from '@/api/document'
import { pad } from '@/lib/format'

import { ErrorNote } from './ReadPanel'

const CONTEXT = 3 // unchanged lines kept around each change while collapsed

type Props = {
  documentId: number
  live: VersionSummary[] // newest first
  from: number
  to: number
  everyLine: boolean
  onChange: (next: { from?: number; to?: number; everyLine?: boolean }) => void
}

const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? '' : 's'}`
const identical = (c: Comparison) =>
  c.stats.words_added + c.stats.words_removed + c.stats.lines_added + c.stats.lines_removed + c.stats.lines_changed === 0

/** Two versions side by side: inserted words underlined, removed words struck, by the API's rows. */
export function ComparePanel({ documentId, live, from, to, everyLine, onChange }: Props) {
  const id = useId()
  const comparison = useQuery({
    queryKey: ['compare', documentId, from, to, everyLine],
    queryFn: ({ signal }) => compareVersions(documentId, from, to, everyLine ? undefined : CONTEXT, signal),
    placeholderData: keepPreviousData,
    meta: { silent: true },
  })

  const select = (side: 'from' | 'to', value: number) => (
    <div>
      <label htmlFor={`${id}-${side}`} className="field__label">
        {side === 'from' ? 'From' : 'To'}
      </label>
      <select
        id={`${id}-${side}`}
        className="field__select"
        value={value}
        onChange={(event) => onChange({ [side]: Number(event.target.value) })}
      >
        {live.map((v) => (
          <option key={v.version_number} value={v.version_number}>
            {pad(v.version_number)} · {v.edited_by_name}
          </option>
        ))}
      </select>
    </div>
  )

  const data = comparison.data
  return (
    <section className="compare" aria-label="Compare versions">
      <div className="compare__controls">
        {select('from', from)}
        {select('to', to)}
        <label className="compare__toggle">
          <input type="checkbox" checked={everyLine} onChange={(event) => onChange({ everyLine: event.target.checked })} />
          Show every line
        </label>
      </div>

      {comparison.isPending ? (
        <p role="status" className="reading__status">
          Comparing…
        </p>
      ) : comparison.isError ? (
        <ErrorNote error={comparison.error} retry={() => void comparison.refetch()} />
      ) : (
        <>
          <p className="compare__stats">
            {identical(data) ? (
              'The two texts are identical.'
            ) : (
              <>
                {plural(data.stats.words_added, 'word')} added, {plural(data.stats.words_removed, 'word')} removed ·{' '}
                {plural(data.stats.lines_changed + data.stats.lines_added + data.stats.lines_removed, 'line')} touched
                {!data.has_meaningful_changes && <> · only spacing differs</>}
              </>
            )}
          </p>
          {data.approximate && (
            <p role="note" className="compare__approximate">
              This comparison is approximate. The versions are long and very different, so some text that
              moved may show as removed in one place and added in another.
            </p>
          )}
          {/* Explicit roles keep it a table for screen readers when phones restack its rows. */}
          <table role="table" className="diff" aria-busy={comparison.isFetching || undefined}>
            <caption className="sr-only">
              Version {data.version_1} compared with version {data.version_2}
            </caption>
            <thead role="rowgroup">
              <tr role="row">
                <th role="columnheader" scope="col" className="diff__line">
                  <span className="sr-only">Line</span>
                </th>
                <th role="columnheader" scope="col">Version {data.version_1}</th>
                <th role="columnheader" scope="col" className="diff__line">
                  <span className="sr-only">Line</span>
                </th>
                <th role="columnheader" scope="col">Version {data.version_2}</th>
              </tr>
            </thead>
            <tbody role="rowgroup">
              {data.rows.map((row, index) => (
                <Row
                  key={index}
                  row={row}
                  labels={[`Version ${data.version_1}`, `Version ${data.version_2}`]}
                  onShowAll={() => onChange({ everyLine: true })}
                />
              ))}
            </tbody>
          </table>
        </>
      )}
    </section>
  )
}

function Row({ row, labels, onShowAll }: { row: DiffRow; labels: [string, string]; onShowAll: () => void }) {
  if (row.type === 'skip') {
    return (
      <tr role="row" className="diff__skip">
        <td role="cell" colSpan={4}>
          <button type="button" className="text-button" onClick={onShowAll}>
            {plural(row.skipped ?? 0, 'unchanged line')}
          </button>
        </td>
      </tr>
    )
  }
  const old = row.type === 'insert' ? null : (row.old_segments ?? row.old_text)
  const next = row.type === 'delete' ? null : (row.new_segments ?? row.new_text)
  return (
    <tr
      role="row"
      className="diff__row"
      data-type={row.type}
      data-blank={(row.type === 'equal' && !row.old_text?.trim() && !row.new_text?.trim()) || undefined}
    >
      <td role="cell" className="diff__line">{row.old_line ?? ''}</td>
      <td role="cell" className="diff__old" data-label={labels[0]}>
        {render(old, row.type === 'delete' ? 'del' : undefined)}
      </td>
      <td role="cell" className="diff__line">{row.new_line ?? ''}</td>
      <td role="cell" className="diff__new" data-label={labels[1]}>
        {render(next, row.type === 'insert' ? 'ins' : undefined)}
        {row.whitespace_only && <span className="diff__spacing"> (spacing only)</span>}
      </td>
    </tr>
  )
}

/** Segments marked by form; a whole inserted or removed line is one underline or strike. */
function render(content: Segment[] | string | null | undefined, whole?: 'ins' | 'del') {
  if (content === null || content === undefined) return null
  if (typeof content === 'string') {
    if (whole === 'ins') return <ins>{content}</ins>
    if (whole === 'del') return <del>{content}</del>
    return content
  }
  return content.map((segment, i) =>
    segment.op === 'insert' ? (
      <ins key={i}>{segment.text}</ins>
    ) : segment.op === 'delete' ? (
      <del key={i}>{segment.text}</del>
    ) : (
      <span key={i}>{segment.text}</span>
    ),
  )
}
