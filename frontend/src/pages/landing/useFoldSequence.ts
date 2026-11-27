import { useCallback, useEffect, useRef, useState } from 'react'
import { flushSync } from 'react-dom'

import { LAST_FOLD } from './history'

// The fold grammar: one fold at a time, each panel rotating on its crease with paper weight
// (about 420 ms in all, split around the moment the panel stands on edge). Nothing slides.
// With reduced motion the states swap directly.

const HALF = 210
const FIRST_DWELL = 900 // on the first draft, before the replay folds on
const DWELL = 1500 // time to read each fold during a replay

const LIFT: Keyframe[] = [
  { transform: 'perspective(1400px) rotateX(0deg)', filter: 'brightness(1)' },
  { transform: 'perspective(1400px) rotateX(-90deg)', filter: 'brightness(0.82)' },
]
const LAY: Keyframe[] = [...LIFT].reverse()

/** Resolves when the animations finish, or after their time anyway: a page that isn't rendering
 *  (a hidden tab) doesn't advance animations, and a fold must never leave a panel on its edge. */
function settled(animations: Animation[]): Promise<unknown> {
  const finished = Promise.all(animations.map((a) => a.finished))
  const deadline = new Promise<void>((resolve) =>
    window.setTimeout(() => {
      animations.forEach((a) => a.finish())
      resolve()
    }, HALF + 250),
  )
  return Promise.race([finished, deadline])
}

export type FoldSequence = {
  shown: number // the fold on the sheet now
  target: number // the fold asked for; the sheet steps toward it
  playing: boolean
  moved: boolean // whether the sheet has folded since the page opened
  choose: (fold: number) => void
  replay: () => void
  stop: () => void
}

export function useFoldSequence(reduced: boolean, panels: () => HTMLElement[]): FoldSequence {
  // The sheet rests on the current version, every crease on it; Replay and the margin column fold it.
  const [shown, setShown] = useState(LAST_FOLD)
  const [target, setTarget] = useState(LAST_FOLD)
  const [replaying, setReplaying] = useState(false)
  const [moved, setMoved] = useState(false)
  const [steps, setSteps] = useState(0) // bumps when a fold finishes, to take the next step
  const busy = useRef(false)

  useEffect(() => {
    if (busy.current || shown === target) return
    const next = shown + Math.sign(target - shown)
    const visible = panels().filter((el) => typeof el.animate === 'function' && el.offsetParent)
    if (reduced || visible.length === 0 || document.hidden) {
      const id = window.setTimeout(() => setShown(next), 0) // states swap directly
      return () => window.clearTimeout(id)
    }
    busy.current = true
    let cancelled = false
    const lift = visible.map((el) =>
      el.animate(LIFT, { duration: HALF, easing: 'cubic-bezier(0.55, 0, 0.8, 0.4)', fill: 'forwards' }),
    )
    settled(lift)
      .then(() => {
        if (cancelled) return
        flushSync(() => setShown(next))
        const lay = visible.map((el) =>
          el.animate(LAY, { duration: HALF, easing: 'cubic-bezier(0.2, 0.6, 0.45, 1)' }),
        )
        lift.forEach((a) => a.cancel())
        return settled(lay)
      })
      .catch(() => {}) // an animation cancelled mid-fold (the user chose another fold)
      .finally(() => {
        if (cancelled) lift.forEach((a) => a.cancel())
        busy.current = false
        setSteps((n) => n + 1)
      })
    return () => {
      cancelled = true
    }
  }, [shown, target, reduced, panels, steps])

  // A replay waits on each fold before asking for the next, and is over once the last has folded.
  const playing = replaying && !(shown === LAST_FOLD && target === LAST_FOLD)
  useEffect(() => {
    if (!playing || busy.current || shown !== target) return
    const id = window.setTimeout(() => setTarget(target + 1), target === 1 ? FIRST_DWELL : DWELL)
    return () => window.clearTimeout(id)
  }, [playing, shown, target, steps])

  const choose = useCallback((fold: number) => {
    setMoved(true)
    setReplaying(false)
    setTarget(Math.min(LAST_FOLD, Math.max(1, fold)))
  }, [])

  const replay = useCallback(() => {
    setMoved(true)
    setTarget(1)
    setReplaying(true)
  }, [])

  const stop = useCallback(() => setReplaying(false), [])

  return { shown, target, playing, moved, choose, replay, stop }
}
