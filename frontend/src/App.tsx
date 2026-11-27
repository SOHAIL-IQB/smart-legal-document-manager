import { useEffect, useState } from 'react'

import { fetchReadiness } from '@/api/health'

type Status = { state: 'checking' } | { state: 'ready'; database: string } | { state: 'down'; reason: string }

/** Placeholder until the landing page (Phase 9 F4): proves the app reaches the API through the proxy. */
export default function App() {
  const [status, setStatus] = useState<Status>({ state: 'checking' })

  useEffect(() => {
    const controller = new AbortController()
    fetchReadiness(controller.signal)
      .then((body) => setStatus({ state: 'ready', database: body.database ?? 'unknown' }))
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          setStatus({ state: 'down', reason: error instanceof Error ? error.message : String(error) })
        }
      })
    return () => controller.abort()
  }, [])

  return (
    <main>
      <h1>Inkstep</h1>
      <p role="status">
        {status.state === 'checking' && 'Checking the API…'}
        {status.state === 'ready' && `API ready · database ${status.database}`}
        {status.state === 'down' && `API unavailable: ${status.reason}`}
      </p>
    </main>
  )
}
