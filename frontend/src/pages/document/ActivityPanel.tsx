import { useInfiniteQuery } from '@tanstack/react-query'

import { listActivity } from '@/api/document'
import { exactTime, timeAgo } from '@/lib/time'

import { ErrorNote } from './ReadPanel'
import { describeActivity } from './sentences'

/** The append-only record of this document, newest first, as sentences. */
export function ActivityPanel({ documentId }: { documentId: number }) {
  const pages = useInfiniteQuery({
    queryKey: ['activity', documentId],
    queryFn: ({ pageParam, signal }) => listActivity(documentId, pageParam, signal),
    initialPageParam: 0,
    getNextPageParam: (last) => (last.offset + last.items.length < last.total ? last.offset + last.items.length : undefined),
    meta: { silent: true },
  })

  if (pages.isPending) return <p role="status" className="reading__status">Loading the activity…</p>
  if (pages.isError) return <ErrorNote error={pages.error} retry={() => void pages.refetch()} />

  const items = pages.data.pages.flatMap((page) => page.items)
  const total = pages.data.pages[0]?.total ?? 0
  return (
    <section className="activity" aria-label="Activity log">
      <p className="activity__count">
        {total} {total === 1 ? 'event' : 'events'}, kept for good: nothing in this log is ever changed or removed.
      </p>
      <ol className="activity__list" aria-label="Activity">
        {items.map((item) => (
          <li key={item.id} className="activity__item">
            <span className="activity__what">{describeActivity(item)}</span>
            <time className="activity__when" dateTime={item.created_at} title={exactTime(item.created_at)}>
              {timeAgo(item.created_at)}
            </time>
          </li>
        ))}
      </ol>
      {pages.hasNextPage && (
        <button
          type="button"
          className="text-button"
          disabled={pages.isFetchingNextPage}
          onClick={() => void pages.fetchNextPage()}
        >
          {pages.isFetchingNextPage ? 'Loading…' : 'Show earlier activity'}
        </button>
      )}
    </section>
  )
}
