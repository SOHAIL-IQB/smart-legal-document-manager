import { useCallback, useRef } from 'react'
import { Link } from 'react-router'

import { useReducedMotion } from '@/lib/useReducedMotion'

import { Clause } from './landing/Clause'
import { useWorkspaceEntry } from './landing/CornerFold'
import { FoldColumn } from './landing/FoldColumn'
import { describeFold, foldAt } from './landing/history'
import { Sheet } from './landing/Sheet'
import { useFoldSequence } from './landing/useFoldSequence'
import './landing/landing.css'

const SOURCE = 'https://github.com/SOHAIL-IQB/smart-legal-document-manager'

export function Landing() {
  const reduced = useReducedMotion()
  const clausePanel = useRef<HTMLElement>(null)
  const excerptPanel = useRef<HTMLDivElement>(null)
  const panels = useCallback(
    () => [clausePanel.current, excerptPanel.current].filter((el): el is HTMLElement => el !== null),
    [],
  )
  const sequence = useFoldSequence(reduced, panels)
  const fold = foldAt(sequence.shown)

  return (
    <div className="landing">
      <section className="hero" aria-labelledby="hero-title">
        <header className="masthead">
          <Link to="/" className="wordmark" aria-label="Inkstep, home">
            <span className="wordmark__mark" aria-hidden="true" />
            Inkstep
          </Link>
          <nav aria-label="Account">
            <Link to="/sign-in" className="masthead__link">
              Sign in
            </Link>
          </nav>
        </header>

        <Sheet shown={sequence.shown} glow={sequence.moved} clauseRef={clausePanel} />

        <div className="hero__folds">
          <FoldColumn sequence={sequence} />
          <p className="sr-only" aria-live="polite">
            {sequence.playing ? describeFold(fold) : ''}
          </p>
        </div>

        <p className="hero__intro">
          Inkstep keeps every version of a contract. Compare any two, word by word. A withdrawn
          draft stays on the record, and nothing is ever overwritten.
        </p>

        <div ref={excerptPanel} className="hero__excerpt">
          <Clause fold={fold} className="clause clause--ground" glow={sequence.moved} />
        </div>
      </section>

      <Legend />
      <Record />
      <Close />

      <footer className="footer">
        <p>
          Inkstep is a portfolio project. The people, companies and contracts in the demo are
          fictional.
        </p>
        <a href={SOURCE} className="footer__link">
          Source on GitHub
        </a>
      </footer>
    </div>
  )
}

const LEGEND = [
  { sample: <span className="legend__rule" data-form="live" />, text: 'A version on the record.' },
  {
    sample: <span className="legend__rule" data-form="withdrawn" />,
    text: 'Withdrawn, but kept: it stays in the history and the activity log.',
  },
  {
    sample: <span className="legend__rule" data-form="restored" />,
    text: 'Restored: an earlier text comes back as a new version.',
  },
  { sample: <ins className="legend__word">inserted</ins>, text: 'Words added since the version before.' },
  { sample: <del className="legend__word">removed</del>, text: 'Words taken out.' },
  { sample: <span className="gold-dot gold-dot--large" />, text: 'The current version.' },
]

function Legend() {
  return (
    <section className="legend" aria-labelledby="legend-title">
      <h2 id="legend-title" className="section-title">
        How to read a sheet
      </h2>
      <dl className="legend__list">
        {LEGEND.map((item) => (
          <div key={item.text} className="legend__item">
            <dt className="legend__sample">{item.sample}</dt>
            <dd className="legend__text">{item.text}</dd>
          </div>
        ))}
      </dl>
    </section>
  )
}

const RECORD = [
  {
    title: 'Nothing is overwritten.',
    text: 'Every edit, upload and restore adds a version. Version numbers are never reused.',
  },
  {
    title: 'Any two versions, word by word.',
    text: 'Side by side, showing exactly which words changed, and fast on long contracts.',
  },
  {
    title: 'Shared on each document’s terms.',
    text: 'Owners, editors and viewers. People who aren’t members can’t tell the document exists.',
  },
  {
    title: 'Every action on the record.',
    text: 'An activity log that is only ever added to, and a notification when a document you belong to changes.',
  },
]

function Record() {
  return (
    <section className="record" aria-labelledby="record-title">
      <h2 id="record-title" className="section-title">
        Built so the record holds
      </h2>
      <ul className="record__panels">
        {RECORD.map((item) => (
          <li key={item.title} className="record__panel">
            <h3 className="record__title">{item.title}</h3>
            <p className="record__text">{item.text}</p>
          </li>
        ))}
      </ul>
    </section>
  )
}

function Close() {
  const { signedIn, open } = useWorkspaceEntry()
  return (
    <section className="close" aria-labelledby="close-title">
      <h2 id="close-title" className="close__title">
        Your own copy, for a day.
      </h2>
      <div className="close__underside">
        <p>
          A demo workspace is yours alone: three sample people, Asha Rao, Ben Carter and Chloe
          Martin, and four sample contracts with their history. You start as Asha and can switch to
          Ben or Chloe to see each role. Everything in it is deleted after 24 hours.
        </p>
        <div className="close__actions">
          {signedIn ? (
            <Link to="/documents" className="button-fold">
              Go to your documents
            </Link>
          ) : (
            <button
              type="button"
              className="button-fold"
              aria-disabled={open.isPending || undefined}
              onClick={() => {
                if (!open.isPending) open.mutate()
              }}
            >
              {open.isPending ? 'Opening your workspace…' : 'Open your demo workspace'}
            </button>
          )}
          {!signedIn && (
            <Link to="/sign-in" className="close__link">
              Sign in with an account
            </Link>
          )}
        </div>
      </div>
    </section>
  )
}
