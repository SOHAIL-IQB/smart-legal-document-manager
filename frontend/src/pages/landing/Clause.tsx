import { focusClause, sample, type Fold } from './history'

type Props = {
  fold: Fold
  className: string
  glow: boolean
  /** Show only the clause this fold changes (the sheet); otherwise both (the excerpt on the ground). */
  focused?: boolean
}

/** Clauses 3 and 4 at one fold. Inserted words are underlined, removed ones struck (form, not colour).
 *  `glow` gives the changed words a short afterglow; it is off until the sheet first folds. */
export function Clause({ fold, className, glow, focused = false }: Props) {
  const indexes = focused ? [focusClause(fold)] : fold.clauses.map((_, index) => index)
  return (
    <div className={className} data-glow={glow || undefined}>
      <p className="clause__sample">Sample text: {sample.title}</p>
      {indexes.map((index) => (
        <p key={index} className="clause__text">
          {fold.clauses[index].map((segment, i) => {
            const key = `${fold.number}-${index}-${i}` // new keys per fold restart the afterglow
            if (segment.mark === 'ins') return <ins key={key}>{segment.text}</ins>
            if (segment.mark === 'del') return <del key={key}>{segment.text}</del>
            return <span key={key}>{segment.text}</span>
          })}
        </p>
      ))}
    </div>
  )
}
