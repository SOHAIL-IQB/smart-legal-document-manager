import { Link } from 'react-router'

/** Unknown addresses (Phase 9 F8 designs this page). */
export function NotFound() {
  return (
    <main>
      <h1>This page doesn't exist</h1>
      <Link to="/">Go to the start</Link>
    </main>
  )
}
