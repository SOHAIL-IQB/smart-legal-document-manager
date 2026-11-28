import { Link } from 'react-router'

import type { VersionSummary } from '@/api/document'
import { pad } from '@/lib/format'
import { exactTime, timeAgo } from '@/lib/time'

export type LineForm = 'live' | 'withdrawn' | 'restored'

export const lineForm = (v: VersionSummary): LineForm =>
  v.is_deleted ? 'withdrawn' : v.source === 'restore' ? 'restored' : 'live'

type Props = {
  versions: VersionSummary[] // newest first
  reading: number | undefined // the version on the page, when reading
  current: number // the newest live version
  compare?: { from: number; to: number; pick: (side: 'from' | 'to', n: number) => void }
}

/** The margin column: every version as a numbered fold, its state drawn by line form and named. */
export function VersionColumn({ versions, reading, current, compare }: Props) {
  return (
    <ol className="versions" aria-label="Versions">
      {versions.map((v) => {
        const form = lineForm(v)
        const isReading = v.version_number === reading
        return (
          <li
            key={v.version_number}
            className="versions__item"
            data-state={form}
            data-reading={isReading || undefined}
          >
            <Link
              to={`?v=${v.version_number}`}
              className="versions__link"
              aria-current={isReading ? 'true' : undefined}
            >
              <span className="versions__number">{pad(v.version_number)}</span>
              <span className="versions__rule" aria-hidden="true" />
              {v.version_number === current && <span className="gold-dot versions__dot" aria-hidden="true" />}
              <span className="versions__text">
                <span className="versions__who">
                  {v.edited_by_name}
                  {v.version_number === current && (
                    <span className="versions__current">
                      <span className="gold-dot" aria-hidden="true" /> current
                    </span>
                  )}
                </span>
                <span className="versions__what">
                  <time dateTime={v.created_at} title={exactTime(v.created_at)}>
                    {timeAgo(v.created_at)}
                  </time>
                  {form === 'restored' && v.restored_from && <> · restores {pad(v.restored_from)}</>}
                  {v.source === 'upload' && v.source_filename && <> · from {v.source_filename}</>}
                  {form === 'withdrawn' && <> · withdrawn, kept on the record</>}
                </span>
                {v.change_note && <span className="versions__note">{v.change_note}</span>}
              </span>
            </Link>
            {compare && form !== 'withdrawn' && (
              <span className="versions__pick">
                {(['from', 'to'] as const).map((side) => (
                  <button
                    key={side}
                    type="button"
                    className="versions__pick-button"
                    aria-label={`Compare ${side} version ${v.version_number}`}
                    aria-pressed={compare[side] === v.version_number}
                    onClick={() => compare.pick(side, v.version_number)}
                  >
                    {side === 'from' ? 'From' : 'To'}
                  </button>
                ))}
              </span>
            )}
          </li>
        )
      })}
    </ol>
  )
}
