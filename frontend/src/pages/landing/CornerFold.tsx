import { ArrowRight } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router'

import { useSession } from '@/auth/session'
import { useOpenDemo } from '@/auth/useOpenDemo'

/** Opens the visitor's own demo workspace, or, when already signed in, their documents. */
export function useWorkspaceEntry() {
  const session = useSession()
  return { signedIn: Boolean(session.data), open: useOpenDemo() }
}

/** The sheet's next fold: its lower corner turned back to show the cream underside. */
export function CornerFold() {
  const { signedIn, open } = useWorkspaceEntry()

  const paper = (label: ReactNode, note: string) => (
    <>
      <span className="corner__ground" aria-hidden="true" />
      <span className="corner__lift" aria-hidden="true">
        <span className="corner__flap" />
      </span>
      <span className="corner__face">
        <span className="corner__label">
          {label}
          <ArrowRight aria-hidden className="corner__arrow" />
        </span>
        <span className="corner__note">{note}</span>
      </span>
    </>
  )

  if (signedIn) {
    return (
      <Link to="/documents" className="corner">
        {paper('Go to your documents', 'You are signed in')}
      </Link>
    )
  }
  return (
    <button
      type="button"
      className="corner"
      data-pending={open.isPending || undefined}
      aria-disabled={open.isPending || undefined}
      onClick={() => {
        if (!open.isPending) open.mutate()
      }}
    >
      {paper(
        open.isPending ? 'Opening your workspace…' : 'Open your demo workspace',
        'Private to you, with sample contracts. Deleted after 24 hours.',
      )}
    </button>
  )
}
