import { Link } from 'react-router'

/** Stand-in for a screen built later in Phase 9; names the task that builds it. */
export function Placeholder({ title, task }: { title: string; task: string }) {
  return (
    <main>
      <h1>{title}</h1>
      <p>Built in Phase 9 {task}.</p>
      <Link to="/">Back to the start</Link>
    </main>
  )
}
