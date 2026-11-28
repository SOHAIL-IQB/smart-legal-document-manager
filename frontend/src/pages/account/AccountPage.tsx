import { useId, type ReactNode } from 'react'
import { Link, Navigate, useLocation } from 'react-router'

import { returnPath } from '@/auth/returnTo'
import { useSession } from '@/auth/session'
import { useOpenDemo } from '@/auth/useOpenDemo'

import type { FormProblem } from './serverErrors'
import './account.css'

type Props = { title: string; children: ReactNode }

/** The sheet turned over: the title on the vermilion face, the form on the washi underside. */
export function AccountPage({ title, children }: Props) {
  const location = useLocation()
  const to = returnPath(location.state)
  const session = useSession()
  const demo = useOpenDemo(to)
  const demoId = useId()

  if (session.data) return <Navigate to={to} replace />

  return (
    <div className="account">
      <title>{`${title.replace(/\.$/, '')} · Inkstep`}</title>
      <section className="account__face" aria-labelledby="account-title">
        <Link to="/" className="account__wordmark" aria-label="Inkstep, home">
          <span className="account__mark" aria-hidden="true" />
          Inkstep
        </Link>
        <h1 id="account-title" className="account__title">
          {title}
        </h1>
      </section>

      <main className="account__underside">
        <div className="account__body">
          {children}
          <div className="account__demo">
            <button
              type="button"
              className="account__demo-button"
              data-pending={demo.isPending || undefined}
              aria-disabled={demo.isPending || undefined}
              aria-labelledby={`${demoId}-label`}
              aria-describedby={`${demoId}-note`}
              onClick={() => {
                if (!demo.isPending) demo.mutate()
              }}
            >
              <span className="account__demo-text">
                <span id={`${demoId}-label`} className="account__demo-label">
                  {demo.isPending ? 'Opening your workspace…' : 'Open a demo workspace instead'}
                </span>
                <span id={`${demoId}-note`} className="account__demo-note">
                  Private to you, with sample contracts. Deleted after 24&nbsp;hours.
                </span>
              </span>
              {/* This strip of the underside, its corner turned back to show the vermilion face. */}
              <span className="account__demo-corner" aria-hidden="true">
                <span className="account__demo-ground" />
                <span className="account__demo-lift">
                  <span className="account__demo-flap" />
                </span>
              </span>
            </button>
          </div>
        </div>
      </main>
    </div>
  )
}

/** The whole form's one problem, when it isn't about a single field. */
export function FormAlert({ problem }: { problem: FormProblem | null }) {
  if (!problem) return null
  return (
    <div role="alert" className="form-alert">
      <p>{problem.message}</p>
      {problem.requestId && <p className="form-alert__reference">Reference: {problem.requestId}</p>}
    </div>
  )
}
