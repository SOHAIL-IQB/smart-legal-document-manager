import { Navigate, Outlet, useLocation } from 'react-router'

import { describeError } from '@/lib/errors'

import { useSession } from './session'

/** Signed-in routes: a signed-out visitor goes to sign-in, which can send them back afterwards. */
export function RequireAuth() {
  const session = useSession()
  const location = useLocation()

  if (session.isPending) {
    return <p role="status">Checking your session…</p>
  }
  if (session.isError) {
    const { message, requestId } = describeError(session.error)
    return (
      <div role="alert">
        <p>{message}</p>
        {requestId && <p>Reference: {requestId}</p>}
        <button type="button" onClick={() => void session.refetch()}>
          Try again
        </button>
      </div>
    )
  }
  if (!session.data) {
    return <Navigate to="/sign-in" replace state={{ from: location.pathname + location.search }} />
  }
  return <Outlet />
}
