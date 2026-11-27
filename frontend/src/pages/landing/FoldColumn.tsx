import { RotateCcw, Square } from 'lucide-react'
import { useRef, type KeyboardEvent, type PointerEvent } from 'react'

import { describeFold, foldAt, LAST_FOLD, pad, sample } from './history'
import type { FoldSequence } from './useFoldSequence'

/** The margin column: the fold numbers, as a slider. Drag along it, click a fold, or use the keys. */
export function FoldColumn({ sequence }: { sequence: FoldSequence }) {
  const { shown, target, playing, choose, replay, stop } = sequence
  const list = useRef<HTMLOListElement>(null)

  // The column runs down the margin on wide screens and across under the sheet on narrow ones.
  function foldAtPoint(clientX: number, clientY: number): number | null {
    const rows = list.current?.children
    if (!rows || rows.length === 0) return null
    const across = rows.length > 1 && rows[0].getBoundingClientRect().top === rows[1].getBoundingClientRect().top
    for (let i = 0; i < rows.length; i++) {
      const box = rows[i].getBoundingClientRect()
      if ((across ? clientX < box.right : clientY < box.bottom) || i === rows.length - 1) return i + 1
    }
    return null
  }

  function onPointerDown(event: PointerEvent<HTMLDivElement>) {
    if (event.button !== 0) return
    event.currentTarget.setPointerCapture?.(event.pointerId)
    const fold = foldAtPoint(event.clientX, event.clientY)
    if (fold) choose(fold)
  }

  function onPointerMove(event: PointerEvent<HTMLDivElement>) {
    if (!event.currentTarget.hasPointerCapture?.(event.pointerId)) return
    const fold = foldAtPoint(event.clientX, event.clientY)
    if (fold && fold !== target) choose(fold)
  }

  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    const steps: Record<string, number> = {
      ArrowDown: target + 1,
      ArrowRight: target + 1,
      PageDown: target + 1,
      ArrowUp: target - 1,
      ArrowLeft: target - 1,
      PageUp: target - 1,
      Home: 1,
      End: LAST_FOLD,
    }
    if (!(event.key in steps)) return
    event.preventDefault()
    choose(steps[event.key])
  }

  return (
    <div className="folds">
      <div
        className="folds__slider"
        role="slider"
        tabIndex={0}
        aria-label="Versions of the sample agreement"
        aria-valuemin={1}
        aria-valuemax={LAST_FOLD}
        aria-valuenow={target}
        aria-valuetext={describeFold(foldAt(target))}
        onKeyDown={onKeyDown}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
      >
        <ol ref={list} className="folds__list" aria-hidden="true">
          {sample.folds.map((fold) => (
            <li
              key={fold.number}
              className="folds__row"
              data-state={fold.state}
              data-shown={fold.number === shown || undefined}
            >
              <span className="folds__number">{pad(fold.number)}</span>
              <span className="folds__rule" />
              {fold.number === LAST_FOLD && <span className="gold-dot folds__dot" />}
              <span className="folds__text">
                <span className="folds__author">
                  {fold.author}
                  {fold.number === LAST_FOLD && (
                    <span className="folds__current">
                      <span className="gold-dot" />
                      current
                    </span>
                  )}
                </span>
                <span className="folds__note">
                  {fold.note ?? 'Created the agreement'}
                  {fold.state === 'withdrawn' && <em> · withdrawn, kept</em>}
                  {fold.state === 'restored' && <em> · restores {pad(fold.restores ?? 0)}</em>}
                </span>
              </span>
            </li>
          ))}
        </ol>
      </div>
      <p className="folds__caption" aria-hidden="true">
        <span className="folds__caption-number">{pad(shown)}</span> {foldAt(shown).author}
        {' · '}
        {foldAt(shown).note ?? 'Created the agreement'}
        {foldAt(shown).state === 'withdrawn' && ' · withdrawn, kept'}
        {foldAt(shown).state === 'restored' && ` · restores ${pad(foldAt(shown).restores ?? 0)}`}
      </p>
      <button type="button" className="folds__replay" onClick={playing ? stop : replay}>
        {playing ? <Square aria-hidden size={16} /> : <RotateCcw aria-hidden size={16} />}
        {playing ? 'Stop' : 'Replay the history'}
      </button>
    </div>
  )
}
