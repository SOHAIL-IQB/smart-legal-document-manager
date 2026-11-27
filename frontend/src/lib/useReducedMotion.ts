import { useSyncExternalStore } from 'react'

const QUERY = '(prefers-reduced-motion: reduce)'

function subscribe(onChange: () => void) {
  if (typeof window.matchMedia !== 'function') return () => {}
  const list = window.matchMedia(QUERY)
  list.addEventListener('change', onChange)
  return () => list.removeEventListener('change', onChange)
}

// Where the preference can't be read, don't animate.
const read = () => typeof window.matchMedia !== 'function' || window.matchMedia(QUERY).matches

export function useReducedMotion(): boolean {
  return useSyncExternalStore(subscribe, read, () => true)
}
