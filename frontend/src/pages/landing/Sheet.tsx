import type { Ref } from 'react'

import { Clause } from './Clause'
import { CornerFold } from './CornerFold'
import { foldAt, type FoldState } from './history'

// One crease per fold, drawn in that fold's line form; the sheet carries every crease up to the fold
// it shows. The corner's own crease is the next fold: the visitor's.
const CREASES: { fold: number; d: string; form: FoldState }[] = [
  { fold: 1, d: 'M0 50 H100', form: 'live' },
  { fold: 2, d: 'M50 0 V100', form: 'live' },
  { fold: 3, d: 'M0 0 L100 100', form: 'withdrawn' },
  { fold: 4, d: 'M100 0 L0 100', form: 'restored' },
]

type Props = { shown: number; glow: boolean; clauseRef: Ref<HTMLElement> }

export function Sheet({ shown, glow, clauseRef }: Props) {
  const fold = foldAt(shown)
  return (
    <div className="sheet">
      <svg className="sheet__creases" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
        {CREASES.map((crease) => (
          <g key={crease.fold} className="crease" data-form={crease.form} data-on={crease.fold <= shown || undefined}>
            {crease.form === 'restored' && <path d={crease.d} className="crease__double" />}
            <path d={crease.d} />
          </g>
        ))}
      </svg>

      <h1 id="hero-title" className="sheet__headline">
        One sheet.
        <br /> Every fold kept.
      </h1>

      <figure ref={clauseRef} className="sheet__panel sheet__clause" aria-label={`Sample text at version ${shown}`}>
        <Clause fold={fold} className="clause clause--sheet" glow={glow} focused />
      </figure>

      <CornerFold />
    </div>
  )
}
