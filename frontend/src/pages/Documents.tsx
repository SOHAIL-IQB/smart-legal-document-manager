import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { ArrowLeft, ArrowRight, Plus } from 'lucide-react'
import { useEffect, useEffectEvent, useId, useState } from 'react'
import { Link, useSearchParams } from 'react-router'

import { listDocuments, type DocumentSummary, type Role, type SortField, type SortOrder } from '@/api/documents'
import { describeError } from '@/lib/errors'
import { exactTime, isWithinLastDay, timeAgo } from '@/lib/time'
import { useDebounced } from '@/lib/useDebounced'

import { NewDocumentDialog } from './documents/NewDocumentDialog'
import './documents/documents.css'

const PAGE_SIZE = 20
const ROLES: Role[] = ['owner', 'editor', 'viewer']
const SORTS: { value: `${SortField}:${SortOrder}`; label: string }[] = [
  { value: 'updated_at:desc', label: 'Recently changed' },
  { value: 'updated_at:asc', label: 'Changed longest ago' },
  { value: 'created_at:desc', label: 'Newly created' },
  { value: 'created_at:asc', label: 'Created first' },
  { value: 'title:asc', label: 'Title, A to Z' },
  { value: 'title:desc', label: 'Title, Z to A' },
]
const DEFAULT_SORT = 'updated_at:desc'

const capital = (text: string) => text.charAt(0).toUpperCase() + text.slice(1)

/** The register: the URL holds the search, role, sort and page, so Back and shared links work. */
function useRegisterParams() {
  const [params, setParams] = useSearchParams()
  const role = params.get('role')
  const sort = SORTS.some((s) => s.value === params.get('sort') + ':' + params.get('order'))
    ? `${params.get('sort')}:${params.get('order')}`
    : DEFAULT_SORT
  const page = Math.max(1, Number.parseInt(params.get('page') ?? '1', 10) || 1)
  const view = {
    q: params.get('q') ?? '',
    role: ROLES.includes(role as Role) ? (role as Role) : undefined,
    sort,
    page,
  }

  /** Change the view; anything but a page change goes back to the first page. */
  function update(next: Partial<typeof view>) {
    const merged = { ...view, page: 1, ...next }
    const out = new URLSearchParams()
    if (merged.q) out.set('q', merged.q)
    if (merged.role) out.set('role', merged.role)
    if (merged.sort !== DEFAULT_SORT) {
      const [field, order] = merged.sort.split(':')
      out.set('sort', field)
      out.set('order', order)
    }
    if (merged.page > 1) out.set('page', String(merged.page))
    setParams(out, { replace: 'q' in next && !('page' in next) })
  }
  return { view, update }
}

export function Documents() {
  const { view, update } = useRegisterParams()
  const [newOpen, setNewOpen] = useState(false)
  const [field, order] = view.sort.split(':') as [SortField, SortOrder]
  const offset = (view.page - 1) * PAGE_SIZE

  const list = useQuery({
    queryKey: ['documents', view.q, view.role, field, order, offset],
    queryFn: ({ signal }) =>
      listDocuments(
        {
          q: view.q || undefined,
          role: view.role,
          sort: view.sort === DEFAULT_SORT ? undefined : field,
          order: view.sort === DEFAULT_SORT ? undefined : order,
          limit: PAGE_SIZE,
          offset,
        },
        signal,
      ),
    placeholderData: keepPreviousData,
    meta: { silent: true }, // the register shows its own error
  })

  return (
    <main className="documents">
      <title>Documents · Inkstep</title>
      <section className="page-band" aria-labelledby="documents-title">
        <h1 id="documents-title" className="page-band__title">
          Documents.
        </h1>
        <button type="button" className="tag tag--large" onClick={() => setNewOpen(true)}>
          <Plus aria-hidden size={18} />
          New document
        </button>
      </section>

      <div className="register">
        <Controls view={view} update={update} />
        <Results
          list={list}
          view={view}
          sortField={field}
          sortOrder={order}
          offset={offset}
          onPage={(page) => update({ page })}
          onClear={(what) => update(what === 'q' ? { q: '' } : { role: undefined })}
          onNew={() => setNewOpen(true)}
        />
      </div>

      <NewDocumentDialog open={newOpen} onOpenChange={setNewOpen} />
    </main>
  )
}

type View = ReturnType<typeof useRegisterParams>['view']
type Update = ReturnType<typeof useRegisterParams>['update']

function Controls({ view, update }: { view: View; update: Update }) {
  const id = useId()
  const [text, setText] = useState(view.q)
  const [shownQ, setShownQ] = useState(view.q)
  const typed = useDebounced(text.trim(), 300)

  // The address can change under us (Back, Clear the search): follow it.
  // https://react.dev/learn/you-might-not-need-an-effect#adjusting-some-state-when-a-prop-changes
  if (view.q !== shownQ) {
    setShownQ(view.q)
    if (view.q !== text.trim()) setText(view.q)
  }

  // Typing reaches the address once it settles; reading the latest view without re-running on it.
  const onTyped = useEffectEvent((q: string) => {
    if (q !== view.q) update({ q })
  })
  useEffect(() => onTyped(typed), [typed])

  return (
    <div className="register__controls" role="search">
      <div className="register__search">
        <label htmlFor={`${id}-q`} className="field__label">
          Search documents
        </label>
        <div className="field__line">
          <input
            id={`${id}-q`}
            type="search"
            className="field__input"
            placeholder="Titles and text"
            maxLength={200}
            value={text}
            onChange={(event) => setText(event.target.value)}
          />
          {text && (
            <button type="button" className="field__toggle" aria-label="Clear search" onClick={() => setText('')}>
              Clear
            </button>
          )}
        </div>
      </div>
      <div>
        <label htmlFor={`${id}-role`} className="field__label">
          Your role
        </label>
        <select
          id={`${id}-role`}
          className="field__select"
          value={view.role ?? ''}
          onChange={(event) => update({ role: (event.target.value || undefined) as Role | undefined })}
        >
          <option value="">Any role</option>
          {ROLES.map((role) => (
            <option key={role} value={role}>
              {capital(role)}
            </option>
          ))}
        </select>
      </div>
      <div>
        <label htmlFor={`${id}-sort`} className="field__label">
          Sort by
        </label>
        <select
          id={`${id}-sort`}
          className="field__select"
          value={view.sort}
          onChange={(event) => update({ sort: event.target.value })}
        >
          {SORTS.map((sort) => (
            <option key={sort.value} value={sort.value}>
              {sort.label}
            </option>
          ))}
        </select>
      </div>
    </div>
  )
}

type ResultsProps = {
  list: ReturnType<typeof useQuery<Awaited<ReturnType<typeof listDocuments>>>>
  view: View
  sortField: SortField
  sortOrder: SortOrder
  offset: number
  onPage: (page: number) => void
  onClear: (what: 'q' | 'role') => void
  onNew: () => void
}

function Results({ list, view, sortField, sortOrder, offset, onPage, onClear, onNew }: ResultsProps) {
  if (list.isPending) {
    return (
      <p role="status" className="register__state">
        Loading your documents…
      </p>
    )
  }
  if (list.isError) {
    const { message, requestId } = describeError(list.error)
    return (
      <div role="alert" className="register__state register__state--error">
        <p>{message}</p>
        {requestId && <p className="register__reference">Reference: {requestId}</p>}
        <button type="button" className="text-button" onClick={() => void list.refetch()}>
          Try again
        </button>
      </div>
    )
  }

  const { items, total } = list.data
  const noun = total === 1 ? 'document' : 'documents'
  const status = view.q ? `${total} ${noun} match “${view.q}”` : `${total} ${noun}`
  const ariaSort = (column: SortField) =>
    sortField === column ? (sortOrder === 'asc' ? 'ascending' : 'descending') : undefined

  return (
    <>
      <p role="status" className="sr-only">
        {status}
      </p>
      {items.length === 0 ? (
        <Empty view={view} onClear={onClear} onNew={onNew} />
      ) : (
        <>
        <p className="register__key">
          <span className="gold-dot" aria-hidden="true" /> changed in the last day
        </p>
        {/* Explicit roles keep the table a table for screen readers when phones restack its rows. */}
        <table role="table" className="register__table" aria-busy={list.isFetching || undefined}>
          <caption className="sr-only">
            Your documents, in order: {SORTS.find((s) => s.value === view.sort)?.label.toLowerCase()}
          </caption>
          <thead role="rowgroup">
            <tr role="row">
              <th role="columnheader" scope="col" className="register__no">
                No.
              </th>
              <th role="columnheader" scope="col" aria-sort={ariaSort('title')}>
                Document
              </th>
              <th role="columnheader" scope="col" className="register__wide register__role">
                Your role
              </th>
              <th role="columnheader" scope="col" className="register__versions">
                Versions
              </th>
              <th role="columnheader" scope="col" className="register__wide register__number">
                Words
              </th>
              <th role="columnheader" scope="col" aria-sort={ariaSort('updated_at')} className="register__last">
                Last change
              </th>
            </tr>
          </thead>
          <tbody role="rowgroup">
            {items.map((document, index) => (
              <Row key={document.id} document={document} number={offset + index + 1} />
            ))}
          </tbody>
        </table>
        </>
      )}
      {total > PAGE_SIZE && <Pages total={total} offset={offset} count={items.length} onPage={onPage} />}
    </>
  )
}

function Row({ document, number }: { document: DocumentSummary; number: number }) {
  const recent = isWithinLastDay(document.updated_at)
  return (
    <tr role="row">
      <td role="cell" className="register__no">{String(number).padStart(2, '0')}</td>
      <td role="cell" className="register__doc">
        <Link to={`/documents/${document.id}`} className="register__title">
          {document.title}
        </Link>
        <span className="register__meta">
          <span>by {document.created_by_name}</span>
          <span className="register__narrow"> · {capital(document.my_role)}</span>
        </span>
      </td>
      <td role="cell" className="register__wide register__role">{capital(document.my_role)}</td>
      <td role="cell" className="register__versions">
        <span>v{document.latest_version ?? 0}</span>
        <span className="sr-only">, {document.version_count} kept</span>
        {recent && (
          <>
            <span className="gold-dot" aria-hidden="true" title="Changed in the last day" />
            <span className="sr-only">, changed in the last day</span>
          </>
        )}
      </td>
      <td role="cell" className="register__wide register__number">
        {document.word_count?.toLocaleString('en') ?? '–'}
      </td>
      <td role="cell" className="register__last">
        <time dateTime={document.updated_at} title={exactTime(document.updated_at)} className="register__when">
          {timeAgo(document.updated_at)}
        </time>
      </td>
    </tr>
  )
}

function Pages({ total, offset, count, onPage }: { total: number; offset: number; count: number; onPage: (page: number) => void }) {
  const page = offset / PAGE_SIZE + 1
  const last = offset + count >= total
  return (
    <nav className="register__pages" aria-label="Pages">
      <button
        type="button"
        className="text-button"
        aria-label="Previous page"
        disabled={page === 1}
        onClick={() => onPage(page - 1)}
      >
        <ArrowLeft aria-hidden size={16} /> Previous
      </button>
      <span className="register__range">
        {offset + 1}–{offset + count} of {total}
      </span>
      <button
        type="button"
        className="text-button"
        aria-label="Next page"
        disabled={last}
        onClick={() => onPage(page + 1)}
      >
        Next <ArrowRight aria-hidden size={16} />
      </button>
    </nav>
  )
}

function Empty({ view, onClear, onNew }: { view: View; onClear: (what: 'q' | 'role') => void; onNew: () => void }) {
  if (view.q) {
    return (
      <div className="register__state">
        <p className="register__empty">Nothing matches “{view.q}”.</p>
        <button type="button" className="text-button" onClick={() => onClear('q')}>
          Clear the search
        </button>
      </div>
    )
  }
  if (view.role) {
    return (
      <div className="register__state">
        <p className="register__empty">You aren’t {view.role === 'owner' ? 'the owner' : `an ${view.role}`} on any document.</p>
        <button type="button" className="text-button" onClick={() => onClear('role')}>
          Show every role
        </button>
      </div>
    )
  }
  return (
    <div className="register__state">
      <p className="register__empty">No documents yet.</p>
      <p>Upload a PDF, Word or text file, or paste a contract’s text, and it becomes version 1.</p>
      <button type="button" className="button-primary" onClick={onNew}>
        <Plus aria-hidden size={18} /> New document
      </button>
    </div>
  )
}
